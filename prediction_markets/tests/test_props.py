import unittest

from prediction_markets.nfl import player_props as P
from prediction_markets.nfl import team_props as T
from prediction_markets.nfl.data import Game


def game(gid, day, home="SF", away="MIN", hs=24, as_=17, season=2020):
    return Game(gid, season, 1, day, home, away, hs, as_, 7, 7, 0, False, "outdoors")


def data(gid="g1"):
    return {"td": [[gid, "SF", 1], [gid, "SF", 3], [gid, "MIN", 2]],
            "fg": [[gid, "SF", 2, 45.0, 1, "K1"], [gid, "SF", 4, 52.0, 0, "K1"], [gid, "MIN", 4, 30.0, 1, "K2"]],
            "xp": [[gid, "SF", 1, 1], [gid, "SF", 3, 1], [gid, "MIN", 2, 1]], "two": [],
            "pass": [[gid, "SF", 1, "QB1", "WR1", 1, 12.0], [gid, "SF", 1, "QB1", "WR1", 0, 0.0],
                     [gid, "SF", 2, "QB1", "TE1", 1, 30.0], [gid, "SF", 3, "QB1", "", 0, 0.0]],
            "rush": [[gid, "SF", 1, "RB1", 5.0], [gid, "SF", 4, "RB1", -3.0]],
            "names": {}, "state": {}, "weather": {}}


BOUNDARY = {"game_id": "g1", "home": "SF", "away": "MIN", "q1": {"hs": 7, "as": 0}, "q2": {"hs": 10, "as": 7},
            "q3": {"hs": 17, "as": 7}, "q4": {"hs": 17, "as": 10}, "final": {"hs": 17, "as": 10}}


class TeamTests(unittest.TestCase):
    def test_actuals_by_quarter(self):
        a = T.team_actuals(data(), [BOUNDARY])
        sf = a[("g1", "SF")]
        self.assertEqual(sf["td"][1:5], [1, 0, 1, 0])
        self.assertEqual((sum(sf["fga"]), sum(sf["fgm"])), (2, 1))
        self.assertEqual(sf["points"][1:], [7, 3, 7, 0, 0])
        self.assertEqual(sf["kicker"], "K1")
        self.assertEqual(a[("g1", "MIN")]["points"][1:], [0, 7, 0, 3, 0])

    def test_a_scoreless_team_still_has_every_count(self):
        b = dict(BOUNDARY, game_id="g2", home="NE", away="NYJ")
        a = T.team_actuals(data(), [BOUNDARY, b])
        self.assertEqual(a[("g2", "NE")]["sd"], [0] * 6)
        self.assertEqual(a[("g1", "SF")]["sd"][1:5], [1, 1, 1, 0])

    def test_weather_only_counts_outdoors(self):
        self.assertEqual(T.weather_x({"roof": "dome", "wind": 20, "temp": 10}), (0.0, 0.0))
        self.assertEqual(T.weather_x({"roof": "outdoors", "wind": 20, "temp": 30}), (2.0, 1.0))

    def test_forecast_is_consistent(self):
        m = T.TeamModel(8, 4)
        f = m.forecast("SF", "MIN")
        g = f[("home", "game")]["points"].mean
        quarters = sum(f[("home", f"Q{q}")]["points"].mean for q in (1, 2, 3, 4))
        self.assertLess(quarters, g + 1e-6)                    # overtime is part of the game, not of Q1-Q4
        self.assertAlmostEqual(f["total"].mean, g + f[("away", "game")]["points"].mean, places=4)
        self.assertAlmostEqual(f["margin"].mean, g - f[("away", "game")]["points"].mean, places=4)

    def test_update_learns_a_high_scoring_team(self):
        m = T.TeamModel(8, 2)
        acts = T.team_actuals(data(), [BOUNDARY])
        before = m.means("SF", "MIN")[("td", "home")]
        for _ in range(5):
            m.update(game("g1", "2020-09-13"), acts, None)
        self.assertNotEqual(m.means("SF", "MIN")[("td", "home")], before)


class DriveTests(unittest.TestCase):
    def test_scoring_drive_points(self):
        m = T.TeamModel(8, 4, drives=True)
        d = m.per_drive("SF")
        self.assertAlmostEqual(sum(d.pmf), 1.0)
        self.assertEqual(d.offset, 3)                              # a field goal is the smallest score
        self.assertEqual(d.prob(4), 0.0)

    def test_drive_points_mean_is_drives_times_points_per_drive(self):
        m = T.TeamModel(8, 4, drives=True)
        f = m.forecast("SF", "MIN")
        mu_sd = m.means("SF", "MIN")[("sd", "home")]
        self.assertAlmostEqual(f[("home", "game")]["points"].mean, mu_sd * m.per_drive("SF").mean, places=3)


class InplayV2Tests(unittest.TestCase):
    def test_state_is_signed_for_the_home_team(self):
        from prediction_markets.nfl.inplay_v2 import state_x
        st = {"q1": ["SF", 25.0, 1, 10], "h2": "MIN"}
        self.assertEqual(state_x("Q1", "SF", st), [1.0, 0.75, 0.0])
        self.assertEqual(state_x("Q1", "MIN", st), [-1.0, -0.75, 0.0])
        self.assertEqual(state_x("H1", "SF", st), [0.0, 0.0, -1.0])
        self.assertIsNone(state_x("Q3", "SF", st))

    def test_least_squares(self):
        from prediction_markets.nfl.inplay_v2 import _lstsq
        X = [[1.0, x, 0.0] for x in (0.0, 1.0, 2.0, 3.0)] + [[0.0, 0.0, 1.0]]
        y = [1.0, 3.0, 5.0, 7.0, 4.0]
        a, b, c = _lstsq(X, y)
        self.assertAlmostEqual(a, 1.0, places=4)
        self.assertAlmostEqual(b, 2.0, places=4)
        self.assertAlmostEqual(c, 4.0, places=4)


class PlayerTests(unittest.TestCase):
    def test_actuals_and_pairs(self):
        players, pairs = P.player_actuals(data())
        sf = players[("g1", "SF")]
        self.assertEqual((sf["QB1"]["att"], sf["QB1"]["cmp"], sf["QB1"]["pyd"]), (4, 2, 42.0))
        self.assertEqual((sf["WR1"]["tgt"], sf["WR1"]["rec"]), (2, 1))
        self.assertEqual(sf["RB1"]["car"], 2)
        self.assertEqual(pairs[("g1", "SF")][("QB1", "TE1")], {"tgt": 1, "rec": 1, "yd": 30.0})

    def test_injured_players_are_not_projected(self):
        players, pairs = P.player_actuals(data())
        m = P.PlayerModel({s: (8, 3) for s in P.COUNT_STATS})
        m.update_team_game("SF", players[("g1", "SF")], pairs[("g1", "SF")], m.eligible("SF", set()))
        self.assertIn("WR1", m.eligible("SF", set())["receiver"])
        self.assertNotIn("WR1", m.eligible("SF", {"WR1"})["receiver"])
        self.assertEqual(m.primary_qb["SF"], "QB1")

    def test_negative_rushing_counts_as_zero(self):
        self.assertEqual(P._count(-3.0), 0)
        self.assertEqual(P._line(4.2), 4.5)


if __name__ == "__main__":
    unittest.main()
