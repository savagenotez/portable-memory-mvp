import math
import random
import unittest

from prediction_markets.nfl import factors as F
from prediction_markets.stats import engine as E


class ShapleyTests(unittest.TestCase):
    def test_parts_add_up_to_the_miss(self):
        proj, act = (64.0, 0.81, 0.14), (61.0, 0.38, 0.086)
        split = F.shapley(proj, act)
        self.assertAlmostEqual(sum(split), math.prod(act) - math.prod(proj), places=9)
        self.assertEqual(max(range(3), key=lambda i: abs(split[i])), 1)       # playing time explains most

    def test_unchanged_factor_gets_nothing(self):
        self.assertAlmostEqual(F.shapley((2, 3, 4), (1, 3, 2))[1], 0.0)


class DecisionTests(unittest.TestCase):
    def test_narrowest_range_reaches_the_level(self):
        d = E.nb(6.0, 4.0)
        lo, hi, mass = d.narrowest(0.8)
        self.assertGreaterEqual(mass, 0.8)
        self.assertLessEqual(hi - lo, d.interval(0.8)[1] - d.interval(0.8)[0])

    def test_exact_number_only_when_confident(self):
        self.assertEqual(F.decide(E.Dist([0.1, 0.7, 0.2]), None)["exact"], 1)
        self.assertIsNone(F.decide(E.nb(6.0), None)["exact"])

    def test_no_call_below_the_confidence_rule(self):
        close = F.decide(E.nb(4.4), 4.5)
        self.assertIsNone(close["call"])
        sure = F.decide(E.nb(9.0), 4.5)
        self.assertEqual(sure["call"], "over")
        self.assertGreaterEqual(sure["confidence"], F.CONF_CALL)


class FitTests(unittest.TestCase):
    def test_poisson_regression_recovers_effects(self):
        rng = random.Random(3)
        rows = []
        for _ in range(4000):
            z = [rng.uniform(-1, 1), float(rng.random() < 0.3)]
            mu = math.exp(math.log(3.0) + 0.4 * z[0] - 0.5 * z[1])
            k, p, u = 0, math.exp(-mu), rng.random()
            c = p
            while u > c:
                k += 1
                p *= mu / k
                c += p
            rows.append((math.log(3.0), z, k))
        b, cov = F.fit_poisson(rows)
        self.assertAlmostEqual(b[1], 0.4, delta=0.06)
        self.assertAlmostEqual(b[2], -0.5, delta=0.08)
        self.assertGreater(cov[1][1], 0)

    def test_range_reasons_add_up(self):
        r = {"volume": 64.0, "share": 0.8, "share_var": 0.02, "usage": 0.12, "usage_shape": 40.0,
             "z": [0.0] * 6, "eff": 8.0, "eff_var": 90.0, "eff_n": 60.0}
        p = F.projection(r, [0.0] * 7, [[0.0] * 7 for _ in range(7)], 0.01, 0.05)
        self.assertAlmostEqual(p["var"], sum(p["parts"].values()))
        self.assertAlmostEqual(p["mu"], 64 * 0.8 * 0.12)
        y = F.yards_projection(r, p)
        self.assertAlmostEqual(y["mu"], p["mu"] * 8.0)


if __name__ == "__main__":
    unittest.main()
