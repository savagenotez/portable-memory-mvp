import math
import unittest

from prediction_markets.stats import engine as E


class DistTests(unittest.TestCase):
    def test_poisson_matches_closed_form(self):
        d = E.nb(2.5)
        self.assertAlmostEqual(d.prob(3), math.exp(-2.5) * 2.5 ** 3 / 6, places=9)
        self.assertAlmostEqual(d.mean, 2.5, places=6)

    def test_negative_binomial_is_wider_than_poisson(self):
        self.assertGreater(E.nb(5.0, 2.0).sd, E.nb(5.0).sd)
        self.assertAlmostEqual(E.nb(5.0, 2.0).mean, 5.0, places=5)
        self.assertAlmostEqual(math.exp(E.nb_logpmf(4, 5.0, 2.0)), E.nb(5.0, 2.0).prob(4), places=9)

    def test_large_means_do_not_underflow(self):
        d = E.nb(900.0, 8.0)
        self.assertAlmostEqual(d.mean, 900.0, delta=2.0)

    def test_over_under_and_push(self):
        d = E.Dist([0.2, 0.3, 0.5])                       # values 0, 1, 2
        self.assertAlmostEqual(d.prob_over(1.5), 0.5)
        self.assertAlmostEqual(d.prob_under(1.5), 0.5)
        self.assertAlmostEqual(d.over_no_push(1), 0.5 / 0.7)   # landing on 1 is a push
        self.assertEqual(d.quantile(0.5), 1)

    def test_sum_difference_and_scale(self):
        a, b = E.Dist([0.5, 0.5]), E.Dist([0.5, 0.5])
        self.assertEqual([round(p, 3) for p in E.add(a, b).pmf], [0.25, 0.5, 0.25])
        m = E.subtract(a, b)
        self.assertEqual((m.offset, [round(p, 3) for p in m.pmf]), (-1, [0.25, 0.5, 0.25]))
        s = E.scale(a, 3)
        self.assertAlmostEqual(s.prob(3), 0.5)
        self.assertAlmostEqual(s.mean, 1.5)

    def test_compound_touchdowns(self):
        # exactly 2 touchdowns, each 6 plus an extra point made with probability 0.9
        pts = E.compound(E.point(2), E.Dist([0.1, 0.9], 6))
        self.assertAlmostEqual(pts.prob(14), 0.81)
        self.assertAlmostEqual(pts.prob(12), 0.01)
        self.assertAlmostEqual(pts.mean, 13.8)

    def test_period_share_keeps_the_mean(self):
        self.assertAlmostEqual(E.period(4.0, 3.0, 0.25).mean, 1.0, places=5)


class MakesTests(unittest.TestCase):
    def test_makes_mean_is_attempts_times_rate(self):
        f = E.makes(E.nb(3.0), 8.0, 2.0)
        self.assertAlmostEqual(f.makes.mean, 3.0 * 0.8, places=4)
        self.assertAlmostEqual(f.pct_mean, 0.8)
        self.assertAlmostEqual(f.p_no_attempt, math.exp(-3.0), places=6)

    def test_more_evidence_narrows_the_percentage(self):
        wide = E.makes(E.point(10), 4.0, 1.0)
        narrow = E.makes(E.point(10), 400.0, 100.0)
        self.assertGreater(wide.makes.sd, narrow.makes.sd)


class TrackerTests(unittest.TestCase):
    def test_shrinks_toward_the_prior_and_learns(self):
        t = E.DecayedRate(halflife=8, k0=4)
        self.assertEqual(t.rate("x", 2.0), 2.0)               # unseen: the prior
        for _ in range(40):
            t.update("x", 6.0)
        lam = 0.5 ** (1.0 / 8)
        w = (1 - lam ** 40) / (1 - lam)                       # decay caps the evidence at about 12 games
        self.assertAlmostEqual(t.rate("x", 2.0), (4 * 2.0 + w * 6.0) / (4 + w), places=6)
        t2 = E.DecayedRate(halflife=8, k0=4)
        t2.update("x", 6.0)
        self.assertAlmostEqual(t2.rate("x", 2.0), (4 * 2.0 + 6.0) / 5.0)

    def test_beta_for_make_rates(self):
        t = E.DecayedRate(halflife=1e9, k0=10)
        t.update("k", 8, 10)
        a, b = t.beta("k", 0.5)
        self.assertAlmostEqual(a, 13.0)
        self.assertAlmostEqual(b, 7.0)

    def test_fit_size_prefers_poisson_for_poisson_like_data(self):
        pairs = [(3.0, k) for k in (1, 2, 2, 3, 3, 3, 4, 4, 5)]
        self.assertGreaterEqual(E.fit_size(pairs), 25)
        wide = [(3.0, k) for k in (0, 0, 0, 0, 1, 2, 6, 9, 9)]
        self.assertLessEqual(E.fit_size(wide), 2)


if __name__ == "__main__":
    unittest.main()
