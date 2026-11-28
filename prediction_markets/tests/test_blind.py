import json
import os
import tempfile
import unittest

from prediction_markets.nfl import blind
from prediction_markets.nfl.data import Game


def g(gid, season=2026, completed=False):
    return Game(game_id=gid, season=season, week=5, gameday="2026-10-04", home="SF", away="MIN",
                home_score=(20 if completed else None), away_score=(10 if completed else None),
                rest_home=7, rest_away=7, div_game=0, neutral=False, roof="outdoors")


class SealTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "manifest.json")

    def test_seal_lists_only_unplayed_games_and_is_hashed(self):
        games = [g("played", completed=True), g("future1"), g("future2"), g("old", season=2025)]
        m = blind.seal(games, path=self.path, now="2026-11-24T00:00:00+00:00")
        self.assertEqual(m["game_ids"], ["future1", "future2"])
        self.assertEqual(blind.sealed_ids(self.path), frozenset({"future1", "future2"}))

    def test_a_sealed_block_is_never_resealed(self):
        blind.seal([g("f")], path=self.path, now="2026-11-24T00:00:00+00:00")
        with self.assertRaises(blind.SealedGameError):
            blind.seal([g("f2")], path=self.path, now="2026-11-25T00:00:00+00:00")

    def test_editing_the_manifest_is_detected(self):
        blind.seal([g("f")], path=self.path, now="2026-11-24T00:00:00+00:00")
        with open(self.path) as fh:
            m = json.load(fh)
        m["game_ids"].append("sneaked-in")
        with open(self.path, "w") as fh:
            json.dump(m, fh)
        with self.assertRaises(blind.SealedGameError):
            blind.sealed_ids(self.path)

    def test_tuning_code_cannot_use_a_sealed_game(self):
        blind.seal([g("f")], path=self.path, now="2026-11-24T00:00:00+00:00")
        blind.assert_not_sealed(["historical-1"], "tuning", path=self.path)           # fine
        with self.assertRaises(blind.SealedGameError):
            blind.assert_not_sealed(["f"], "tuning", path=self.path)


class StatisticsTests(unittest.TestCase):
    def test_holm_is_never_smaller_than_raw_and_is_monotone(self):
        raw = {"a": 0.001, "b": 0.04, "c": 0.03, "d": 0.5}
        adj = blind.holm(raw)
        for k in raw:
            self.assertGreaterEqual(adj[k], raw[k] - 1e-12)
        self.assertLessEqual(adj["a"], adj["c"] + 1e-12)
        self.assertAlmostEqual(adj["a"], 0.004)                                     # 0.001 x 4

    def test_judge_refuses_before_the_sample_size_is_reached(self):
        blind_path = os.path.join(tempfile.mkdtemp(), "m.json")
        blind.seal([g("f")], path=blind_path, now="2026-11-24T00:00:00+00:00")
        old = blind.MANIFEST
        blind.MANIFEST = blind_path
        try:
            out = blind.judge(os.path.join(tempfile.mkdtemp(), "empty.jsonl"), [g("f")],
                              path=os.path.join(tempfile.mkdtemp(), "j.json"))
        finally:
            blind.MANIFEST = old
        self.assertEqual(out["status"], "not yet")


if __name__ == "__main__":
    unittest.main()
