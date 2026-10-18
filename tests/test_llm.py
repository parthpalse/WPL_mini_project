import unittest
from unittest.mock import patch, MagicMock
import json
from app.llm.explain import explain_plan, verify_numbers, generate_deterministic_explanation

class TestLLMExplain(unittest.TestCase):
    def setUp(self):
        self.engine_output = {
            'summary': {
                'monthly_surplus': 15000,
                'net_monthly_income': 50000,
                'total_monthly_expenses': 30000,
                'emergency_fund_monthly': 2000,
                'safety_buffer_monthly': 3000,
                'surplus_is_positive': True
            },
            'trace': []
        }

    @patch('app.llm.explain.requests.post')
    def test_explain_plan_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': json.dumps({
                "headline": "You have a surplus of 15000.",
                "what_this_means": "Income is 50000 and expenses are 30000.",
                "three_key_actions": ["Save 2000 for emergency."],
                "watch_outs": "Be careful."
            })
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Clear cache to ensure we hit the mock
        import app.llm.explain
        from app.llm import explain
        explain._CACHE.clear()

        result = explain_plan(self.engine_output)
        self.assertEqual(result['source'], 'ai')
        self.assertEqual(result['headline'], "You have a surplus of 15000.")

    @patch('app.llm.explain.requests.post')
    def test_explain_plan_timeout_fallback(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.Timeout

        from app.llm import explain
        explain._CACHE.clear()

        result = explain_plan(self.engine_output)
        self.assertEqual(result['source'], 'deterministic')
        self.assertIn('15,000', result['headline'])

    @patch('app.llm.explain.requests.post')
    def test_explain_plan_hallucination_fallback(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': json.dumps({
                "headline": "You have a surplus of 999999.", # Hallucinated number
                "what_this_means": "",
                "three_key_actions": [],
                "watch_outs": ""
            })
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        from app.llm import explain
        explain._CACHE.clear()

        result = explain_plan(self.engine_output)
        self.assertEqual(result['source'], 'deterministic')
        self.assertEqual(result.get('note'), 'Standard explanation used (AI number verification rejected invalid numbers).')

    def test_twenty_scenarios_eval_deterministic_safety(self):
        """Phase 3.7: 20 scenarios eval checking explanation formatting and zero hallucinated numbers."""
        from app.llm import explain
        from app.engine.money import format_inr

        scenarios = [
            {"monthly_surplus": 1000, "net_monthly_income": 25000, "total_monthly_expenses": 23000, "surplus_is_positive": True},
            {"monthly_surplus": -5000, "net_monthly_income": 30000, "total_monthly_expenses": 35000, "surplus_is_positive": False},
            {"monthly_surplus": 12500, "net_monthly_income": 50000, "total_monthly_expenses": 35000, "surplus_is_positive": True},
            {"monthly_surplus": 25000, "net_monthly_income": 75000, "total_monthly_expenses": 45000, "surplus_is_positive": True},
            {"monthly_surplus": 45000, "net_monthly_income": 100000, "total_monthly_expenses": 50000, "surplus_is_positive": True},
            {"monthly_surplus": -12000, "net_monthly_income": 60000, "total_monthly_expenses": 72000, "surplus_is_positive": False},
            {"monthly_surplus": 85000, "net_monthly_income": 150000, "total_monthly_expenses": 60000, "surplus_is_positive": True},
            {"monthly_surplus": 120000, "net_monthly_income": 200000, "total_monthly_expenses": 70000, "surplus_is_positive": True},
            {"monthly_surplus": 0, "net_monthly_income": 40000, "total_monthly_expenses": 40000, "surplus_is_positive": False},
            {"monthly_surplus": 500, "net_monthly_income": 18000, "total_monthly_expenses": 17000, "surplus_is_positive": True},
            {"monthly_surplus": 320000, "net_monthly_income": 500000, "total_monthly_expenses": 150000, "surplus_is_positive": True},
            {"monthly_surplus": -25000, "net_monthly_income": 80000, "total_monthly_expenses": 105000, "surplus_is_positive": False},
            {"monthly_surplus": 62000, "net_monthly_income": 120000, "total_monthly_expenses": 52000, "surplus_is_positive": True},
            {"monthly_surplus": 18000, "net_monthly_income": 65000, "total_monthly_expenses": 43000, "surplus_is_positive": True},
            {"monthly_surplus": 2100, "net_monthly_income": 32000, "total_monthly_expenses": 28000, "surplus_is_positive": True},
            {"monthly_surplus": -1500, "net_monthly_income": 22000, "total_monthly_expenses": 23500, "surplus_is_positive": False},
            {"monthly_surplus": 750000, "net_monthly_income": 1000000, "total_monthly_expenses": 200000, "surplus_is_positive": True},
            {"monthly_surplus": 35000, "net_monthly_income": 90000, "total_monthly_expenses": 50000, "surplus_is_positive": True},
            {"monthly_surplus": 4800, "net_monthly_income": 38000, "total_monthly_expenses": 31000, "surplus_is_positive": True},
            {"monthly_surplus": -8000, "net_monthly_income": 45000, "total_monthly_expenses": 53000, "surplus_is_positive": False},
        ]

        self.assertEqual(len(scenarios), 20)
        for i, sc in enumerate(scenarios, start=1):
            engine_data = {
                'summary': {
                    'monthly_surplus': sc['monthly_surplus'],
                    'net_monthly_income': sc['net_monthly_income'],
                    'total_monthly_expenses': sc['total_monthly_expenses'],
                    'emergency_fund_monthly': max(0, int(sc['monthly_surplus'] * 0.2)) if sc['surplus_is_positive'] else 0,
                    'safety_buffer_monthly': int(sc['net_monthly_income'] * 0.05),
                    'surplus_is_positive': sc['surplus_is_positive']
                },
                'trace': []
            }
            explain._CACHE.clear()
            res = generate_deterministic_explanation(engine_data)
            self.assertEqual(res['source'], 'deterministic')
            self.assertTrue(len(res['headline']) > 0)
            self.assertTrue(len(res['three_key_actions']) >= 2)
            # Verify numbers: all numbers in explanation must come from engine data
            full_text = f"{res['headline']} {res['what_this_means']} {' '.join(res['three_key_actions'])} {res['watch_outs']}"
            self.assertTrue(verify_numbers(full_text, engine_data), f"Scenario {i} failed number verification: {full_text}")


if __name__ == '__main__':
    unittest.main()

