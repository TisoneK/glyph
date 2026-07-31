"""First-party vs third-party host classification.

A live capture pulls in analytics, ads, and CDN hosts alongside the target.
Flagging their CORS/headers as the *target's* risk is misleading, so every
finding is tagged relative to the capture's primary host: same registrable
domain = first-party, otherwise third-party.

Registrable domain = eTLD+1. Without bundling a full Public Suffix List we
keep a compact set of common multi-label suffixes (incl. East-African ones,
Kenya-priority) so `x.betika.com` and `betika.com` match and `foo.co.ke`
resolves to `foo.co.ke`, not `co.ke`.
"""
from __future__ import annotations

from typing import Optional

# registrable_domain lives in catalog.normalize (shared with rosetta, which
# scopes reference-joins to a domain) — re-exported here for convenience.
from glyph.catalog.normalize import registrable_domain

PARTY_FIRST = "first_party"
PARTY_THIRD = "third_party"
PARTY_UNKNOWN = "unknown"

# Known analytics / advertising / tracking / session-replay vendors. These
# are pure infrastructure noise — a target's own data never lives here, so
# their CORS/header hygiene is not the target's concern. This is DELIBERATELY
# NOT a CDN/storage list: a target's data DOES live on CDNs and object stores
# (S3, googleapis storage, Cloudinary, Firebase, CloudFront), so those are
# never treated as noise — findings on them are surfaced like any other.
_TRACKING_VENDORS = {
    "google-analytics.com", "googletagmanager.com", "googlesyndication.com",
    "googletagservices.com", "googleadservices.com", "doubleclick.net",
    "adnxs.com", "adsrvr.org", "rubiconproject.com", "pubmatic.com",
    "criteo.com", "criteo.net", "taboola.com", "outbrain.com", "adform.net",
    "facebook.com", "facebook.net", "hotjar.com", "mixpanel.com",
    "segment.com", "segment.io", "amplitude.com", "fullstory.com",
    "clarity.ms", "mouseflow.com", "crazyegg.com", "quantserve.com",
    "scorecardresearch.com", "newrelic.com", "nr-data.net", "sentry.io",
    "bugsnag.com", "optimizely.com", "branch.io", "appsflyer.com",
    "adjust.com", "onesignal.com", "cookiebot.com", "onetrust.com",
    "yandex.ru", "bat.bing.com", "snowplowanalytics.com", "chartbeat.com",
}


def is_tracking_vendor(host: Optional[str]) -> bool:
    """True if the host is a known analytics/ads/tracking vendor (noise).

    CDNs and object stores are intentionally excluded — a target's own data
    lives on those, so they are never treated as noise.
    """
    host = (host or "").split(":")[0].strip(".").lower()
    if not host:
        return False
    if registrable_domain(host) in _TRACKING_VENDORS:
        return True
    return any(host == v or host.endswith("." + v) for v in _TRACKING_VENDORS)


def classify(host: Optional[str], target: Optional[str]) -> str:
    """Classify ``host`` relative to the capture's primary ``target`` host."""
    if not target:
        return PARTY_UNKNOWN
    rd_host = registrable_domain(host)
    rd_target = registrable_domain(target)
    if not rd_host or not rd_target:
        return PARTY_UNKNOWN
    return PARTY_FIRST if rd_host == rd_target else PARTY_THIRD
