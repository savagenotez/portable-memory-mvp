"""A deliberately small, polite HTTP client: GET only, https only, an allowlist of documented public hosts."""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

ALLOWED_HOSTS = {
    "api.elections.kalshi.com",   # Kalshi official API, public market data
    "gamma-api.polymarket.com",   # Polymarket Gamma API, market discovery
    "clob.polymarket.com",        # Polymarket CLOB API, public prices
    "raw.githubusercontent.com",  # nflverse open game data (approved 2026-11-24), read-only raw files
}

# Approved 2026-11-24: nflverse release assets, and nothing else on GitHub. A release-download URL may be
# redirected only to the release-asset host below. Any other GitHub path, or any other redirect, is refused.
RELEASE_PREFIX = "/nflverse/nflverse-data/releases/download/"
RELEASE_HOST = "github.com"
RELEASE_REDIRECT_HOST = "release-assets.githubusercontent.com"


def check_release_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != RELEASE_HOST:
        raise ValueError("not a GitHub release URL")
    if not parsed.path.startswith(RELEASE_PREFIX):
        raise ValueError(f"only nflverse release downloads are allowed, not {parsed.path!r}")


class _ReleaseRedirects(urllib.request.HTTPRedirectHandler):
    """Follow only the one redirect a GitHub release download makes, and only to the release-asset host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlparse(newurl)
        if target.scheme != "https" or target.hostname != RELEASE_REDIRECT_HOST:
            raise urllib.error.URLError(f"redirect to {target.hostname!r} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_release_opener = urllib.request.build_opener(_ReleaseRedirects)


def get_release_text(url: str, *, timeout: float = 120.0, retries: int = 3) -> str:
    """GET an nflverse release asset (a CSV). Same retry rules; only the approved release path is reachable."""
    check_release_url(url)
    delay = 1.0
    for attempt in range(retries + 1):
        wait = 0.5 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"})
        try:
            with _release_opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, http.client.HTTPException):
            if attempt < retries:
                time.sleep(delay)
                delay = min(30.0, delay * 2)
                continue
            raise
USER_AGENT = "prediction-markets-research-client"
_last_call = [0.0]


def _pause_for_budget(headers) -> None:
    """If the server says the request budget is nearly spent, wait for it to reset before the next call."""
    try:
        remaining = float(headers.get("x-ratelimit-remaining"))
        cost = float(headers.get("x-ratelimit-cost", 1))
        reset = float(headers.get("x-ratelimit-reset", 0))
    except (TypeError, ValueError):
        return
    if remaining < 3 * cost:
        time.sleep(min(30.0, reset + 0.5))


def get_text(url: str, *, min_interval: float = 0.5, timeout: float = 60.0, retries: int = 3) -> str:
    """GET a public text file (for example a CSV). Same allowlist, https-only and retry rules as get_json."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("only https URLs on the allowlist are allowed")
    delay = 1.0
    for attempt in range(retries + 1):
        wait = min_interval - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv,text/plain"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, http.client.HTTPException):
            if attempt < retries:
                time.sleep(delay)
                delay = min(30.0, delay * 2)
                continue
            raise


def get_json(url: str, params: Optional[dict] = None, *, min_interval: float = 1.0,
             timeout: float = 25.0, retries: int = 6):
    """GET a documented public endpoint. Honours the server's rate-limit headers and never retries blindly."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("only https URLs are allowed")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"host {parsed.hostname!r} is not on the allowlist of documented public hosts")
    if params:
        url = url + ("&" if parsed.query else "?") + urllib.parse.urlencode(params)
    delay = 1.0
    for attempt in range(retries + 1):
        wait = min_interval - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _pause_for_budget(resp.headers)
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                try:
                    reset = float(e.headers.get("x-ratelimit-reset", e.headers.get("retry-after", delay)))
                except (TypeError, ValueError):
                    reset = delay
                time.sleep(min(60.0, reset + 0.5))
                delay = min(30.0, delay * 2)
                continue
            if e.code in (500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay = min(30.0, delay * 2)
                continue
            raise
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            # a dropped or reset connection, a timeout, or a malformed reply: wait and retry a few times
            if attempt < retries:
                time.sleep(delay)
                delay = min(30.0, delay * 2)
                continue
            raise
