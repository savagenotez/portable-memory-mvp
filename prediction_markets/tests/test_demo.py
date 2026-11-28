import unittest

from prediction_markets.backtest import synthetic_sports_events
from prediction_markets.run_demo import build_report
from prediction_markets.simulate import load_domain_specs


class BacktestTests(unittest.TestCase):
    def test_events_are_valid_and_reproducible(self):
        spec = next(s for s in load_domain_specs() if s.key == "sports_star")
        a = synthetic_sports_events(spec, warmup=10, market_noise_sd=0.05, seasons=2, seed=3)
        b = synthetic_sports_events(spec, warmup=10, market_noise_sd=0.05, seasons=2, seed=3)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 2 * (spec.total_periods - 10))
        for e in a:
            self.assertTrue(0.0 <= e.model_prob <= 1.0)
            self.assertTrue(0.0 < e.market_price < 1.0)
            self.assertIn(e.outcome, (0, 1))


class DemoSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report(quick=True)

    def test_report_has_every_section(self):
        self.assertIn("SIMULATED DATA ONLY", self.report["disclaimer"])
        self.assertEqual(len(self.report["domains"]), 5)
        self.assertIsNotNone(self.report["forecast"])
        self.assertIsNotNone(self.report["paper_trading"])

    def test_percentages_are_in_range(self):
        for key, d in self.report["domains"].items():
            with self.subTest(domain=key):
                pct = d["checkpoint"]["attainment_probability_pct"]
                self.assertTrue(0.0 <= pct <= 100.0)
                cal = d["calibration"]
                self.assertTrue(0.0 <= cal["predicted_mean_pct"] <= 100.0)
                self.assertTrue(0.0 <= cal["realized_rate_pct"] <= 100.0)

    def test_paper_trading_is_labelled_synthetic(self):
        for name, pt in self.report["paper_trading"].items():
            with self.subTest(scenario=name):
                self.assertEqual(pt["events_source"], "synthetic")

    def test_fair_market_has_no_mispricing_by_construction(self):
        self.assertEqual(self.report["paper_trading"]["fair_market"]["market_noise_sd"], 0.0)


if __name__ == "__main__":
    unittest.main()
