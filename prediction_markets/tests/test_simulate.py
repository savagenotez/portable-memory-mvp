import random
import unittest

from prediction_markets.simulate import load_config, load_domain_specs, simulate_series


class ConfigTests(unittest.TestCase):
    def test_all_domains_load_and_are_consistent(self):
        specs = load_domain_specs()
        self.assertEqual(
            {s.key for s in specs},
            {"sports_star", "sports_role_player", "weather_precipitation", "politics_poll_share", "systems_throughput"},
        )
        for s in specs:
            with self.subTest(domain=s.key):
                self.assertGreater(s.total_periods, s.observed_periods)
                self.assertGreater(s.stat_max, s.stat_min)
                self.assertGreater(s.goal, 0)
                self.assertLess(s.phi, 1.0)
                self.assertGreater(s.phi, -1.0)

    def test_unknown_config_key_is_rejected(self):
        cfg = load_config()
        cfg["domains"]["sports_star"]["typo_key"] = 1
        with self.assertRaises(ValueError):
            load_domain_specs(cfg)


class SimulationTests(unittest.TestCase):
    def test_values_stay_within_bounds(self):
        for spec in load_domain_specs():
            with self.subTest(domain=spec.key):
                values = simulate_series(spec, random.Random(1), n_periods=500)
                self.assertTrue(all(spec.stat_min <= v <= spec.stat_max for v in values))

    def test_same_seed_same_series(self):
        spec = load_domain_specs()[0]
        a = simulate_series(spec, random.Random(9))
        b = simulate_series(spec, random.Random(9))
        self.assertEqual(a, b)

    def test_mean_matches_deterministic_mean_when_unclipped(self):
        # Politics drifts slowly; over one 60-period horizon it stays well inside [0, 1],
        # so clipping does not bias the average. Average many replicates to shrink noise.
        spec = next(s for s in load_domain_specs() if s.key == "politics_poll_share")
        n = spec.total_periods
        rng = random.Random(5)
        total, count = 0.0, 0
        for _ in range(2000):
            values = simulate_series(spec, rng)
            total += sum(values)
            count += len(values)
        expected = sum(spec.deterministic_mean(t) for t in range(n)) / n
        self.assertAlmostEqual(total / count, expected, delta=0.003)

    def test_weather_precipitation_never_negative(self):
        spec = next(s for s in load_domain_specs() if s.key == "weather_precipitation")
        self.assertTrue(all(v >= 0.0 for v in simulate_series(spec, random.Random(2), n_periods=300)))


if __name__ == "__main__":
    unittest.main()
