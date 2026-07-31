"""SNI bug-host hunt orchestrator (ADR-10).

Runs every hunter over the captured host surface, scores each candidate
0-100, and persists the top candidates as ``Finding(kind="sni_bug_host")``
rows. Idempotent: a re-run clears the stage's findings first.

Scoring weights (additive, capped at 100) — this is a FRONTING-LIKELIHOOD
score, NOT a free-internet-confirmation. It ranks candidates by how likely
they are to be usable as an SNI for tunnelling, based on observable signals:
  - captured in this session (vs discovered):       +10  (we know it's live)
  - CDN-frontable edge (Cloudflare/Fastly/Akamai):  +30  (SNI/Host splittable)
  - zero-rating pattern matched:                    +30  (highest-value signal)
  - CT logs: shared cert (>= 5 subdomains):         +15  (multi-name cert)
  - CT logs: wildcard cert:                         +10  (*.domain coverage)
  - reverse-IP: sibling hostnames on the same IP:   +10  (multi-tenant edge)
  - optional probe confirmed the SNI serves a cert: +10  (live verification)

WHAT THE SCORE DOES NOT TELL YOU: whether the host is actually zero-rated
by YOUR carrier. The definitive signal — "bytes flow through the carrier's
DPI without deducting data balance" — needs the user's SIM on the target
network with a real tunnel test. Glyph surfaces CANDIDATES ranked by
fronting likelihood; the user confirms free-internet viability on-device
(RESEARCH.md §10, ADR-10). A high score means "worth testing," not "works."

Severity: >= 70 high, >= 40 medium, else low.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from glyph.catalog import Catalog, Finding, FINDING_SNI_BUG_HOST
from glyph.catalog.models import SEV_HIGH, SEV_MEDIUM, SEV_LOW
from glyph.snihunt import cdn as cdn_mod
from glyph.snihunt import ctlogs as ct_mod
from glyph.snihunt import dns as dns_mod
from glyph.snihunt import extract as extract_mod
from glyph.snihunt import probe as probe_mod
from glyph.snihunt import reverseip as rip_mod
from glyph.snihunt import zerorate as zr_mod
from glyph.snihunt._net import HttpGet

# Categories for SNI findings.
CAT_CANDIDATE = "sni_candidate"
CAT_FRONTABLE = "sni_frontable_cdn"
CAT_ZERO_RATED = "sni_zero_rated"
CAT_SHARED_CERT = "sni_shared_cert"

# Cap candidates persisted so a huge capture doesn't flood the findings table.
# The summary always reports the full count discovered; only the top N are
# stored as rows (the rest are reachable via the CLI's --all flag if added).
_MAX_FINDINGS = 250


def _severity(score: int) -> str:
    if score >= 70:
        return SEV_HIGH
    if score >= 40:
        return SEV_MEDIUM
    return SEV_LOW


def _category(signals: Dict[str, Any]) -> str:
    """Pick the primary category from the strongest signal."""
    if signals.get("zero_rating"):
        return CAT_ZERO_RATED
    if signals.get("cdn"):
        return CAT_FRONTABLE
    if signals.get("shared_cert") or signals.get("wildcard"):
        return CAT_SHARED_CERT
    return CAT_CANDIDATE


def _evidence(host: str, score: int, signals: Dict[str, Any]) -> str:
    """Compact, parseable evidence line. Format: ``ip=X cdn=Y sig=…``.

    The full signal detail lives in the structured ``signals`` dict at hunt
    time; the evidence string is a compact summary for the table + a fallback
    for `--json`. Kept short so the CLI/TUI table can show real columns
    (HOST / IP / CDN / TYPE) instead of a wall of prose.
    """
    import json
    summary = {
        "score": score,
        "ip": (signals.get("ips") or [""])[0] or "",
        "cdn": signals.get("cdn") or "",
        "captured": signals.get("captured") or 0,
        "zero_rating": signals.get("zero_rating") or [],
        "wildcard": bool(signals.get("wildcard")),
        "shared_cert": signals.get("shared_cert") or 0,
        "reverse_siblings": signals.get("reverse_siblings") or 0,
        "reverse_sourced": bool(signals.get("reverse_sourced")),
        "probe_ok": bool(signals.get("probe_ok")),
        "http_status": signals.get("http_status"),
    }
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))


def parse_evidence(evidence: str) -> Dict[str, Any]:
    """Parse an SNI finding's evidence back into a structured dict.

    The evidence is stored as compact JSON (see ``_evidence``). Returns an
    empty dict on any parse failure — callers default gracefully."""
    import json
    if not evidence:
        return {}
    try:
        data = json.loads(evidence)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def run_hunt(catalog: Catalog, target: Optional[str] = None, *,
             net: bool = True, probe: bool = True,
             http_get: Optional[HttpGet] = None,
             max_domains: int = 25,
             progress=None) -> Dict[str, Any]:
    """Run the full SNI hunt over ``catalog`` and persist findings.

    Parameters
    ----------
    catalog : Catalog
        The captured catalog. ``sni_bug_host`` findings are cleared and
        re-written (idempotent).
    target : str, optional
        The primary capture host. Used only as a party hint; the hunt runs
        over every host the capture touched.
    net : bool
        If False, ALL network hunters are skipped — the stage still runs
        the local heuristics (extract + embedded CDN ranges + zero-rating
        patterns over the captured surface). Online path is the default.
    probe : bool
        If True (the DEFAULT), the active SNI probe runs — one TLS handshake
        + HTTP GET per top candidate, recording the cert CN/SAN + the HTTP
        status code. This is what a browser does on every page load (no port
        scanning, no exploitation). Opt OUT with ``--no-probe`` for a faster,
        read-only recon pass (no HTTP status codes).
    http_get : callable, optional
        Swappable network fetch (tests inject a fake). Defaults to the real
        ``urllib`` fetcher.
    max_domains : int
        Cap on the number of registrable domains to enumerate via CT logs
        (each CT query is one network round-trip; 25 domains is a sane bound).
    progress : callable, optional
        ``progress(message: str)`` called at each phase / per-item so the
        CLI can show live activity (a hunt makes N network calls and looks
        frozen without it). Default None = silent (library / test use).
    """
    def _prog(msg: str) -> None:
        if progress is not None:
            try:
                progress(msg)
            except Exception:
                pass  # progress reporting must never break the hunt

    hosts = extract_mod.extract_hosts(catalog)
    # Build the candidate set: every captured hostname, PLUS the subdomains
    # CT logs surface for their registrable domains (the "find NEW hosts"
    # path the user asked for — not just what the capture happened to hit).
    candidates: Dict[str, Dict[str, Any]] = {}
    cache: Dict[str, List[str]] = {}

    # Seed with captured hosts (these get the "captured" signal bonus).
    captured_by_reg: Dict[str, List[str]] = {}
    for info in hosts:
        candidates[info.host] = {
            "host": info.host,
            "captured": len(info.flow_ids),
            "captured_ips": set(info.captured_ips),
            "registrable": info.registrable,
            "ips": list(info.captured_ips),
        }
        captured_by_reg.setdefault(info.registrable, []).append(info.host)

    # CT-log enumeration: for each registrable domain seen in the capture
    # (capped), pull every subdomain that has ever held a cert. These are
    # the NEW candidate hosts the user wants discovered.
    ct_results: Dict[str, Set[str]] = {}
    if net:
        # Sort domains by how many captured hosts sit under them (most
        # relevant first), then cap.
        regs = sorted(captured_by_reg.keys(),
                      key=lambda d: -len(captured_by_reg[d]))[:max_domains]
        _prog(f"CT logs: enumerating {len(regs)} registrable domain(s)…")
        for i, reg in enumerate(regs, 1):
            _prog(f"  [{i}/{len(regs)}] crt.sh/certspotter ← {reg}")
            subs = ct_mod.subdomains(reg, http_get=http_get)
            ct_results[reg] = subs
            new_here = 0
            for sub in subs:
                if sub not in candidates:
                    new_here += 1
                    candidates[sub] = {
                        "host": sub, "captured": 0, "captured_ips": set(),
                        "registrable": reg, "ips": [],
                    }
            # Surface the NEW subdomains CT found (not just the total) —
            # these are the "find a NEW host" results the user asked for.
            if new_here:
                preview = ", ".join(sorted(subs)[:3]) + ("…" if len(subs) > 3 else "")
                _prog(f"    → +{new_here} new subdomain(s) under {reg}: {preview}")
        _prog(f"CT logs: {sum(len(s) for s in ct_results.values())} subdomains found")

    # --- DISCOVERY PHASE: resolve IPs + reverse-IP for every candidate, so
    # siblings are in the candidate set BEFORE scoring. One level deep; no
    # recursion (siblings-of-siblings aren't chased). ---
    if net:
        to_resolve = list(candidates.values())
        _prog(f"DNS: resolving {len(to_resolve)} host(s) via DoH…")
        for i, cand in enumerate(to_resolve, 1):
            if i % 10 == 1 or i == len(to_resolve):  # throttle: every 10th + last
                _prog(f"  [{i}/{len(to_resolve)}] resolve {cand['host']}")
            ips = dns_mod.resolve(cand["host"], http_get=http_get, cache=cache)
            if ips:
                cand["ips"] = ips
                cand["captured_ips"].update(ips)
            elif cand["ips"]:
                pass  # keep captured IPs
        # Reverse-IP on each candidate's first IP; promote siblings.
        from glyph.catalog.normalize import registrable_domain
        rip_targets = [c for c in list(candidates.values()) if c.get("ips")]
        _prog(f"reverse-IP: looking up siblings for {len(rip_targets)} host(s)…")
        rip_discovered = 0  # running total of NEW hosts found via reverse-IP
        rip_empty = 0       # calls that returned 0 siblings (rate-limit signal)
        for i, cand in enumerate(rip_targets, 1):
            if i % 10 == 1 or i == len(rip_targets):
                _prog(f"  [{i}/{len(rip_targets)}] reverse-IP {cand['host']}"
                      + (f"  (+{rip_discovered} new so far)" if rip_discovered else ""))
            ips = cand.get("ips") or []
            if not ips:
                continue
            for ip in ips[:1]:
                sibs = rip_mod.reverse_ip(ip, http_get=http_get)
                if not sibs:
                    rip_empty += 1
                new_sibs = [s for s in sibs if s != cand["host"]
                            and s not in candidates]
                if new_sibs:
                    cand.setdefault("reverse_siblings", []).extend(new_sibs[:20])
                    kept = new_sibs[:20]
                    for sib in kept:
                        candidates[sib] = {
                            "host": sib, "captured": 0,
                            "captured_ips": set(ips),
                            "registrable": registrable_domain(sib),
                            "ips": list(ips),
                            "reverse_sourced": True,
                        }
                    rip_discovered += len(kept)
                    # Show the discovery AS it happens — the names, not just
                    # the count, so the user can spot interesting siblings.
                    preview = ", ".join(kept[:3]) + ("…" if len(kept) > 3 else "")
                    _prog(f"    → +{len(kept)} new via {cand['host']}: {preview}")
                    break
        if rip_discovered:
            _prog(f"reverse-IP: +{rip_discovered} new host(s) discovered "
                  f"({len(candidates)} total candidates)")
        # Heuristic: if MOST reverse-IP calls came back empty, the free
        # HackerTarget API likely rate-limited (HTTP 200 + "API count
        # exceeded" body — undetectable per-call). Surface it so the user
        # knows the 0-siblings result is suspect, not definitive.
        if len(rip_targets) >= 5 and rip_empty >= len(rip_targets) * 0.8:
            _prog("reverse-IP: WARNING — most lookups returned empty; the free "
                  "HackerTarget API may be rate-limited (try again later, or "
                  "set a different reverse-IP source)")

    # --- SCORING PHASE: score every candidate (snapshot — no mutation now). ---
    _prog(f"scoring {len(candidates)} candidate(s)…")
    scored: List[Dict[str, Any]] = []
    for cand in list(candidates.values()):
        host = cand["host"]
        signals: Dict[str, Any] = {}
        score = 0

        if cand["captured"]:
            score += 10
            signals["captured"] = cand["captured"]

        ips: List[str] = list(cand.get("ips") or cand["captured_ips"])

        # CDN detection.
        cdn = cdn_mod.detect(host, ips)
        if cdn:
            score += 30
            signals["cdn"] = cdn.name

        # Zero-rating heuristics.
        zr = zr_mod.zero_rate_signals(host)
        if zr:
            score += 30
            signals["zero_rating"] = zr

        # CT-log signals (shared cert / wildcard).
        reg = cand["registrable"]
        if reg in ct_results:
            subs = ct_results[reg]
            if ct_mod.has_wildcard(subs, reg):
                score += 10
                signals["wildcard"] = True
            # "Shared cert" proxy: many subdomains under one registrable
            # domain means certs there tend to cover many names.
            if len(subs) >= 5:
                score += 15
                signals["shared_cert"] = len(subs)

        # Reverse-IP signal (siblings were discovered in the discovery phase).
        if cand.get("reverse_siblings"):
            score += 10
            signals["reverse_siblings"] = len(cand["reverse_siblings"])
        elif cand.get("reverse_sourced"):
            # This candidate WAS a reverse-IP discovery — it shares an IP
            # with a captured host, which is a fronting signal.
            score += 10
            signals["reverse_sourced"] = True

        score = min(score, 100)
        signals["ips"] = ips[:3]

        # Active probe (default ON; opt out with --no-probe). Does a TLS
        # handshake + HTTP GET to capture the cert CN/SAN AND the HTTP status
        # code. Only fires for candidates scoring >= 40 (keeps the probe
        # budget tiny) AND requires net=True (the probe needs a reachable IP;
        # --no-net means no network, so no probe).
        if probe and net and score >= 40:
            res = probe_mod.probe_sni(host, ip=ips[0] if ips else None)
            if res.ok:
                score += 10
                score = min(score, 100)
                signals["probe_ok"] = True
                if res.sans:
                    signals["probe_sans"] = len(res.sans)
                    signals["probe_subject"] = res.subject
                if res.http_status is not None:
                    signals["http_status"] = res.http_status
            else:
                signals["probe_error"] = res.error

        cand["score"] = score
        cand["signals"] = signals
        cand["category"] = _category(signals)
        scored.append(cand)

    # Persist the top N as findings (sorted by score desc, then host).
    scored.sort(key=lambda c: (-c["score"], c["host"]))
    catalog.clear_findings(kind=FINDING_SNI_BUG_HOST)
    persisted = 0
    for cand in scored[:_MAX_FINDINGS]:
        if cand["score"] < 1:
            break  # don't persist zero-score noise
        catalog.add_finding(Finding(
            kind=FINDING_SNI_BUG_HOST,
            category=cand["category"],
            severity=_severity(cand["score"]),
            location="sni",
            evidence=_evidence(cand["host"], cand["score"], cand["signals"]),
            endpoint_id=None,
            value_sample=cand["host"],
            party=None,
            host=cand["host"],
            score=cand["score"],
        ))
        persisted += 1

    return summarize(catalog, discovered=len(scored), persisted=persisted)


def is_noise(finding: Finding) -> bool:
    """SNI bug-host findings are never noise — they are the point of the
    stage (mirrors ADR-4's stance on sensitive-data findings)."""
    return False


def summarize(catalog: Catalog, discovered: Optional[int] = None,
              persisted: Optional[int] = None) -> Dict[str, Any]:
    """Return a summary of the SNI hunt findings in ``catalog``."""
    findings = catalog.findings(kind=FINDING_SNI_BUG_HOST)
    by_sev: Dict[str, int] = {}
    by_cat: Dict[str, int] = {}
    by_cdn: Dict[str, int] = {}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
        # CDN name is now structured JSON in evidence (parse_evidence); no
        # more fragile string-split on "-fronted".
        ev = parse_evidence(f.evidence or "")
        cdn = ev.get("cdn")
        if cdn:
            by_cdn[cdn] = by_cdn.get(cdn, 0) + 1

    def sevmap(src):
        return {s: src[s] for s in ("critical", "high", "medium", "low")
                if src.get(s)}

    out = {
        "total": len(findings),
        "discovered": discovered if discovered is not None else len(findings),
        "persisted": persisted if persisted is not None else len(findings),
        "target": catalog.target(),
        "by_severity": sevmap(by_sev),
        "by_category": by_cat,
        "by_cdn": by_cdn,
    }
    return out
