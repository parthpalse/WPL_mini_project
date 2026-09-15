"""Optimizer engine tests."""
import pytest
from app.engine.optimizer import optimize_allocation


@pytest.fixture
def product_config():
    return {
        "products": [
            {"name": "Savings", "return_pct": 3.5, "risk": "very_low", "liquidity": "high"},
            {"name": "RD", "return_pct": 6.5, "risk": "low", "liquidity": "medium"},
            {"name": "FD", "return_pct": 7.0, "risk": "low", "liquidity": "low_medium"},
            {"name": "Debt Fund", "return_pct": 7.5, "risk": "moderate", "liquidity": "medium_high"},
            {"name": "Equity Fund", "return_pct": 12.0, "risk": "high", "liquidity": "high"}
        ]
    }


class TestOptimizer:
    def test_zero_surplus(self, product_config):
        """Test with zero surplus."""
        res = optimize_allocation(0, product_config=product_config)
        assert res['safe'] == {}
        assert res['balanced'] == {}
        assert res['growth'] == {}

    def test_strategies(self, product_config):
        """Test the 3 strategies yield valid allocations."""
        surplus = 10000
        res = optimize_allocation(surplus, product_config=product_config)
        
        for strategy in ['safe', 'balanced', 'growth']:
            allocation = res[strategy]
            assert allocation, f"{strategy} allocation is empty"
            
            total_pct = sum(item['percentage'] for item in allocation.values())
            total_amt = sum(item['amount'] for item in allocation.values())
            
            # Allow tiny floating point differences
            assert pytest.approx(total_pct, abs=0.2) == 100.0
            assert pytest.approx(total_amt, abs=1.0) == surplus

        # Specific constraints checks
        # Safe should have 0% Equity
        assert 'Equity Fund' not in res['safe']
        
        # Growth should have more equity than Safe
        growth_equity = res['growth'].get('Equity Fund', {}).get('percentage', 0)
        safe_equity = res['safe'].get('Equity Fund', {}).get('percentage', 0)
        assert growth_equity > safe_equity
