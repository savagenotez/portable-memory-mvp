import unittest

from prediction_markets.markets import (
    BetPolicy,
    MarketEvent,
    ev_per_unit,
    events_from_rows,
    kelly_fraction,
    paper_trade,
    wilson_interval,
)


class EdgeAndSizingTests(unittest.TestCase):
    def test_expected_value_known_case(self):
        # p = 0.6 at price 0.5, no fee: EV = 0.6 * 1 - 0.4 = 0.2 per unit staked
        self.assertAlmostEqual(ev_per_unit(0.6, 0.5), 0.2)

    def test_kelly_known_case(self):
        self.assertAlmostEqual(kelly_fraction(0.6, 0.5), 0.2)

    def test_kelly_zero_without_edge(self):
        self.assertEqual(kelly_fraction(0.4, 0.5), 0.0)

    def test_fee_reduces_ev(self):
        self.assertLess(ev_per_unit(0.6, 0.5, fee_rate=0.1), ev_per_unit(0.6, 0.5))

    def test_no_bets_when_model_equals_market(self):
        events = [MarketEvent(f"e{i}", 0.4, 0.4, i % 2) for i in range(20)]
        result = paper_trade(events, BetPolicy(edge_threshold=0.0))
        self.assertEqual(result["bets"], 0)
        self.assertIsNone(result["win_rate"])

    def test_profitable_when_model_has_real_edge_on_known_outcomes(self):
        events = [MarketEvent(f"e{i}", 0.7, 0.4, 1) for i in range(10)]
        result = paper_trade(events, BetPolicy(bankroll=1000.0, edge_threshold=0.01))
        self.assertEqual(result["bets"], 10)
        self.assertEqual(result["win_rate"], 1.0)
        self.assertGreater(result["final_bankroll"], 1000.0)
        self.assertGreater(result["roi"], 0.0)

    def test_stake_cap_respected(self):
        events = [MarketEvent("e", 0.99, 0.1, 1)]
        policy = BetPolicy(bankroll=1000.0, kelly_fraction=1.0, max_stake_fraction=0.05, edge_threshold=0.0)
        result = paper_trade(events, policy)
        self.assertAlmostEqual(result["staked"], 50.0)


class WinRateTests(unittest.TestCase):
    def test_wilson_known_value(self):
        lo, hi = wilson_interval(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)

    def test_wilson_empty(self):
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))

    def test_win_rate_is_not_profit(self):
        # Betting favourites at 0.9 with a 90% win rate still loses after a 2% fee in this setup.
        events = [MarketEvent(f"e{i}", 0.95, 0.9, 1 if i < 9 else 0) for i in range(10)]
        result = paper_trade(events, BetPolicy(bankroll=1000.0, edge_threshold=0.0, fee_rate=0.02))
        self.assertEqual(result["bets"], 10)
        self.assertAlmostEqual(result["win_rate"], 0.9)
        self.assertLess(result["roi"], 0.0)


class InputValidationTests(unittest.TestCase):
    def good(self, **kw):
        row = {"event_id": "e1", "model_prob": "0.6", "market_price": "0.5", "outcome": "1"}
        row.update(kw)
        return row

    def test_valid_row_parses(self):
        (event,) = events_from_rows([self.good()])
        self.assertEqual(event.outcome, 1)

    def test_price_bounds_enforced(self):
        with self.assertRaises(ValueError):
            events_from_rows([self.good(market_price="1.0")])
        with self.assertRaises(ValueError):
            events_from_rows([self.good(market_price="0")])

    def test_probability_bounds_enforced(self):
        with self.assertRaises(ValueError):
            events_from_rows([self.good(model_prob="1.2")])

    def test_outcome_must_be_binary(self):
        with self.assertRaises(ValueError):
            events_from_rows([self.good(outcome="2")])

    def test_missing_column_value_reported(self):
        with self.assertRaises(ValueError):
            events_from_rows([self.good(model_prob="")])


if __name__ == "__main__":
    unittest.main()
