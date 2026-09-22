"""Domain data models for BankEase financial calculation engine.

Pure dataclasses with self-validation and serialization.
Zero external framework dependencies (pure Python).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Any, Optional
from app.engine.money import to_decimal, round_inr, format_inr


class ValidationError(ValueError):
    """Raised when domain model validation fails."""
    pass


@dataclass
class CalcStep:
    """Represents a single traceable step in the financial calculation pipeline.
    
    This is the single source of truth used for UI waterfall displays,
    audit traces, and LLM explanation prompts.
    """
    step_id: str
    label: str
    formula: str
    inputs: Dict[str, Any]
    result: Decimal
    note: str
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "formula": self.formula,
            "inputs": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in self.inputs.items()},
            "result": str(round_inr(self.result, places=2)),
            "formatted_result": format_inr(self.result),
            "note": self.note,
            "category": self.category
        }


@dataclass
class UserProfile:
    """User demographics and preferences."""
    age: int = 30
    city_tier: str = "tier_1"  # tier_1, tier_2, tier_3
    adults: int = 1
    dependents: int = 0
    employment_type: str = "salaried"  # salaried, self_employed, variable
    income_stability: str = "stable"  # stable, moderate, variable
    risk_profile: str = "balanced"  # conservative, balanced, growth
    tax_regime_preference: str = "auto"  # auto, new, old

    def __post_init__(self):
        if not (18 <= self.age <= 100):
            raise ValidationError(f"Age must be between 18 and 100 (got {self.age}).")
        if self.city_tier not in {"tier_1", "tier_2", "tier_3"}:
            raise ValidationError(f"Invalid city tier '{self.city_tier}'. Must be tier_1, tier_2, or tier_3.")
        if self.adults < 1:
            raise ValidationError(f"Household must have at least 1 adult.")
        if self.dependents < 0:
            raise ValidationError(f"Dependents cannot be negative.")
        if self.employment_type not in {"salaried", "self_employed", "variable"}:
            raise ValidationError(f"Invalid employment type '{self.employment_type}'.")
        if self.income_stability not in {"stable", "moderate", "variable"}:
            raise ValidationError(f"Invalid income stability '{self.income_stability}'.")
        if self.risk_profile not in {"conservative", "balanced", "growth"}:
            raise ValidationError(f"Invalid risk profile '{self.risk_profile}'.")
        if self.tax_regime_preference not in {"auto", "new", "old"}:
            raise ValidationError(f"Invalid tax regime preference '{self.tax_regime_preference}'.")


@dataclass
class Income:
    """Income components with payroll deduction tracking."""
    gross_annual: Decimal
    basic_annual: Decimal = Decimal('0.00')
    hra_annual: Decimal = Decimal('0.00')
    special_allowance_annual: Decimal = Decimal('0.00')
    employer_nps_annual: Decimal = Decimal('0.00')
    epf_employee_annual: Decimal = Decimal('0.00')
    professional_tax_annual: Decimal = Decimal('0.00')
    other_annual: Decimal = Decimal('0.00')

    def __post_init__(self):
        self.gross_annual = to_decimal(self.gross_annual)
        self.basic_annual = to_decimal(self.basic_annual)
        self.hra_annual = to_decimal(self.hra_annual)
        self.special_allowance_annual = to_decimal(self.special_allowance_annual)
        self.employer_nps_annual = to_decimal(self.employer_nps_annual)
        self.epf_employee_annual = to_decimal(self.epf_employee_annual)
        self.professional_tax_annual = to_decimal(self.professional_tax_annual)
        self.other_annual = to_decimal(self.other_annual)

        if self.gross_annual < 0:
            raise ValidationError(f"Gross annual income cannot be negative (got {self.gross_annual}).")

    @property
    def gross_monthly(self) -> Decimal:
        return round_inr(self.gross_annual / Decimal('12'), places=2)

    @property
    def mandatory_payroll_deductions_monthly(self) -> Decimal:
        """EPF and Professional tax already deducted at source monthly."""
        return round_inr((self.epf_employee_annual + self.professional_tax_annual) / Decimal('12'), places=2)


@dataclass
class ExpenseItem:
    """Individual expense line item."""
    name: str
    amount: Decimal
    category: str = "essential"  # essential, discretionary, annual_irregular

    def __post_init__(self):
        self.amount = to_decimal(self.amount)
        if self.amount < 0:
            raise ValidationError(f"Expense amount for '{self.name}' cannot be negative.")
        if self.category not in {"essential", "discretionary", "annual_irregular"}:
            raise ValidationError(f"Invalid category '{self.category}'.")


@dataclass
class Expenses:
    """Aggregated expenses."""
    items: List[ExpenseItem] = field(default_factory=list)

    @property
    def total_essential_monthly(self) -> Decimal:
        return sum((item.amount for item in self.items if item.category == "essential"), Decimal('0.00'))

    @property
    def total_discretionary_monthly(self) -> Decimal:
        return sum((item.amount for item in self.items if item.category == "discretionary"), Decimal('0.00'))

    @property
    def total_sinking_fund_monthly(self) -> Decimal:
        """Annual/irregular expenses converted to monthly sinking fund."""
        annual_total = sum((item.amount for item in self.items if item.category == "annual_irregular"), Decimal('0.00'))
        return round_inr(annual_total / Decimal('12'), places=2)

    @property
    def total_monthly(self) -> Decimal:
        return self.total_essential_monthly + self.total_discretionary_monthly + self.total_sinking_fund_monthly


@dataclass
class DebtItem:
    """Outstanding loan or credit card."""
    name: str
    debt_type: str  # credit_card, personal_loan, car_loan, home_loan, education_loan, other
    outstanding: Decimal
    interest_rate_pct: Decimal
    emi: Decimal
    tenure_months_left: int = 0
    is_secured: bool = False
    prepayment_penalty_pct: Decimal = Decimal('0.0')

    def __post_init__(self):
        self.outstanding = to_decimal(self.outstanding)
        self.interest_rate_pct = to_decimal(self.interest_rate_pct)
        self.emi = to_decimal(self.emi)
        self.prepayment_penalty_pct = to_decimal(self.prepayment_penalty_pct)

        if self.outstanding < 0:
            raise ValidationError("Outstanding balance cannot be negative.")
        if self.interest_rate_pct < 0:
            raise ValidationError("Interest rate cannot be negative.")
        if self.emi < 0:
            raise ValidationError("EMI cannot be negative.")


@dataclass
class GoalItem:
    """Financial goal target."""
    name: str
    target_amount: Decimal
    horizon_months: int
    priority: int = 1

    def __post_init__(self):
        self.target_amount = to_decimal(self.target_amount)
        if self.target_amount <= 0:
            raise ValidationError(f"Goal target amount must be positive (got {self.target_amount}).")
        if self.horizon_months <= 0:
            raise ValidationError(f"Goal horizon in months must be positive (got {self.horizon_months}).")


@dataclass
class TaxDeductions:
    """Tax deductions for Old Regime and allowed New Regime sections."""
    sec_80c: Decimal = Decimal('0.00')           # Max 1.5L
    sec_80d: Decimal = Decimal('0.00')           # Health insurance (25k-1L)
    hra_exemption: Decimal = Decimal('0.00')     # Actual exempt HRA
    home_loan_interest_24b: Decimal = Decimal('0.00')  # Max 2L for self-occupied
    sec_80ccd_1b: Decimal = Decimal('0.00')      # Additional NPS max 50k
    employer_nps_80ccd_2: Decimal = Decimal('0.00') # Allowed in both Old and New (up to 14% govt / 10% private)

    def __post_init__(self):
        self.sec_80c = to_decimal(self.sec_80c)
        self.sec_80d = to_decimal(self.sec_80d)
        self.hra_exemption = to_decimal(self.hra_exemption)
        self.home_loan_interest_24b = to_decimal(self.home_loan_interest_24b)
        self.sec_80ccd_1b = to_decimal(self.sec_80ccd_1b)
        self.employer_nps_80ccd_2 = to_decimal(self.employer_nps_80ccd_2)
