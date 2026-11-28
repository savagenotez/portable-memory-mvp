import datetime as dt
import unittest

from prediction_markets.nfl import prospective as pro
from prediction_markets.nfl.data import Game


def game(gid, day, home, away, hs=None, as_=None):
    return Game(game_id=gid, season=2026, week=12, gameday=day, home=home, away=away, home_score=hs,
                away_score=as_, rest_home=7, rest_away=7, div_game=0, neutral=False, roof="outdoors")


def snap(market_id, event_id, game_id, side, hours, mid, model=0.6):
    return {"market_id": market_id, "event_id": event_id, "game_id": game_id, "gameday": "2026-12-06",
            "side": side, "hours_to_close": hours, "bid": None, "ask": None, "mid": mid, "model": model,
            "model_version": pro.MODEL_VERSION}


class SnapshotRuleTests(unittest.TestCase):
    def test_choose_takes_the_latest_snapshot_at_least_24_hours_before_close(self):
        rows = [snap("m", "e", "g", "home", 60, 0.5), snap("m", "e", "g", "home", 30, 0.55),
                snap("m", "e", "g", "home", 24.5, 0.58), snap("m", "e", "g", "home", 10, 0.7)]
        self.assertEqual(pro.choose_snapshot(rows)["hours_to_close"], 24.5)

    def test_no_snapshot_before_the_horizon_means_no_score(self):
        self.assertIsNone(pro.choose_snapshot([snap("m", "e", "g", "home", 10, 0.6)]))

    def test_a_wide_book_has_no_midpoint(self):
        m = {"yes_bid_dollars": "0.24", "yes_ask_dollars": "0.62"}
        self.assertIsNone(pro._quote(m)[2])
        self.assertAlmostEqual(pro._quote({"yes_bid_dollars": "0.40", "yes_ask_dollars": "0.44"})[2], 0.42)


class ScoreTests(unittest.TestCase):
    def test_one_market_per_event_and_only_finished_games(self):
        games = [game("g1", "2026-12-06", "SF", "MIN", 30, 20), game("g2", "2026-12-07", "DAL", "SEA")]
        log = [snap("KX-SF", "EV1", "g1", "home", 30, 0.6, model=0.7),
               snap("KX-MIN", "EV1", "g1", "away", 30, 0.4, model=0.3),     # same event, other side: ignored
               snap("KX-DAL", "EV2", "g2", "home", 30, 0.5, model=0.5)]      # game not finished: not scored
        res = pro.score(log, games)
        self.assertEqual(res["scored_games"], 1)
        # one market per event: the first ticker in sorted order is kept (KX-MIN, the away side, which lost)
        self.assertEqual(res["rows"][0]["market_id"], "KX-MIN")
        self.assertEqual(res["rows"][0]["outcome"], 0)

    def test_no_decision_before_the_first_100_games(self):
        games = [game(f"g{i}", "2026-12-06", "SF", "MIN", 30, 20) for i in range(5)]
        log = [snap(f"KX{i}", f"EV{i}", f"g{i}", "home", 30, 0.6, model=0.7) for i in range(5)]
        res = pro.score(log, games)
        self.assertEqual(res["scored_games"], 5)
        self.assertIn("not yet", res["decision"])

    def test_empty_log_reports_status(self):
        self.assertEqual(pro.score([], [])["status"], "no scored games yet")

    def test_snapshot_rows_match_games_and_skip_far_markets(self):
        now = dt.datetime(2026, 12, 5, 12, 0, tzinfo=dt.timezone.utc)   # 30 hours before the Dec 6 game
        games = [game("g1", "2026-12-06", "SF", "MIN"), game("g2", "2026-12-20", "DAL", "SEA")]
        markets = [
            {"ticker": "KXNFLGAME-26DEC06MINSF-SF", "event_ticker": "KXNFLGAME-26DEC06MINSF", "title": "SF wins",
             "close_time": "2026-12-06T18:00:00Z", "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.44"},
            {"ticker": "KXNFLGAME-26DEC20DALSEA-DAL", "event_ticker": "KXNFLGAME-26DEC20DALSEA", "title": "DAL wins",
             "close_time": "2026-12-20T18:00:00Z", "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.44"},
        ]
        rows = pro.snapshot_rows(markets, games, now)
        self.assertEqual([r["market_id"] for r in rows], ["KXNFLGAME-26DEC06MINSF-SF"])
        self.assertAlmostEqual(rows[0]["mid"], 0.42)
        self.assertGreater(rows[0]["hours_to_close"], 0)


if __name__ == "__main__":
    unittest.main()
