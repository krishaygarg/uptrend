"""
Unit tests for AlphaPulse backend modules.
"""

import unittest
from backend.quant_engine import calculate_dcf_valuation, calculate_graham_value, analyze_stock
from backend.rebalancer import calculate_rebalance

class TestQuantEngine(unittest.TestCase):
    
    def test_dcf_valuation(self):
        val = calculate_dcf_valuation(
            free_cash_flow=1_000_000_000,
            growth_rate=0.10,
            discount_rate=0.09,
            terminal_growth=0.025,
            years=5,
            shares_outstanding=100_000_000
        )
        self.assertIsNotNone(val)
        self.assertGreater(val, 0)

    def test_graham_value(self):
        val = calculate_graham_value(eps=5.0, growth_rate=0.10)
        self.assertEqual(val, 5.0 * (8.5 + 20.0))

    def test_analyze_stock(self):
        result = analyze_stock("NVDA")
        self.assertEqual(result["ticker"], "NVDA")
        self.assertIn("conviction_score", result)
        self.assertIn("asymmetry_ratio", result)
        self.assertGreaterEqual(result["asymmetry_ratio"], 0.0)

class TestRebalancer(unittest.TestCase):

    def test_rebalance_calculation(self):
        portfolio = {
            "cash_balance": 10000.0,
            "holdings": {
                "JNJ": {"shares": 10, "avg_cost": 150.0}
            }
        }
        stock_analysis_list = [
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corp",
                "current_price": 120.0,
                "conviction_score": 90,
                "asymmetry_ratio": 3.5,
                "margin_of_safety_pct": 25.0
            },
            {
                "ticker": "POWI",
                "company_name": "Power Integrations",
                "current_price": 60.0,
                "conviction_score": 80,
                "asymmetry_ratio": 3.0,
                "margin_of_safety_pct": 30.0
            }
        ]
        result = calculate_rebalance(portfolio, stock_analysis_list)
        self.assertIn("total_equity", result)
        self.assertIn("rebalancing_trades", result)
        self.assertGreater(len(result["rebalancing_trades"]), 0)

if __name__ == "__main__":
    unittest.main()
