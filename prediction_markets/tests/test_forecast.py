import random
import unittest

from prediction_markets.forecast import forecast_next_period, milestone_probability


HISTORY = [22.0, 25.0, 19.0, 27.0, 24.0, 23.0, 21.0, 26.0, 24.0, 25.0]


def run(**overrides):
    kwargs = dict(
        prior_mean=22.0,
        prior_strength=10.0,
        stat_min=0.0,
        stat_max=60.0,
        planned_actions=15.0,
        reference_actions=15.0,
        action_elasticity=0.7,
        milestone=30.0,
        trials=4000,
        rng=random.Random(4),
    )
    kwargs.update(overrides)
    return forecast_next_period(HISTORY, **kwargs)


class ForecastTests(unittest.TestCase):
    def test_more_planned_actions_means_higher_expected(self):
        low = run(planned_actions=10.0)
        high = run(planned_actions=20.0)
        self.assertGreater(high["expected"], low["expected"])

    def test_no_actions_means_zero_expected_before_clip(self):
        self.assertEqual(run(planned_actions=0.0)["expected"], 0.0)

    def test_fatigue_only_applies_above_baseline(self):
        rested = run(recent_workload=2, baseline_workload=3, fatigue_drag=2.0)
        tired = run(recent_workload=5, baseline_workload=3, fatigue_drag=2.0)
        self.assertEqual(rested["fatigue_drag_applied"], 0.0)
        self.assertEqual(tired["fatigue_drag_applied"], 4.0)
        self.assertLess(tired["expected"], rested["expected"])

    def test_range_is_ordered_and_bounded(self):
        out = run()
        self.assertLessEqual(out["likely_range_p10"], out["likely_range_p90"])
        self.assertGreaterEqual(out["likely_range_p10"], 0.0)
        self.assertLessEqual(out["likely_range_p90"], 60.0)

    def test_milestone_closed_form_matches_monte_carlo(self):
        out = run()
        self.assertLess(abs(out["milestone_probability"] - out["milestone_probability_mc"]), 0.03)
        self.assertTrue(0.0 <= out["milestone_probability"] <= 1.0)

    def test_milestone_probability_edges(self):
        self.assertEqual(milestone_probability(10, 2, -5, 0, 60), 1.0)
        self.assertEqual(milestone_probability(10, 2, 70, 0, 60), 0.0)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run(reference_actions=0.0)
        with self.assertRaises(ValueError):
            run(planned_actions=-1.0)


if __name__ == "__main__":
    unittest.main()
