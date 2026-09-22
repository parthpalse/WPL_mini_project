# BankEase — Methodology

This document describes every formula used in the BankEase financial planning engine,
linked to the corresponding test and the authoritative source.

---

## 1. Tax Calculation (`app/engine/tax.py`)

### 1.1 New Tax Regime (Default — Section 115BAC, FY 2026-27)

| Taxable Income Slab | Rate |
|---|---|
| Up to ₹4,00,000 | 0% |
| ₹4,00,001 – ₹8,00,000 | 5% |
| ₹8,00,001 – ₹12,00,000 | 10% |
| ₹12,00,001 – ₹16,00,000 | 15% |
| ₹16,00,001 – ₹20,00,000 | 20% |
| ₹20,00,001 – ₹24,00,000 | 25% |
| Above ₹24,00,000 | 30% |

**Source:** Finance Act 2026-27, Section 115BAC.

### 1.2 Section 87A Rebate (New Regime)
- Full rebate of up to ₹25,000 if taxable income ≤ ₹12,75,000.
- **Marginal Relief:** If income slightly exceeds the threshold, tax is capped at `income − 12,75,000`. This prevents a cliff-edge.

**Test:** `tests/test_golden_scenarios.py::test_scenario_5_just_above_rebate_cutoff_marginal_relief`

### 1.3 Surcharges

| Income Range | Surcharge Rate |
|---|---|
| ₹50L – ₹1 Cr | 10% |
| ₹1 Cr – ₹2 Cr | 15% |
| ₹2 Cr – ₹5 Cr | 25% |
| Above ₹5 Cr | 37% |

### 1.4 Health & Education Cess
4% on (tax + surcharge).

---

## 2. Monthly Surplus (`app/engine/max_investment.py`)

```
Net Monthly Income = Gross Annual Income / 12 − Monthly Tax
Monthly Surplus = Net Monthly Income − Total Monthly Expenses − Safety Buffer − Emergency Fund Contribution
```

All values computed using `decimal.Decimal` (zero floating-point rounding).

**Test:** `tests/test_max_investment.py`

---

## 3. Emergency Fund (`app/engine/emergency_fund.py`)

```
Target = Monthly Expenses × Emergency Months (default: 6)
Monthly Contribution = (Target − Existing Fund) / Months to Fund (default: 12)
```

Emergency fund investments are restricted to liquid instruments only (savings account, liquid funds, short FD).

---

## 4. Optimizer (`app/engine/optimizer.py`)

Uses **scipy.optimize.linprog** (linear programming) to maximise expected post-tax returns subject to:
- Allocations sum exactly to monthly investable amount.
- Per-product min/max allocation bounds (from `config/products.json`).
- Diversification cap: no single product exceeds its `max_allocation` fraction.
- Horizon rules: `<12m → liquid only; 1-3y → short debt; 3-5y → debt+hybrid; 5y+ → equity-tilted`.
- Risk cap: max equity percentage per risk profile.

If the LP is infeasible (rare edge case), falls back to a deterministic rule-based allocation.

**Sanity check:** Optimizer result is compared to a 100% FD benchmark. If worse, the benchmark is returned.

**Test:** `tests/test_optimizer.py`, `tests/test_properties.py`

---

## 5. Projections (`app/engine/inflation.py`)

### 5.1 SIP Future Value (Annuity Due — payments at start of month)
```
FV = P × [(1+r)^n − 1] / r × (1+r)
where r = annual rate / 12, n = months
```

### 5.2 Inflation-adjusted (Real) Value
```
Real FV = Nominal FV / (1 + inflation_rate)^years
```

### 5.3 Three Scenarios
| Scenario | Return Assumption |
|---|---|
| Conservative | 6% p.a. |
| Base | 10% p.a. |
| Optimistic | 14% p.a. |

Inflation assumption: 6% p.a. (RBI target band centre).

**Test:** `tests/test_projections.py`

---

## 6. AI Explanation (`app/llm/explain.py`)

1. Engine output is serialised to JSON and sent to Ollama (llama3.2).
2. Every number in the LLM response is extracted via regex and cross-checked against the input JSON.
3. If any number fails verification → deterministic template fallback.
4. Fallback also triggers on: timeout (>20s), Ollama offline, JSON parse error.

**Test:** `tests/test_llm.py`
