import unittest

from prediction_markets.nfl import inplay


def play(gid, pid, qtr, hs, as_, home_wp=0.5, vegas=0.5, season="2025", week="3"):
    return {"game_id": gid, "play_id": str(pid), "qtr": str(qtr), "total_home_score": str(hs),
            "total_away_score": str(as_), "home_wp": str(home_wp), "vegas_home_wp": str(vegas),
            "season": season, "week": week, "home_team": "SF", "away_team": "MIN"}


class DerivationTests(unittest.TestCase):
    def test_takes_the_score_at_the_last_play_of_each_quarter(self):
        rows = [play("g", 1, 1, 0, 0), play("g", 5, 1, 3, 0), play("g", 9, 1, 3, 7),   # last Q1 play: 3-7
                play("g", 12, 2, 3, 7), play("g", 40, 2, 10, 7),                       # last Q2 play: 10-7
                play("g", 80, 4, 24, 17)]
        rec = inplay.derive_boundaries(rows)[0]
        self.assertEqual((rec["q1"]["hs"], rec["q1"]["as"]), (3, 7))
        self.assertEqual((rec["q2"]["hs"], rec["q2"]["as"]), (10, 7))
        self.assertEqual((rec["final"]["hs"], rec["final"]["as"]), (24, 17))
        self.assertIsNone(rec["q3"])                                              # no Q3 plays in this game

    def test_a_missing_score_is_skipped_not_guessed(self):
        bad = play("g", 3, 1, 0, 0)
        bad["total_home_score"] = ""
        self.assertEqual(inplay.derive_boundaries([bad]), [])


class ProbabilityTests(unittest.TestCase):
    def test_a_lead_raises_the_home_probability(self):
        self.assertGreater(inplay.win_prob(0.0, 7.0, 0.5, 2.0, 13.0), inplay.win_prob(0.0, 0.0, 0.5, 2.0, 13.0))
        self.assertGreater(inplay.win_prob(0.0, 0.0, 0.5, 2.0, 13.0), inplay.win_prob(0.0, -7.0, 0.5, 2.0, 13.0))

    def test_no_time_left_is_decided_by_the_score(self):
        self.assertGreater(inplay.win_prob(0.0, 1.0, 0.0, 2.0, 13.0), 0.99)
        self.assertLess(inplay.win_prob(0.0, -1.0, 0.0, 2.0, 13.0), 0.01)

    def test_full_game_with_no_score_is_the_pre_game_prior(self):
        m0 = 3.0
        self.assertAlmostEqual(inplay.win_prob(m0, 0.0, 1.0, 2.0, 13.0), inplay.win_prob(m0, 0.0, 1.0, 2.0, 13.0))
        self.assertGreater(inplay.win_prob(m0, 0.0, 1.0, 2.0, 13.0), 0.5)

    def test_brier_of_a_perfect_forecast_is_zero(self):
        self.assertAlmostEqual(inplay.brier([1.0, 0.0], [1, 0]), 0.0)


if __name__ == "__main__":
    unittest.main()
