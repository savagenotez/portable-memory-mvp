import unittest

from prediction_markets.nfl.data import Game
from prediction_markets.nfl.efficiency import TeamGame, efficiency_diffs, net_per_play, parse_team_stats
from prediction_markets.nfl.injuries import injury_diff, parse_injury_counts


def g(gid, day, home, away):
    return Game(game_id=gid, season=2025, week=1, gameday=day, home=home, away=away, home_score=None,
                away_score=None, rest_home=7, rest_away=7, div_game=0, neutral=False)


def tg(gid, team, opp, epa, plays=60.0):
    return TeamGame(season=2025, week=1, game_id=gid, team=team, opponent=opp, plays=plays, epa=epa)


class EfficiencyTests(unittest.TestCase):
    def test_net_is_team_offence_minus_opponent_offence(self):
        rows = [tg("G", "A", "B", 12.0), tg("G", "B", "A", -6.0)]   # A: 0.2/play, B: -0.1/play
        net = net_per_play(rows)
        self.assertAlmostEqual(net[("G", "A")], 0.3)
        self.assertAlmostEqual(net[("G", "B")], -0.3)

    def test_same_day_games_do_not_inform_each_other(self):
        games = [g("g1", "2025-09-07", "A", "C"), g("g2", "2025-09-07", "B", "A")]
        rows = [tg("g1", "A", "C", 20.0), tg("g1", "C", "A", -10.0)]    # A looks strong in g1
        diffs = efficiency_diffs(games, rows, halflife=10)
        self.assertEqual(diffs["g1"], 0.0)
        self.assertEqual(diffs["g2"], 0.0)                              # same day: must not see g1

    def test_next_day_uses_the_earlier_result(self):
        games = [g("g1", "2025-09-07", "A", "C"), g("g2", "2025-09-14", "A", "B")]
        rows = [tg("g1", "A", "C", 20.0), tg("g1", "C", "A", -10.0)]
        diffs = efficiency_diffs(games, rows, halflife=10)
        self.assertGreater(diffs["g2"], 0.0)                            # A's strong game counts from the next week

    def test_parse_reads_the_nflverse_columns(self):
        text = ("season,week,team,opponent_team,game_id,attempts,carries,sacks_suffered,passing_epa,rushing_epa\n"
                "2025,1,ARI,NO,2025_01_ARI_NO,29,27,2,1.5,1.2\n")
        r = parse_team_stats(text)[0]
        self.assertEqual((r.team, r.opponent), ("ARI", "NO"))
        self.assertAlmostEqual(r.plays, 58.0)
        self.assertAlmostEqual(r.off_pp, 2.7 / 58.0)


class InjuryTests(unittest.TestCase):
    TEXT = ("season,season_type,team,week,position,report_status\n"
            "2025,REG,SF,5,QB,Out\n"
            "2025,REG,SF,5,RB,Out\n"            # not a key position: not counted
            "2025,REG,SF,5,CB,Questionable\n"   # questionable: not counted
            "2025,REG,MIN,5,WR,Doubtful\n"
            "2025,REG,MIN,5,DE,Out\n")

    def test_counts_only_out_or_doubtful_key_positions(self):
        c = parse_injury_counts(self.TEXT)
        self.assertEqual(c[(2025, 5, "SF")], 1)
        self.assertEqual(c[(2025, 5, "MIN")], 2)

    def test_diff_is_home_minus_away(self):
        c = parse_injury_counts(self.TEXT)
        self.assertEqual(injury_diff(c, 2025, 5, home="SF", away="MIN"), 1.0)   # MIN has more missing


if __name__ == "__main__":
    unittest.main()
