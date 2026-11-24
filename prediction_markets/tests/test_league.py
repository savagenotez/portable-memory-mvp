import copy
import math
import random
import unittest
from dataclasses import replace

from prediction_markets.league import evaluate as ev
from prediction_markets.league import study
from prediction_markets.league.features import BASE_BRANCHES, branches_for, build_rows
from prediction_markets.league.model import (
    BranchEnsemble, EWMAStat, ModelConfig, Standardizer, logloss, sigmoid,
)
from prediction_markets.league.sim import LeagueConfig, config_from_dict, simulate_league


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a) / n)
    sb = math.sqrt(sum((x - mb) ** 2 for x in b) / n)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / n / (sa * sb)


class SimulatorTests(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        a = simulate_league(LeagueConfig(seasons=2), random.Random(4))
        b = simulate_league(LeagueConfig(seasons=2), random.Random(4))
        self.assertEqual([g.home_win for g in a.games], [g.home_win for g in b.games])
        self.assertEqual([g.p_true for g in a.games], [g.p_true for g in b.games])

    def test_oracle_probabilities_and_structure(self):
        ld = simulate_league(LeagueConfig(seasons=2), random.Random(1))
        cfg = ld.config
        self.assertEqual(len(ld.teams), cfg.n_teams)
        self.assertTrue(all(0.0 < g.p_true < 1.0 for g in ld.games))
        self.assertTrue(all(g.home != g.away for g in ld.games))
        self.assertTrue(all(1 <= g.rest_home <= 3 and 1 <= g.rest_away <= 3 for g in ld.games))
        # indoor venues have no weather
        self.assertTrue(all(g.wind == 0.0 for g in ld.games if g.indoor))

    def test_oracle_is_calibrated_against_outcomes(self):
        ps, ys = [], []
        for seed in range(6):
            ld = simulate_league(LeagueConfig(seasons=3), random.Random(seed))
            ps += [g.p_true for g in ld.games]
            ys += [g.home_win for g in ld.games]
        gap = sum(ps) / len(ps) - sum(ys) / len(ys)
        se = math.sqrt(0.25 / len(ys))
        self.assertLess(abs(gap), 3 * se)

    def test_unknown_scenario_and_config_keys_rejected(self):
        with self.assertRaises(ValueError):
            simulate_league(LeagueConfig(scenario="nope"), random.Random(0))
        with self.assertRaises(ValueError):
            config_from_dict({"not_a_key": 1})

    def test_spurious_feature_tracks_strength_early_then_not(self):
        ld = simulate_league(LeagueConfig(seasons=5, spurious_until_season=2), random.Random(2))
        early = [g for g in ld.games if g.season < 2]
        late = [g for g in ld.games if g.season >= 2]
        self.assertGreater(corr([g.spurious for g in early], [g.margin_mean for g in early]), 0.3)
        self.assertLess(abs(corr([g.spurious for g in late], [g.margin_mean for g in late])), 0.15)

    def test_leak_feature_carries_the_outcome(self):
        ld = simulate_league(LeagueConfig(seasons=2), random.Random(3))
        self.assertGreater(corr([g.leak for g in ld.games], [float(g.home_win) for g in ld.games]), 0.8)

    def test_regime_shift_is_marked(self):
        ld = simulate_league(LeagueConfig(seasons=4, scenario="regime_shift"), random.Random(5))
        self.assertIsNotNone(ld.shift_game_index)
        clean = simulate_league(LeagueConfig(seasons=4), random.Random(5))
        self.assertIsNone(clean.shift_game_index)


class FeatureTests(unittest.TestCase):
    def test_features_use_no_future_information(self):
        ld = simulate_league(LeagueConfig(seasons=3), random.Random(3))
        a = build_rows(ld)
        k = 300
        altered = copy.deepcopy(ld)
        for g in altered.games[k:]:
            g.home_pts += 37
            g.away_pts -= 11
            g.home_win = 1 - g.home_win
            g.eff_home = tuple(None if e is None else e + 5 for e in g.eff_home)
            g.eff_away = tuple(None if e is None else e - 5 for e in g.eff_away)
        b = build_rows(altered)
        for i in range(k + 1):
            self.assertEqual(a[i].features, b[i].features)
            self.assertEqual(a[i].context, b[i].context)

    def test_every_scenario_branch_feature_exists(self):
        ld = simulate_league(LeagueConfig(seasons=1), random.Random(0))
        row = build_rows(ld)[50]
        for scenario in ("clean", "spurious_decoy", "leakage_trap", "duplicate_branch", "regime_shift"):
            for cols in branches_for(scenario).values():
                for c in cols:
                    self.assertIn(c, row.features)

    def test_base_branches_unchanged_by_extras(self):
        self.assertEqual(set(branches_for("clean")), set(BASE_BRANCHES))
        self.assertIn("leak", branches_for("leakage_trap"))
        self.assertNotIn("leak", branches_for("clean"))

    def test_team_features_track_true_strength(self):
        ld = simulate_league(LeagueConfig(seasons=3), random.Random(7))
        rows = build_rows(ld)[400:]
        mm = [g.margin_mean for g in ld.games[400:]]
        self.assertGreater(corr([r.features["net_diff"] for r in rows], mm), 0.5)
        self.assertLess(abs(corr([r.features["n1"] for r in rows], mm)), 0.15)


def stream(n, seed, signal=1.2, flip_at=None, leak=False):
    rng = random.Random(seed)
    out = []
    for t in range(n):
        s = signal if (flip_at is None or t < flip_at) else -signal
        x1, x2 = rng.gauss(0, 1), rng.gauss(0, 1)
        y = 1 if rng.random() < sigmoid(s * x1) else 0
        f = {"x1": x1, "x2": x2, "n1": rng.gauss(0, 1), "n2": rng.gauss(0, 1)}
        if leak:
            f["l"] = (2 * y - 1) * 0.9 + 0.4 * rng.gauss(0, 1)
        out.append((f, y))
    return out


def run_stream(model, data):
    losses = []
    for f, y in data:
        pr = model.predict(f, {"min_games_total": 1000.0})
        losses.append(logloss(pr.p, y))
        model.update(pr, y)
    return losses


class ModelTests(unittest.TestCase):
    BF = {"signal": ["x1", "x2"], "noise": ["n1", "n2"]}

    def test_primitives(self):
        self.assertAlmostEqual(sigmoid(0.0), 0.5)
        self.assertGreater(sigmoid(800), 0.999999)
        self.assertLess(sigmoid(-800), 1e-6)
        self.assertAlmostEqual(logloss(0.5, 1), math.log(2))
        e = EWMAStat(10)
        for x in [1.0] * 50:
            e.add(x)
        self.assertAlmostEqual(e.mean, 1.0)
        self.assertGreater(e.n_eff, 5)
        s = Standardizer(1, 100, 3.0)
        for _ in range(50):
            s.update([10.0])
        self.assertEqual(s.transform([1e9]), [3.0])

    def test_learns_signal_and_scores_it_above_noise(self):
        data = stream(3000, seed=1)
        m = BranchEnsemble(self.BF, ModelConfig())
        losses = run_stream(m, data)
        rate = sum(y for _, y in data) / len(data)
        base_loss = -(rate * math.log(rate) + (1 - rate) * math.log(1 - rate))
        self.assertLess(sum(losses[-1000:]) / 1000, base_loss - 0.02)
        rep = m.report()
        self.assertGreater(rep["signal"]["score"], rep["noise"]["score"] + 1.0)
        self.assertGreater(rep["signal"]["gate"], rep["noise"]["gate"])

    def test_quarantines_a_leaking_branch_only_when_a_cap_is_set(self):
        # The cap must sit above the best legitimate gain (about 0.14 nats here) and below the leak's.
        bf = dict(self.BF, leak=["l"])
        data = stream(1500, seed=2, leak=True)
        capped = BranchEnsemble(bf, ModelConfig(), plausible_gain=0.30)
        run_stream(capped, data)
        self.assertTrue(capped.report()["leak"]["quarantined"])
        self.assertEqual(capped.gate(capped.branches["leak"]), 0.0)
        self.assertFalse(capped.report()["signal"]["quarantined"])
        uncapped = BranchEnsemble(bf, ModelConfig(), plausible_gain=None)
        run_stream(uncapped, data)
        self.assertFalse(uncapped.report()["leak"]["quarantined"])

    def test_cap_stops_fake_skill(self):
        bf = dict(self.BF, leak=["l"])
        data = stream(2500, seed=3, leak=True)
        capped = run_stream(BranchEnsemble(bf, ModelConfig(), plausible_gain=0.30), data)
        uncapped = run_stream(BranchEnsemble(bf, ModelConfig(use_plausibility_cap=False), plausible_gain=0.30), data)
        self.assertGreater(sum(capped[-1000:]) / 1000, sum(uncapped[-1000:]) / 1000 + 0.1)

    def test_drift_alarm_fires_when_a_relationship_flips(self):
        data = stream(2200, seed=4, signal=1.5, flip_at=1800)
        on = BranchEnsemble(self.BF, ModelConfig(use_drift=True))
        off = BranchEnsemble(self.BF, ModelConfig(use_drift=False))
        run_stream(on, data)
        run_stream(off, data)
        self.assertGreaterEqual(on.report()["signal"]["drift_alarms"], 1)
        self.assertEqual(off.report()["signal"]["drift_alarms"], 0)

    def test_gate_is_bounded_and_floor_respected(self):
        data = stream(1500, seed=5)
        cfg = ModelConfig()
        m = BranchEnsemble(self.BF, cfg)
        run_stream(m, data)
        for b in m.branches.values():
            g = m.gate(b)
            self.assertTrue(cfg.gate_floor - 1e-9 <= g <= 1.0 + 1e-9)

    def test_predictions_stay_in_range_for_every_tripwire_setting(self):
        data = stream(400, seed=6)
        for flag in ("use_gates", "use_drift", "use_plausibility_cap", "use_early_shrink", "use_platt"):
            m = BranchEnsemble(self.BF, replace(ModelConfig(), **{flag: False}), plausible_gain=0.1)
            for f, y in data:
                pr = m.predict(f, {"min_games_total": 3.0})
                self.assertTrue(0.0 < pr.p < 1.0)
                m.update(pr, y)

    def test_early_shrink_pulls_toward_the_base_rate(self):
        data = stream(600, seed=7)
        m = BranchEnsemble(self.BF, ModelConfig())
        run_stream(m, data)
        f = {"x1": 2.0, "x2": 0.0, "n1": 0.0, "n2": 0.0}
        cold = m.predict(f, {"min_games_total": 0.0})
        warm = m.predict(f, {"min_games_total": 1000.0})
        self.assertLess(abs(cold.z_final - m.gamma), abs(warm.z_final - m.gamma))

    def test_deterministic(self):
        data = stream(300, seed=8)
        a = run_stream(BranchEnsemble(self.BF, ModelConfig()), data)
        b = run_stream(BranchEnsemble(self.BF, ModelConfig()), data)
        self.assertEqual(a, b)


class EvaluateTests(unittest.TestCase):
    def test_capture_math(self):
        self.assertAlmostEqual(ev.capture(0.25, 0.20, 0.15), 0.5)
        self.assertAlmostEqual(ev.capture(0.25, 0.25, 0.15), 0.0)
        self.assertAlmostEqual(ev.capture(0.25, 0.15, 0.15), 1.0)

    def test_calibration_row_and_slice_filter(self):
        row = ev.calibration_row([0.5] * 100, [1] * 50 + [0] * 50)
        self.assertTrue(row["passes"])
        bad = ev.calibration_row([0.8] * 400, [1] * 200 + [0] * 200)
        self.assertFalse(bad["passes"])
        ctx = {"min_games_season": 5.0, "cross_conf": 1.0, "wind_z": 0.0, "outdoor": 1.0, "streak_gap": 0.0}
        table = ev.slice_table([(ctx, 0.5, 1), (ctx, 0.5, 0)], min_n=300)
        self.assertFalse(table["season_games_3_9"]["evaluated"])
        self.assertEqual(table["season_games_3_9"]["n"], 2)

    def test_ci95_and_mean(self):
        m, lo, hi = ev.ci95([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(m, 2.5)
        self.assertLess(lo, m)
        self.assertGreater(hi, m)

    def test_base_rate_is_prequential(self):
        ld = simulate_league(LeagueConfig(seasons=1), random.Random(1))
        rows = build_rows(ld)
        base = ev.run_base_rate(rows)
        self.assertAlmostEqual(base[0], 0.5)
        self.assertAlmostEqual(base[1], (rows[0].y + 1.0) / 3.0)


class StudyPlumbingTests(unittest.TestCase):
    def test_one_league_run_has_the_expected_shape(self):
        cfg = study.load_config()
        lc = replace(config_from_dict(cfg["league"]), seasons=3, spurious_until_season=1)
        res = study.run_league(1000, "clean", lc, ModelConfig(**cfg["model"]), cap=0.14,
                               study=cfg["study"], want_samples=True)
        self.assertIn("post_warmup", res["windows"])
        for model in ("base", "oracle", "flat", "ens", "ens_off", "no_gates", "no_platt"):
            self.assertIn(model, res["windows"]["post_warmup"])
        self.assertLess(res["windows"]["post_warmup"]["oracle"], res["windows"]["post_warmup"]["base"])
        self.assertEqual(set(res["report"]), set(BASE_BRANCHES))
        self.assertGreater(len(res["samples"]), 100)

    def test_variants_turn_off_exactly_one_tripwire(self):
        base = ModelConfig()
        v = study.variants(base)
        self.assertFalse(v["no_gates"].use_gates)
        self.assertTrue(v["no_gates"].use_drift)
        self.assertFalse(any(getattr(v["ens_off"], f) for f in study.TRIPWIRE_FLAGS))

    def test_window_summary_capture(self):
        results = [{"windows": {"w": {"base": 0.25, "oracle": 0.15, "ens": 0.20, "flat": 0.22}}},
                   {"windows": {"w": {"base": 0.25, "oracle": 0.15, "ens": 0.20, "flat": 0.22}}}]
        s = study.window_summary(results, "w")
        self.assertAlmostEqual(s["capture"]["ens"], 0.5)
        self.assertAlmostEqual(s["capture"]["flat"], 0.3)

    def test_criteria_are_all_defined(self):
        self.assertEqual(set(study.CRITERIA), {f"C{i}" for i in range(1, 9)})


if __name__ == "__main__":
    unittest.main()
