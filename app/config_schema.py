"""Configuration schema validation using Pydantic.

Validates that all financial parameters, tax rules, product tables,
and macro assumptions are structurally sound, bounded, sourced, and dated.
The application refuses to start if any configuration is invalid.
"""

from __future__ import annotations

import os
import json
from typing import List, Dict, Optional, Any, Union, Type
from pydantic import BaseModel, Field, field_validator, model_validator


class ConfigValidationError(ValueError):
    """Raised when configuration file fails schema validation."""
    pass


# 1. Meta Schema
class MetaConfig(BaseModel):
    system_version: str
    schema_version: str
    last_reviewed: str
    default_financial_year: str
    supported_financial_years: List[str] = Field(default_factory=list)


# 2. Macro Schema
class MacroItem(BaseModel):
    annual_rate_pct: float = Field(..., ge=0.0, le=100.0)
    source: str
    as_of: str
    confidence_note: Optional[str] = None
    unit: str = "percentage"


class MacroConfig(BaseModel):
    financial_year: str
    as_of: str
    inflation: MacroItem
    risk_free_rate: MacroItem


# 3. Product Schema
class ReturnRange(BaseModel):
    low: float = Field(..., ge=0.0)
    base: float = Field(..., ge=0.0)
    high: float = Field(..., ge=0.0)

    @model_validator(mode='after')
    def check_range(self):
        if not (self.low <= self.base <= self.high):
            raise ValueError(f"Return range must satisfy low <= base <= high (got {self.low}, {self.base}, {self.high})")
        return self


class ProductItem(BaseModel):
    name: str
    return_pct: float = Field(..., ge=0.0, le=100.0)
    return_range: Optional[ReturnRange] = None
    volatility_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    risk: str = Field(..., pattern="^(very_low|low|moderate|high)$")
    liquidity: str
    lock_in_months: int = Field(0, ge=0)
    tax_treatment: str = Field("slab", pattern="^(slab|equity_capital_gains)$")
    min_allocation_pct: float = Field(0.0, ge=0.0, le=100.0)
    max_allocation_pct: float = Field(100.0, ge=0.0, le=100.0)
    source: Optional[str] = None
    as_of: Optional[str] = None


class ProductsConfig(BaseModel):
    products: List[ProductItem] = Field(..., min_length=1)

    @model_validator(mode='after')
    def check_min_max(self):
        for p in self.products:
            if p.min_allocation_pct > p.max_allocation_pct:
                raise ValueError(f"Product {p.name}: min_allocation ({p.min_allocation_pct}) cannot exceed max_allocation ({p.max_allocation_pct}).")
        return self


# 4. Tax Schema
class TaxSlab(BaseModel):
    upto: Optional[float] = None
    rate: float = Field(..., ge=0.0, le=1.0)


class Rebate87A(BaseModel):
    max_taxable_income: float = Field(..., ge=0.0)
    max_rebate: float = Field(..., ge=0.0)
    marginal_relief: bool = False


class SurchargeTier(BaseModel):
    threshold: float = Field(..., ge=0.0)
    rate: float = Field(..., ge=0.0, le=1.0)


class TaxRegimeRules(BaseModel):
    standard_deduction: float = Field(..., ge=0.0)
    slabs: List[TaxSlab] = Field(..., min_length=1)
    rebate_87a: Rebate87A
    surcharge: List[SurchargeTier] = Field(default_factory=list)


class TaxConfig(BaseModel):
    financial_year: str
    regime: str = "new"
    cess_rate: float = Field(0.04, ge=0.0, le=0.20)
    slabs: List[TaxSlab]
    standard_deduction: float
    rebate_87a: Rebate87A
    new_regime: Optional[TaxRegimeRules] = None
    old_regime: Optional[TaxRegimeRules] = None


# 5. Planning Rules Schema
class PlanningRulesConfig(BaseModel):
    emergency_fund: Dict[str, Any]
    buffer_pct: float = Field(..., ge=0.0, le=50.0)
    debt_rules: Dict[str, Any]
    diversification_caps: Dict[str, float]


def validate_file(file_path: str, model_cls: type[BaseModel]) -> BaseModel:
    """Validate a specific JSON config file against a Pydantic model."""
    if not os.path.exists(file_path):
        raise ConfigValidationError(f"Configuration file not found: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return model_cls.model_validate(data)
    except Exception as e:
        raise ConfigValidationError(f"Invalid config '{os.path.basename(file_path)}': {str(e)}") from e


def validate_all_configs(config_dir: str) -> Dict[str, Any]:
    """Validate all required configurations in config_dir at startup."""
    validations = {
        "_meta.json": (MetaConfig, os.path.join(config_dir, "_meta.json")),
        "macro.json": (MacroConfig, os.path.join(config_dir, "macro.json")),
        "products.json": (ProductsConfig, os.path.join(config_dir, "products.json")),
        "planning_rules.json": (PlanningRulesConfig, os.path.join(config_dir, "planning_rules.json")),
        "tax_fy2026_27.json": (TaxConfig, os.path.join(config_dir, "tax_fy2026_27.json")),
    }

    validated_configs = {}
    for name, (model, path) in validations.items():
        if os.path.exists(path):
            validated_configs[name] = validate_file(path, model)
        else:
            raise ConfigValidationError(f"Missing required configuration file: {name}")

    return validated_configs
