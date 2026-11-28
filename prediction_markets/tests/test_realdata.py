import json
import os
import random
import tempfile
import unittest

from prediction_markets.realdata import calibration, http, kalshi, polymarket
from prediction_markets.realdata.observation import Observation, clip_price, read_csv, write_csv

CLOSE = "2026-11-24T03:00:00Z"
CLOSE_TS = 1795489200.0  # 2026-11-24T03:00:00Z


def candle(ts, bid, ask):
    return {"end_period_ts": ts, "yes_bid": {"close_dollars": bid}, "yes_ask": {"close_dollars": ask},
            "price": {}, "volume_fp": "10.00"}


def kalshi_market(ticker, event, result="yes", **extra):
    m = {"ticker": ticker, "event_ticker": event, "title": "X wins", "market_type": "binary",
         "result": result, "close_time": CLOSE, "mve_collection_ticker": None, "volume_fp": "100.00"}
    m.update(extra)
    return m


class HostGuardTests(unittest.TestCase):
    def test_rejects_hosts_that_are_not_on_the_allowlist(self):
        with self.assertRaises(ValueError):
            http.get_json("https://example.com/markets")
        with self.assertRaises(ValueError):
            http.get_json("https://api.kalshi.com.evil.test/markets")

    def test_rejects_plain_http(self):
        with self.assertRaises(ValueError):
            http.get_json("http://api.elections.kalshi.com/trade-api/v2/markets")

    def test_allowlist_is_the_documented_hosts_only(self):
        self.assertEqual(http.ALLOWED_HOSTS, {"api.elections.kalshi.com", "gamma-api.polymarket.com",
                                               "clob.polymarket.com", "raw.githubusercontent.com"})

    def test_github_is_reachable_only_for_nflverse_release_assets(self):
        http.check_release_url("https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2025.csv")
        for bad in ("https://github.com/someone/else/releases/download/x/y.csv",
                    "https://github.com/nflverse/nflverse-data/tree/main/data",
                    "https://api.github.com/repos/nflverse/nflverse-data"):
            with self.assertRaises(ValueError):
                http.check_release_url(bad)

    def test_redirects_are_followed_only_to_the_release_asset_host(self):
        import urllib.request
        handler = http._ReleaseRedirects()
        req = urllib.request.Request("https://github.com/nflverse/nflverse-data/releases/download/x/y.csv")
        ok = handler.redirect_request(req, None, 302, "Found", {}, "https://release-assets.githubusercontent.com/a")
        self.assertIsNotNone(ok)
        with self.assertRaises(urllib.error.URLError):
            handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.com/a")

    def test_text_fetch_is_guarded_too(self):
        with self.assertRaises(ValueError):
            http.get_text("https://example.com/file.csv")
        with self.assertRaises(ValueError):
            http.get_text("http://raw.githubusercontent.com/x.csv")


class RateLimitTests(unittest.TestCase):
    URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

    class _Resp:
        def __init__(self, body, headers=None):
            self._b = json.dumps(body).encode()
            self.headers = headers or {}
        def read(self, *a):
            return self._b
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def _http_error(self, code, headers):
        import io
        import urllib.error
        return urllib.error.HTTPError(self.URL, code, "x", headers, io.BytesIO(b"{}"))

    def test_waits_for_the_reset_time_on_429_then_succeeds(self):
        from unittest import mock
        seq = [self._http_error(429, {"x-ratelimit-reset": "2.0"}), self._Resp({"ok": 1})]
        sleeps = []
        def fake_open(req, timeout=0):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch("urllib.request.urlopen", fake_open), mock.patch("time.sleep", sleeps.append):
            self.assertEqual(http.get_json(self.URL, min_interval=0.0), {"ok": 1})
        self.assertTrue(any(s >= 2.5 for s in sleeps))

    def test_pauses_when_the_remaining_budget_is_low(self):
        from unittest import mock
        sleeps = []
        low = self._Resp({"ok": 1}, {"x-ratelimit-remaining": "40", "x-ratelimit-cost": "50", "x-ratelimit-reset": "3"})
        with mock.patch("urllib.request.urlopen", lambda req, timeout=0: low), mock.patch("time.sleep", sleeps.append):
            http.get_json(self.URL, min_interval=0.0)
        self.assertTrue(any(s >= 3.5 for s in sleeps))

    def test_retries_a_dropped_connection(self):
        import http.client as httpclient
        from unittest import mock
        seq = [httpclient.RemoteDisconnected("Remote end closed connection without response"),
               ConnectionResetError("reset"), self._Resp({"ok": 1})]
        def fake_open(req, timeout=0):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch("urllib.request.urlopen", fake_open), mock.patch("time.sleep", lambda s: None):
            self.assertEqual(http.get_json(self.URL, min_interval=0.0), {"ok": 1})

    def test_gives_up_after_the_retry_limit(self):
        import urllib.error
        from unittest import mock
        def always_429(req, timeout=0):
            raise self._http_error(429, {"x-ratelimit-reset": "0.1"})
        with mock.patch("urllib.request.urlopen", always_429), mock.patch("time.sleep", lambda s: None):
            with self.assertRaises(urllib.error.HTTPError):
                http.get_json(self.URL, min_interval=0.0, retries=2)

    def test_a_missing_history_is_skipped_but_a_rate_limit_is_not_swallowed(self):
        import urllib.error
        target = CLOSE_TS - 24 * 3600
        markets = [kalshi_market("G1-A", "G1", "yes"), kalshi_market("G2-A", "G2", "no")]
        def missing(url, params=None):
            if url.endswith("/markets"):
                return {"markets": markets, "cursor": ""}
            raise self._http_error(404, {})
        self.assertEqual(kalshi.collect(("S",), per_series=5, horizon_hours=24, fetch=missing), [])
        def limited(url, params=None):
            if url.endswith("/markets"):
                return {"markets": markets, "cursor": ""}
            raise self._http_error(429, {})
        with self.assertRaises(urllib.error.HTTPError):
            kalshi.collect(("S",), per_series=5, horizon_hours=24, fetch=limited)


class KalshiTests(unittest.TestCase):
    def test_usable_filter_drops_combos_and_unresolved(self):
        self.assertTrue(kalshi.is_usable(kalshi_market("A", "E")))
        self.assertFalse(kalshi.is_usable(kalshi_market("A", "E", mve_collection_ticker="KXMVE")))
        self.assertFalse(kalshi.is_usable(kalshi_market("A", "E", result="")))
        self.assertFalse(kalshi.is_usable(kalshi_market("A", "E", market_type="scalar")))

    def test_settled_markets_follows_the_cursor(self):
        pages = [{"markets": [{"ticker": f"A{i}"} for i in range(3)], "cursor": "c1"},
                 {"markets": [{"ticker": f"B{i}"} for i in range(3)], "cursor": ""}]
        calls = []
        def fake(url, params=None):
            calls.append(dict(params))
            return pages[len(calls) - 1]
        out = kalshi.settled_markets("KXNBAGAME", 10, fake)
        self.assertEqual([m["ticker"] for m in out], ["A0", "A1", "A2", "B0", "B1", "B2"])
        self.assertEqual(calls[1].get("cursor"), "c1")
        self.assertEqual(calls[0]["status"], "settled")

    def test_price_is_the_midpoint_of_the_last_candle_before_the_target(self):
        target = CLOSE_TS - 24 * 3600
        candles = [candle(target - 7200, "0.30", "0.34"), candle(target - 3600, "0.40", "0.44"),
                   candle(target + 3600, "0.90", "0.94")]   # after the target: must be ignored
        fake = lambda url, params=None: {"candlesticks": candles}
        mid, spread = kalshi.price_before_close("S", kalshi_market("T", "E"), 24, 0.10, fake)
        self.assertAlmostEqual(mid, 0.42)
        self.assertAlmostEqual(spread, 0.04)

    def test_wide_stale_or_missing_quotes_are_skipped(self):
        target = CLOSE_TS - 24 * 3600
        m = kalshi_market("T", "E")
        wide = lambda url, params=None: {"candlesticks": [candle(target - 600, "0.10", "0.80")]}
        stale = lambda url, params=None: {"candlesticks": [candle(target - 10 * 3600, "0.40", "0.44")]}
        none = lambda url, params=None: {"candlesticks": []}
        no_bid = lambda url, params=None: {"candlesticks": [{"end_period_ts": target - 600, "yes_bid": {}, "yes_ask": {}}]}
        for fake in (wide, stale, none, no_bid):
            self.assertIsNone(kalshi.price_before_close("S", m, 24, 0.10, fake))

    def test_collect_takes_one_market_per_event_and_maps_the_result(self):
        target = CLOSE_TS - 24 * 3600
        markets = [kalshi_market("G1-A", "G1", "yes"), kalshi_market("G1-B", "G1", "no"),
                   kalshi_market("G2-A", "G2", "no"),
                   kalshi_market("C1", "C", "yes", mve_collection_ticker="KXMVE")]
        def fake(url, params=None):
            if url.endswith("/markets"):
                return {"markets": markets, "cursor": ""}
            return {"candlesticks": [candle(target - 300, "0.60", "0.64")]}
        obs = kalshi.collect(("S",), per_series=10, horizon_hours=24, fetch=fake)
        self.assertEqual([o.event_id for o in obs], ["G1", "G2"])
        self.assertEqual([o.outcome for o in obs], [1, 0])
        self.assertTrue(all(abs(o.price - 0.62) < 1e-9 for o in obs))
        self.assertTrue(all(o.source == "kalshi" for o in obs))


def poly_market(prices, outcomes=("Yes", "No"), end="2026-11-24T03:00:00Z", **extra):
    m = {"id": "1", "conditionId": "0xabc", "question": "Will it happen?",
         "outcomes": json.dumps(list(outcomes)), "outcomePrices": json.dumps(prices),
         "clobTokenIds": json.dumps(["tokYES", "tokNO"]), "endDate": end, "volumeNum": 50000.0,
         "events": [{"id": "77"}]}
    m.update(extra)
    return m


class PolymarketTests(unittest.TestCase):
    def test_clean_two_outcome_resolution_is_detected(self):
        self.assertEqual(polymarket.resolved_first_outcome(poly_market(["1", "0"])), 1)
        self.assertEqual(polymarket.resolved_first_outcome(poly_market(["0", "1"])), 0)
        self.assertEqual(polymarket.resolved_first_outcome(poly_market(["1", "0"], outcomes=("Team A", "Team B"))), 1)

    def test_unclean_or_multi_outcome_markets_are_rejected(self):
        self.assertIsNone(polymarket.resolved_first_outcome(poly_market(["0", "0"])))        # voided or unresolved
        self.assertIsNone(polymarket.resolved_first_outcome(poly_market(["0.5", "0.5"])))
        three = poly_market(["1", "0", "0"], outcomes=("A", "B", "C"))
        self.assertIsNone(polymarket.resolved_first_outcome(three))
        self.assertIsNone(polymarket.resolved_first_outcome({"outcomes": None}))

    def test_price_is_the_last_point_at_or_before_the_target(self):
        target = CLOSE_TS - 24 * 3600
        hist = {"history": [{"t": target - 7200, "p": 0.30}, {"t": target - 1800, "p": 0.35}, {"t": target + 600, "p": 0.99}]}
        seen = {}
        def fake(url, params=None):
            seen.update(params)
            return hist
        p = polymarket.price_before_close(poly_market(["1", "0"]), 24, fake)
        self.assertAlmostEqual(p, 0.35)
        self.assertEqual(seen["market"], "tokYES")   # the first outcome's token

    def test_stale_or_empty_history_is_skipped(self):
        target = CLOSE_TS - 24 * 3600
        stale = lambda url, params=None: {"history": [{"t": target - 12 * 3600, "p": 0.4}]}
        empty = lambda url, params=None: {"history": []}
        self.assertIsNone(polymarket.price_before_close(poly_market(["1", "0"]), 24, stale))
        self.assertIsNone(polymarket.price_before_close(poly_market(["1", "0"]), 24, empty))

    def test_collect_keeps_only_clean_markets_with_a_price(self):
        target = CLOSE_TS - 24 * 3600
        markets = [poly_market(["1", "0"]), poly_market(["0", "0"]), poly_market(["0", "1"], conditionId="0xdef")]
        def fake(url, params=None):
            if url.endswith("/markets"):
                return markets if params["offset"] == 0 else []
            return {"history": [{"t": target - 60, "p": 0.55}]}
        obs = polymarket.collect(limit=5, min_volume=1000, horizon_hours=24, fetch=fake)
        self.assertEqual([o.outcome for o in obs], [1, 0])
        self.assertTrue(all(o.source == "polymarket" and o.event_id == "77" for o in obs))


def synthetic(n, seed, noise=0.0, shrink=1.0):
    """Prices drawn uniformly; outcomes drawn at the true probability. shrink < 1 makes prices too extreme."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        true_p = rng.uniform(0.05, 0.95)
        price = clip_price(0.5 + (true_p - 0.5) / shrink + rng.gauss(0.0, noise))
        out.append(Observation("kalshi", f"m{i}", f"e{i}", "t", 0.0, 24.0, price, 1 if rng.random() < true_p else 0))
    return out


class StreamingTests(unittest.TestCase):
    def test_iter_collect_yields_progress_before_a_failure(self):
        target = CLOSE_TS - 24 * 3600
        markets = [kalshi_market("G1-A", "G1", "yes"), kalshi_market("G2-A", "G2", "no")]
        state = {"n": 0}
        def fake(url, params=None):
            if url.endswith("/markets"):
                return {"markets": markets, "cursor": ""}
            state["n"] += 1
            if state["n"] == 2:
                raise ConnectionResetError("boom")
            return {"candlesticks": [candle(target - 300, "0.60", "0.64")]}
        got = []
        with self.assertRaises(ConnectionResetError):
            for o in kalshi.iter_collect(("S",), per_series=5, horizon_hours=24, fetch=fake):
                got.append(o)
        self.assertEqual([o.event_id for o in got], ["G1"])   # the first event survived the failure

    def test_collect_and_iter_collect_agree(self):
        target = CLOSE_TS - 24 * 3600
        markets = [kalshi_market("G1-A", "G1", "yes")]
        fake = lambda url, params=None: ({"markets": markets, "cursor": ""} if url.endswith("/markets")
                                         else {"candlesticks": [candle(target - 300, "0.60", "0.64")]})
        self.assertEqual(kalshi.collect(("S",), 5, 24, fetch=fake), list(kalshi.iter_collect(("S",), 5, 24, fetch=fake)))


class CalibrationTests(unittest.TestCase):
    def test_well_calibrated_prices_have_slope_near_one(self):
        fit = calibration.fit_calibration(synthetic(6000, 1))
        self.assertLess(abs(fit["slope"] - 1.0), 2.5 * fit["slope_se"])
        self.assertLess(abs(fit["intercept"]), 2.5 * fit["intercept_se"])

    def test_overconfident_prices_have_slope_below_one(self):
        fit = calibration.fit_calibration(synthetic(6000, 2, shrink=0.6))
        self.assertLess(fit["slope"], 1.0 - 3 * fit["slope_se"])

    def test_reliability_bins_partition_the_data(self):
        obs = synthetic(2000, 3)
        table = calibration.reliability_table(obs)
        self.assertEqual(sum(r["n"] for r in table), len(obs))
        for r in table:
            self.assertTrue(r["ci_low"] <= r["realized"] <= r["ci_high"])

    def test_report_structure_and_text(self):
        obs = synthetic(500, 4) + [Observation("polymarket", f"p{i}", f"pe{i}", "t", 0.0, 24.0, 0.3 + 0.001 * i, i % 2)
                                   for i in range(300)]
        rep = calibration.report(obs)
        self.assertEqual(set(rep["by_source"]), {"kalshi", "polymarket"})
        self.assertEqual(rep["overall"]["n"], 800)
        text = calibration.format_report(rep)
        self.assertIn("ALL SOURCES", text)
        self.assertIn("calibration slope", text)

    def test_skill_is_positive_for_informative_prices_and_zero_for_flat_ones(self):
        informative = calibration.summarize(synthetic(4000, 5))
        flat = calibration.summarize([Observation("kalshi", f"m{i}", f"e{i}", "t", 0.0, 24.0, 0.5, i % 2) for i in range(400)])
        self.assertGreater(informative["skill_vs_base_rate"], 0.05)
        self.assertAlmostEqual(flat["skill_vs_base_rate"], 0.0, places=6)

    def test_too_few_observations_are_reported_as_such(self):
        self.assertEqual(calibration.summarize(synthetic(3, 6)), {"n": 3})


class ObservationTests(unittest.TestCase):
    def test_csv_round_trip(self):
        obs = [Observation("kalshi", "m1", "e1", "A, wins", 1.5e9, 24.0, 0.42, 1, 0.04, 100.0),
               Observation("polymarket", "m2", "e2", "B", 1.6e9, 24.0, 0.7, 0, None, None)]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.csv")
            write_csv(path, obs)
            back = read_csv(path)
        self.assertEqual(back, obs)

    def test_clip_price_bounds(self):
        self.assertEqual(clip_price(0.0), 0.01)
        self.assertEqual(clip_price(1.0), 0.99)
        self.assertEqual(clip_price(0.4), 0.4)


if __name__ == "__main__":
    unittest.main()
