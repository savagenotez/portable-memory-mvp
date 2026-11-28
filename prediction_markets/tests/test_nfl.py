import random
import unittest
from dataclasses import replace

from prediction_markets.nfl import compare as cmp_mod
from prediction_markets.nfl.data import Game, parse_games
from prediction_markets.nfl.features import (
    feature_vector, fit_logistic, replay_elo, sigmoid, walk_forward_home_prob,
)
from prediction_markets.nfl.match import match_observation, parse_event
from prediction_markets.realdata.observation import Observation


def game(gid, day, home, away, hs=None, as_=None, season=2025, rest=(7, 7), div=0, neutral=False):
    return Game(game_id=gid, season=season, week=1, gameday=day, home=home, away=away, home_score=hs,
                away_score=as_, rest_home=rest[0], rest_away=rest[1], div_game=div, neutral=neutral)


CSV = ("game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,"
       "location,result,total,overtime,away_rest,home_rest,div_game,temp,wind\n"
       "2025_01_A_B,2025,REG,1,2025-09-07,Sunday,13:00,B,20,A,24,Home,4,44,0,7,6,0,,\n"
       "2025_01_C_D,2025,REG,1,2025-09-07,Sunday,13:00,D,,C,,Neutral,,,0,7,7,1,,\n")


class DataTests(unittest.TestCase):
    def test_parse_reads_scores_rest_location_and_completion(self):
        g = parse_games(CSV)
        played, future = g[0], g[1]
        self.assertTrue(played.completed)
        self.assertEqual(played.home_won, 1)
        self.assertEqual((played.rest_home, played.rest_away), (6, 7))
        self.assertFalse(future.completed)
        self.assertIsNone(future.home_won)
        self.assertTrue(future.neutral)

    def test_ties_have_no_winner(self):
        self.assertIsNone(game("t", "2025-01-01", "A", "B", 20, 20).home_won)


class EloTests(unittest.TestCase):
    def test_a_games_pregame_value_ignores_its_own_result(self):
        # g1's pre-game value must not depend on g1's own score; g2's value legitimately does depend on it.
        won = [game("g1", "2025-09-07", "A", "B", 30, 0), game("g2", "2025-09-14", "A", "C")]
        lost = [game("g1", "2025-09-07", "A", "B", 0, 30), game("g2", "2025-09-14", "A", "C")]
        self.assertAlmostEqual(replay_elo(won)["g1"], replay_elo(lost)["g1"])
        self.assertNotAlmostEqual(replay_elo(won)["g2"], replay_elo(lost)["g2"])

    def test_pregame_value_changes_with_earlier_results(self):
        winners = [game("g1", "2025-09-07", "A", "B", 30, 0), game("g2", "2025-09-14", "A", "C")]
        losers = [game("g1", "2025-09-07", "A", "B", 0, 30), game("g2", "2025-09-14", "A", "C")]
        self.assertGreater(replay_elo(winners)["g2"], replay_elo(losers)["g2"])

    def test_home_advantage_only_at_non_neutral_sites(self):
        home = replay_elo([game("g", "2025-09-07", "A", "B")])["g"]
        neutral = replay_elo([game("g", "2025-09-07", "A", "B", neutral=True)])["g"]
        self.assertAlmostEqual(home - neutral, 65.0)

    def test_season_regression_pulls_ratings_toward_the_mean(self):
        games = [game("g1", "2025-09-07", "A", "B", 30, 0, season=2025),
                 game("g2", "2026-09-06", "A", "B", season=2026)]
        d_same = replay_elo([game("g1", "2025-09-07", "A", "B", 30, 0, season=2025),
                             game("g2", "2025-12-07", "A", "B", season=2025)])["g2"]
        d_next = replay_elo(games)["g2"]
        self.assertLess(d_next, d_same)


class ModelTests(unittest.TestCase):
    def test_logistic_recovers_a_known_coefficient(self):
        rng = random.Random(3)
        X, y = [], []
        for _ in range(3000):
            x = rng.gauss(0, 1)
            X.append([1.0, x])
            y.append(1 if rng.random() < sigmoid(0.2 + 1.5 * x) else 0)
        w = fit_logistic(X, y)
        self.assertLess(abs(w[1] - 1.5), 0.15)
        self.assertLess(abs(w[0] - 0.2), 0.15)

    def test_walk_forward_never_uses_the_target_day_or_later(self):
        # Two copies of the history differ only in games on or after the target day. The forecast must match.
        base = [game(f"h{i}", f"2025-09-{i + 1:02d}", "A", "B", 20 + i % 3, 17) for i in range(10)]
        target = [game("target", "2025-10-01", "A", "B")]
        later = [game("late", "2025-10-05", "A", "B", 3, 40)]
        one = walk_forward_home_prob(base + target + later, {"target"})["target"]
        two = walk_forward_home_prob(base + target + [replace(later[0], home_score=40, away_score=3)],
                                     {"target"})["target"]
        self.assertAlmostEqual(one, two, places=12)

    def test_feature_vector_caps_rest(self):
        x = feature_vector(game("g", "2025-09-07", "A", "B", rest=(14, 0)), 0.0)
        self.assertEqual(x[2], 1.0)


class MatchTests(unittest.TestCase):
    def test_parse_event_gives_the_date_and_team_block(self):
        self.assertEqual(parse_event("KXNFLGAME-26NOV22MINSF"), ("2026-11-22", "MINSF"))
        self.assertIsNone(parse_event("KXNFLGAME-XX"))

    def test_match_finds_the_game_and_which_side_the_yes_team_is(self):
        games = [game("g", "2026-11-22", "SF", "MIN", 30, 20, season=2026)]
        obs = Observation("kalshi", "KXNFLGAME-26NOV22MINSF-SF", "KXNFLGAME-26NOV22MINSF", "SF wins",
                          0.0, 24.0, 0.6, 1)
        g, side = match_observation(obs, games)
        self.assertEqual((g.game_id, side), ("g", "home"))
        obs_min = replace(obs, market_id="KXNFLGAME-26NOV22MINSF-MIN")
        self.assertEqual(match_observation(obs_min, games)[1], "away")

    def test_codes_that_differ_between_sources_are_aliased(self):
        games = [game("g", "2026-11-15", "LA", "ARI", season=2026)]
        obs = Observation("kalshi", "KXNFLGAME-26NOV15LARARI-LAR", "KXNFLGAME-26NOV15LARARI", "LA wins", 0.0, 24.0,
                          0.5, 1)
        self.assertEqual(match_observation(obs, games)[1], "home")

    def test_unknown_games_are_not_guessed(self):
        obs = Observation("kalshi", "KXNFLGAME-26NOV22QQQZZZ-ZZZ", "KXNFLGAME-26NOV22QQQZZZ", "t", 0.0, 24.0, 0.5, 0)
        self.assertIsNone(match_observation(obs, [game("g", "2026-11-22", "SF", "MIN")]))


class CompareTests(unittest.TestCase):
    def test_no_matches_is_reported_not_scored(self):
        rep = cmp_mod.compare([], [game("g", "2026-09-01", "SF", "MIN", 30, 10, season=2026)], bootstrap=20)
        self.assertEqual(rep["matched"], 0)

    def test_scores_are_on_the_same_matched_games(self):
        days = ["2026-09-01", "2026-09-08", "2026-09-15"]
        games = [game(f"g{i}", d, "SF", "MIN", 30, 10, season=2026) for i, d in enumerate(days)]
        obs = [Observation("kalshi", f"KXNFLGAME-26SEP{d[-2:]}MINSF-SF", f"KXNFLGAME-26SEP{d[-2:]}MINSF",
                           "SF wins", 0.0, 24.0, 0.7, 1) for d in days]
        rep = cmp_mod.compare(obs, games, bootstrap=100)
        self.assertEqual(rep["matched"], 3)
        self.assertEqual(rep["agreement_with_score"], 1.0)
        self.assertEqual(len(rep["model_minus_market_ci95"]), 2)
        self.assertLessEqual(rep["model_minus_market_ci95"][0], rep["model_minus_market_ci95"][1])

if __name__ == "__main__":
    unittest.main()
