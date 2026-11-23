import math
import unittest

from prediction_markets.statmodel import (
    ar1_stationary_sd,
    clip,
    eb_shrink,
    eb_weight,
    norm_cdf,
    popoviciu_max_std,
    shrunk_baseline,
)


class EmpiricalBayesTests(unittest.TestCase):
    def test_weight_limits(self):
        self.assertAlmostEqual(eb_weight(0, 4.0, 16.0), 0.0)
        self.assertLess(eb_weight(1, 4.0, 16.0), eb_weight(10, 4.0, 16.0))
        self.assertGreater(eb_weight(10_000, 4.0, 16.0), 0.999)

    def test_variance_form_matches_prior_strength_form(self):
        # tau^2 = 4, sigma^2 = 16  =>  n0 = sigma^2 / tau^2 = 4
        ybar, n, mu0 = 20.0, 10, 15.0
        variance_form = eb_shrink(ybar, n, mu0, tau2=4.0, sigma2=16.0)
        history = [ybar] * n
        strength_form, _ = shrunk_baseline(history, mu0, prior_strength=4.0, stat_min=0, stat_max=100)
        self.assertAlmostEqual(variance_form, strength_form, places=9)
        self.assertAlmostEqual(variance_form, 260.0 / 14.0, places=9)

    def test_no_history_returns_prior(self):
        # Popoviciu bound for [0, 60] is 30; with no data we use half of it.
        mu, sd = shrunk_baseline([], 22.0, 10.0, 0.0, 60.0)
        self.assertEqual(mu, 22.0)
        self.assertAlmostEqual(sd, 15.0)

    def test_popoviciu_clamps_volatility(self):
        history = [0.0, 10.0] * 50  # sample sd is about 5.03, bound is 5.0
        _, sd = shrunk_baseline(history, 5.0, 1.0, 0.0, 10.0)
        self.assertLessEqual(sd, popoviciu_max_std(0.0, 10.0) + 1e-12)

    def test_single_observation_uses_half_bound(self):
        _, sd = shrunk_baseline([7.0], 5.0, 1.0, 0.0, 10.0)
        self.assertAlmostEqual(sd, 2.5)


class HelperTests(unittest.TestCase):
    def test_clip(self):
        self.assertEqual(clip(-1, 0, 5), 0)
        self.assertEqual(clip(9, 0, 5), 5)
        self.assertEqual(clip(3, 0, 5), 3)

    def test_norm_cdf_known_values(self):
        self.assertAlmostEqual(norm_cdf(0.0), 0.5, places=12)
        self.assertAlmostEqual(norm_cdf(1.959963984540054), 0.975, places=6)

    def test_ar1_stationary_sd(self):
        self.assertAlmostEqual(ar1_stationary_sd(0.5, 1.0), 1.0 / math.sqrt(0.75))
        with self.assertRaises(ValueError):
            ar1_stationary_sd(1.0, 1.0)


if __name__ == "__main__":
    unittest.main()
