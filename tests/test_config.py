"""Unit tests for configuration system and Pydantic schema validation."""

import pytest
import os
import json
import tempfile
from app.config_schema import validate_all_configs, validate_file, ProductsConfig, ConfigValidationError
from scripts.import_research import validate_research_entry, import_research_file


def test_all_config_files_valid():
    """Verify that all production config files pass schema validation."""
    validated = validate_all_configs("config")
    assert "_meta.json" in validated
    assert "macro.json" in validated
    assert "products.json" in validated
    assert "planning_rules.json" in validated
    assert "tax_fy2026_27.json" in validated


def test_invalid_product_returns_fails_validation():
    """Schema rejects products where min_allocation > max_allocation."""
    invalid_data = {
        "products": [
            {
                "name": "Invalid Product",
                "return_pct": 5.0,
                "risk": "low",
                "liquidity": "high",
                "min_allocation_pct": 80.0,
                "max_allocation_pct": 20.0  # Invalid: min > max
            }
        ]
    }
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.json') as f:
        json.dump(invalid_data, f)
        temp_path = f.name

    try:
        with pytest.raises(ConfigValidationError):
            validate_file(temp_path, ProductsConfig)
    finally:
        os.remove(temp_path)


def test_missing_config_file_raises_error():
    """System refuses to start if a mandatory config file is missing."""
    with pytest.raises(ConfigValidationError) as exc:
        validate_all_configs("non_existent_config_dir")
    assert "not found" in str(exc.value).lower() or "missing" in str(exc.value).lower()


def test_research_importer_fails_on_missing_source():
    """Research importer must fail loudly if an entry lacks verifiable source."""
    entry_without_source = {"as_of": "2026-09-15"}
    with pytest.raises(ValueError) as exc:
        validate_research_entry(entry_without_source, "Test Entry")
    assert "missing required 'source'" in str(exc.value)


def test_research_importer_fails_on_missing_as_of():
    """Research importer must fail loudly if an entry lacks as_of date."""
    entry_without_date = {"source": "RBI Bulletin"}
    with pytest.raises(ValueError) as exc:
        validate_research_entry(entry_without_date, "Test Entry")
    assert "missing required 'as_of'" in str(exc.value)
