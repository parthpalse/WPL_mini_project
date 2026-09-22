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

if __name__ == '__main__':
    unittest.main()
