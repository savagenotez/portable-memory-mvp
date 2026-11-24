import unittest

from prediction_markets.statmodel import norm_cdf
from prediction_markets.vbgpc import GoalAttainmentController, SubjectProfile


def controller(lo=0.0, hi=10.0, prior=5.0, n0=10.0, total=20, goal=100.0, trials=4000, seed=1):
    profile = SubjectProfile(prior_mean=prior, prior_strength=n0, stat_min=lo, stat_max=hi)
    return GoalAttainmentController(profile, goal=goal, total_steps=total, trials=trials, seed=seed)


class FeasibilityTests(unittest.TestCase):
    def test_infeasible_when_goal_above_max_reachable(self):
        c = controller(lo=0, hi=10, total=10, goal=1000)
        self.assertEqual(c.step_plan()["status"], "MATHEMATICALLY_INFEASIBLE")

    def test_guaranteed_when_goal_below_min_reachable(self):
        c = controller(lo=1, hi=10, total=10, goal=5)
        plan = c.step_plan()
        self.assertEqual(plan["status"], "GUARANTEED")
        self.assertEqual(plan["probability"], 1.0)

    def test_horizon_expired(self):
        c = controller(lo=0, hi=10, total=2, goal=10)
        c.record_observation(3)
        c.record_observation(3)  # total 6 < goal 10, horizon used up
        self.assertEqual(c.step_plan()["status"], "HORIZON_EXPIRED")


class RegimeTests(unittest.TestCase):
    def test_lock_in_when_comfortably_ahead(self):
        c = controller(lo=0, hi=20, prior=10, n0=0.0, total=20, goal=150)
        for _ in range(10):
            c.record_observation(10.0)  # zero sample sd, so margin is tiny
        plan = c.step_plan()
        self.assertEqual(plan["regime"], "LOCK_IN_LOW_VARIANCE")
        self.assertGreaterEqual(plan["recommended_next_target"], plan["required_pace"] - 1e-9)
        self.assertLessEqual(plan["recommended_next_target"], plan["shrunk_mean"] + 1e-9)

    def test_pd_pacing_in_middle_band(self):
        c = controller(lo=0, hi=10, prior=5, n0=10, total=20, goal=60)
        for _ in range(10):
            c.record_observation(1.0)  # mu_hat = 3, required pace = 5, high threshold = 8.25
        self.assertEqual(c.step_plan()["regime"], "PD_PACING_CONTROL")

    def test_tail_seeking_when_far_behind_late(self):
        c = controller(lo=0, hi=10, prior=5, n0=10, total=20, goal=100)
        for _ in range(10):
            c.record_observation(1.0)  # required pace = 9 > high threshold 8.25
        plan = c.step_plan()
        self.assertEqual(plan["regime"], "TAIL_SEEKING_HIGH_VARIANCE")
        self.assertEqual(plan["recommended_next_target"], 10.0)
        self.assertEqual(plan["variance_policy"], "maximize_upside")


class ProbabilityTests(unittest.TestCase):
    def test_monte_carlo_matches_normal_approx_with_wide_bounds(self):
        c = GoalAttainmentController(
            SubjectProfile(prior_mean=5.0, prior_strength=0.0, stat_min=-1e6, stat_max=1e6),
            goal=45.0,
            total_steps=10,
            trials=20000,
            seed=3,
        )
        mc = c.simulate_attainment_prob(0.0, 10, 5.0, 2.0)
        approx = c.normal_approx_prob(0.0, 10, 5.0, 2.0)
        self.assertAlmostEqual(approx, 1.0 - norm_cdf((45 - 50) / (2 * 10 ** 0.5)), places=9)
        self.assertLess(abs(mc - approx), 0.02)

    def test_more_volatility_helps_when_goal_is_above_expected_total(self):
        # G > C + k * mu  =>  dP/dsigma > 0 (Regime 3 rationale)
        c = GoalAttainmentController(
            SubjectProfile(prior_mean=5.0, prior_strength=0.0, stat_min=0.0, stat_max=100.0),
            goal=60.0,
            total_steps=10,
            trials=6000,
            seed=11,
        )
        low_vol = c.simulate_attainment_prob(0.0, 10, 5.0, 1.0)
        high_vol = c.simulate_attainment_prob(0.0, 10, 5.0, 8.0)
        self.assertGreater(high_vol, low_vol)

    def test_seeded_controllers_reproduce(self):
        a = controller(seed=42)
        b = controller(seed=42)
        for c in (a, b):
            for y in (4, 6, 5, 7):
                c.record_observation(y)
        self.assertEqual(a.attainment_probability(), b.attainment_probability())


class StateTests(unittest.TestCase):
    def test_observations_are_clamped(self):
        c = controller(lo=0, hi=10)
        c.record_observation(99)
        c.record_observation(-5)
        self.assertEqual(c.history, [10.0, 0.0])

    def test_trend_uses_baseline_before_latest_observation(self):
        c = controller(lo=0, hi=10, prior=5, n0=10)
        before = c.estimate_parameters()[0]
        c.record_observation(10.0)
        self.assertAlmostEqual(c.prev_shrunk_mean, before)

    def test_step_plan_has_no_side_effects_on_trend(self):
        c = controller(lo=0, hi=10, prior=5, n0=10, total=20, goal=60)
        for _ in range(5):
            c.record_observation(3.0)
        before = c.prev_shrunk_mean
        c.step_plan()
        c.step_plan()
        self.assertEqual(c.prev_shrunk_mean, before)


class DependenceAndDriftTests(unittest.TestCase):
    def test_estimate_phi_bounds(self):
        from prediction_markets.vbgpc import estimate_phi
        self.assertEqual(estimate_phi([1.0, 2.0]), 0.0)                       # too short
        alternating = [0.0, 10.0] * 20                                         # negative lag-1 corr
        self.assertEqual(estimate_phi(alternating), 0.0)
        ramp = [float(i) for i in range(30)]                                   # strong positive corr
        self.assertGreater(estimate_phi(ramp), 0.5)
        self.assertLessEqual(estimate_phi(ramp, cap=0.95), 0.95)

    def test_constant_drift_equals_shifted_prior(self):
        # Shifting history, prior and drift by the same constant leaves the forecast unchanged.
        history = [22.0, 25.0, 19.0, 27.0, 24.0, 23.0]
        c = 3.0
        flat = GoalAttainmentController(
            SubjectProfile(prior_mean=20.0 + c, prior_strength=4.0, stat_min=0.0, stat_max=100.0),
            goal=150.0, total_steps=12, trials=3000, seed=21)
        drifted = GoalAttainmentController(
            SubjectProfile(prior_mean=20.0, prior_strength=4.0, stat_min=0.0, stat_max=100.0),
            goal=150.0, total_steps=12, trials=3000, seed=21, drift=lambda t: c)
        for y in history:
            flat.record_observation(y)
            drifted.record_observation(y)
        # The drift controller's baseline is on de-drifted data, so add the constant back.
        self.assertAlmostEqual(flat.estimate_parameters()[0], drifted.estimate_parameters()[0] + c, places=9)
        self.assertAlmostEqual(flat.attainment_probability(), drifted.attainment_probability(), places=12)

    def test_negative_future_drift_lowers_attainment(self):
        history = [10.0] * 6
        plain = GoalAttainmentController(
            SubjectProfile(prior_mean=10.0, prior_strength=0.0, stat_min=0.0, stat_max=20.0),
            goal=110.0, total_steps=12, trials=3000, seed=5)
        falling = GoalAttainmentController(
            SubjectProfile(prior_mean=10.0, prior_strength=0.0, stat_min=0.0, stat_max=20.0),
            goal=110.0, total_steps=12, trials=3000, seed=5,
            drift=lambda t: -2.0 if t >= 6 else 0.0)
        for y in history:
            plain.record_observation(y)
            falling.record_observation(y)
        self.assertLess(falling.attainment_probability(), plain.attainment_probability())

    def test_unknown_dependence_rejected(self):
        with self.assertRaises(ValueError):
            GoalAttainmentController(SubjectProfile(5.0, 1.0, 0.0, 10.0), goal=10.0, total_steps=5, dependence="garch")

    def test_mu_uncertainty_is_reproducible(self):
        def run():
            c = GoalAttainmentController(SubjectProfile(5.0, 2.0, 0.0, 10.0), goal=40.0, total_steps=10,
                                         trials=2000, seed=8, mu_uncertainty=True)
            for y in (4.0, 6.0, 5.0, 7.0):
                c.record_observation(y)
            return c.attainment_probability()
        self.assertEqual(run(), run())


class CalibrationStudyTests(unittest.TestCase):
    def test_small_study_has_every_variant_and_domain(self):
        from prediction_markets.calibration import VARIANTS, run_study
        study = run_study(replicates=4, trials=20, seed_base=123_000)
        self.assertEqual(set(study["variants"]), set(VARIANTS))
        for name, v in study["variants"].items():
            with self.subTest(variant=name):
                self.assertEqual(len(v["domains"]), 5)
                self.assertIn("passes_all_domains", v)



if __name__ == "__main__":
    unittest.main()
