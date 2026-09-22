# ADR-15 parallel pipeline — wall-clock profile (Session 25, 2026-08-01)

**Target:** quantify the ADR-15 wall-clock speedup by profiling `glyph run har`
before/after on a larger HAR (expected: max instead of sum). **No product code
changed** — the benchmarks are throwaway scripts in `/tmp`.

## Method

- **Before** = the old `_gather` order (removed in `cabce93`), reconstructed
  from the stage APIs: `infer_all → build_dictionary → run_scan → run_hunt` on
  ONE catalog connection. **After** = `run_analysis()` (3 lanes).
- Same synthetic HAR, same flags on both sides, **fresh SQLite DB per rep**
  (no cache bias), **ingest excluded** from stage timing (identical in both)
  but reported so total `glyph run har` wall clock is reconstructible.
- Median of 3–4 reps; **parity check** on findings counts proves the timing
  comparison is apples-to-apples.

## Results

### 1. Offline (`net=False`) — CPU-bound: **1.00x** (no win, no regression)

| | time |
|---|---|
| sequential (median, 4 reps) | 2.412s |
| parallel (median) | 2.403s |
| **speedup** | **1.00x** |

Per-stage (sequential): schema 1.39s (54%), sensitive 0.93s (36%), rosetta
0.25s, snihunt 0.01s. Schema + sensitive are pure-Python CPU work (JSON
walking, regex, dict building) — the **GIL serializes** them, so threads can't
overlap them. The near-equal totals prove the lanes did NOT overlap offline
(had they, parallel would be ~1.8s, not 2.40s) — direct evidence of GIL
serialization, and that the parallel infra adds ~0 overhead. Parity identical
(696 / 46 / 372 / 12 findings; 476 endpoints / 6680 fields / 560 enum
candidates).

### 2. Real network (`net=True`) — overlap mechanism works, jitter swamps the number

Reps: 0.41x / 1.44x (median 0.85x) — CT-log queries ranged 2–9s each, so a
2–3s CPU win is noise against ±8s of external latency. But the timeline
PROVED the overlap: schema/rosetta/sensitive all finished at ~2.9s while
snihunt's CT→DNS→reverse-IP I/O ran to ~31s.

### 3. Controlled I/O — deterministic sleeps on CT/DNS/reverse-IP, 2.5x HAR: **1.44x**

Patched `ct_mod.subdomains` (1.0s), `dns_mod.resolve` (0.15s),
`rip_mod.reverse_ip` (0.2s) with fixed sleeps; ~700 flows / 22 candidates.

| | time |
|---|---|
| sequential (median, 3 reps) | 17.628s |
| parallel (median) | 12.237s |
| **speedup** | **1.44x** (1.47 / 1.42 / 1.43) |

Per-stage (sequential): schema 2.86s + rosetta 0.73s + sensitive 2.36s
(**~6s CPU sum**), snihunt 11.84s (67%). Timeline: schema+rosetta done at
5.5s, sensitive ~5.5s, snihunt I/O (CT 4s + DNS 3.2s + reverse-IP 4.2s ≈ 12s)
dominates — **the ~6s of CPU work hides entirely under snihunt's I/O**.
Parity identical (1068 / 54 / 574 / 14 findings; sni discovered 22).

## Conclusion

- **ADR-15's speedup is I/O-bound-only.** ~**1.4x** when snihunt runs its
  network recon (its real dominant cost — 66%+ of sequential runtime); ~**1.0x**
  when everything is offline/CPU-bound (GIL), with **zero regression**.
- **Max-instead-of-sum confirmed on the I/O path:** parallel ≈ snihunt-I/O
  (CPU lanes hidden) vs sequential = CPU-sum + snihunt-I/O.
- Caveats (reviewer-flagged, all stated): lane windows are upper bounds
  (progress-message based, end at run end — not presented as proof of
  overlap; the totals comparison is the evidence); rosetta did minimal work
  on the synthetic HAR (`entries: 0` — synthetic HTML labels didn't feed it);
  the offline run uses `net=False` for BOTH sides to isolate stage
  parallelism (the old default was `net=True`).

## Artifacts

- `/tmp/prof_har.py` (offline + real-network variants), `/tmp/prof_io.py`
  (controlled-I/O variant) — throwaway, not committed.
