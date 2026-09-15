import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def tax_config():
    return {
        "financial_year": "2026-27",
        "last_updated": "2026-09-15",
        "regime": "new",
        "slabs": [
            {"upto": 400000, "rate": 0.0},
            {"upto": 800000, "rate": 0.05},
            {"upto": 1200000, "rate": 0.10},
            {"upto": 1600000, "rate": 0.15},
            {"upto": 2000000, "rate": 0.20},
            {"upto": 2400000, "rate": 0.25},
            {"upto": None, "rate": 0.30}
        ],
        "standard_deduction": 75000,
        "rebate_87a": {
            "max_taxable_income": 1200000,
            "max_rebate": 60000
        },
        "cess_rate": 0.04
    }


@pytest.fixture
def inflation_config():
    return {
        "annual_rate_pct": 6.0,
        "note": "Test fixture"
    }
