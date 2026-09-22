# BankEase Codebase Audit (Phase 0)

**Date**: 2026-09-22  
**Auditor**: Antigravity AI Assistant  
**Repository**: [WPL_mini_project](https://github.com/parthpalse/WPL_mini_project)  
**Status**: Completed  

---

## 1. Architecture Map & Data Flow

### Modules Overview
```
bankease/
├── app/
│   ├── __init__.py           # Flask App factory, DB & LoginManager init, Blueprint registration
│   ├── engine/               # Pure financial calculation logic (supposed to be isolated)
│   │   ├── tax.py            # Income tax (New Tax Regime)
│   │   ├── expenses.py       # Fixed & variable expense summation
│   │   ├── emergency_fund.py # Emergency fund target & shortfall
│   │   ├── max_investment.py # Full surplus pipeline orchestration
│   │   ├── optimizer.py      # Scipy linear programming asset allocator
│   │   └── inflation.py      # FV and real return calculations
│   ├── llm/
│   │   └── explain.py        # Ollama API client (llama3.2)
│   ├── models/
│   │   └── models.py         # SQLAlchemy models (User, FinancialProfile, Goal, PlanResult)
│   ├── routes/
│   │   ├── profile.py        # Intake endpoint (/profile/tier1_submit)
│   │   ├── dashboard.py      # Dashboard (/dashboard/), explanation (/dashboard/explain), simulator (/dashboard/simulator)
│   │   └── plan.py           # Stub endpoint (/plan/)
│   └── templates/            # Jinja2 templates (base.html, onboarding/tier1.html, dashboard/index.html, simulator.html)
├── config/                   # JSON configuration files
│   ├── inflation_assumption.json
│   ├── product_rates_2026.json
│   └── tax_rules_fy2026_27.json
└── tests/                    # Pytest test suite (27 unit tests)
```

### Runtime Data Flow
1. **User Intake**: User visits `GET /profile/` and enters 5 fields (Income, Expenses, Goal Name, Goal Amount, Goal Horizon).
2. **Submission**: `POST /profile/tier1_submit` captures unvalidated form fields, converts them to raw `float`, and stores a dictionary into Flask `session['tier1']`. It redirects to `/dashboard/`.
3. **Dashboard Calculation**: `GET /dashboard/` pulls `session['tier1']`:
   - Calls `max_investment.calculate_surplus(gross_income, fixed_expenses, ...)`:
     - `calculate_tax` (New Regime)
     - `calculate_expenses`
     - `calculate_emergency_fund`
     - Computes `monthly_surplus = net_monthly_income - total_monthly_expenses - debt - emergency_monthly`
   - Calls `optimizer.optimize_allocation(monthly_surplus, ...)` with hard-coded `risk_score=5` and `liquidity_need='medium'`.
   - Renders `dashboard/index.html` with pie charts (Chart.js).
4. **AI Explanation**: Client JavaScript fires an asynchronous `POST /dashboard/explain` with raw JSON payload (`monthly_surplus`, `safe`, `balanced`, `growth`).
   - `dashboard.py` passes this to `llm/explain.py`.
   - `explain.py` sends a prompt to local Ollama (`http://localhost:11434/api/generate`).
   - The returned text is directly inserted into `<div id="ai-explanation">` via `.innerHTML`.
5. **Simulator**: `GET /dashboard/simulator` renders range sliders; client JavaScript debounces and calls `POST /dashboard/simulate_api`, updating surplus and donut charts dynamically.

---

## 2. Formula Audit in `app/engine/`

| File | Function | Inputs | Formula Used | Verdict | Correctness Reasoning & Deficiencies |
|---|---|---|---|---|---|
| `tax.py` | `calculate_tax` | `gross_income: float, config` | `taxable_income = max(0, gross - std_ded)`<br>`tax_before_cess = sum(min(rem, width) * rate)`<br>`rebate_87a = min(tax, max_rebate) if taxable <= max_taxable else 0`<br>`cess = tax_after_rebate * 0.04` | ❌ **CRITICAL BUG** | **1. Catastrophic Cliff Edge**: Section 87A rebate lacks **marginal relief**! At ₹12,75,000 gross (₹12,00,000 taxable), tax is ₹0. At ₹12,80,000 gross (₹12,05,000 taxable), tax jumps to ₹63,180. Earning ₹5,000 more results in ₹58,180 less take-home pay!<br>**2. Missing Surcharge**: Surcharge tiers for income > ₹50L and > ₹1Cr are absent.<br>**3. Missing Old Regime**: Cannot compare Old vs New regimes.<br>**4. Missing Marginal Tax Rate**: Does not return marginal tax rate to compute post-tax yields. |
| `expenses.py` | `calculate_expenses` | `fixed: list[dict], variable: list[dict]` | `total_fixed = sum(item['amount'])`<br>`total_variable = sum(item['amount'])`<br>`total_monthly = total_fixed + total_variable`<br>`total_annual = total_monthly * 12` | ⚠️ **INADEQUATE** | Does not distinguish between Essential vs Discretionary spending or Annual Irregular Sinking Funds. Uses float summation. No schema validation on inputs. |
| `emergency_fund.py` | `calculate_emergency_fund` | `monthly_expenses: float, existing_fund: float, target_months: int = 6, contribution_period_months: int = 12` | `target = monthly_expenses * target_months`<br>`shortfall = max(0, target - existing_fund)`<br>`monthly_contrib = shortfall / contribution_period` | ⚠️ **INCORRECT LOGIC** | **1. Wrong Basis**: Computes target on *total expenses* rather than *essential expenses + debt EMIs*.<br>**2. Hardcoded target**: Default 6 months is static; does not vary by dependents, employment type (salaried/freelance), or income stability.<br>**3. Arbitrary 12 months**: Hard-coded 12-month build period ignores user capacity. |
| `max_investment.py` | `calculate_surplus` | `gross_income, fixed_expenses, variable_expenses, monthly_debt_payments, existing_emergency_fund, emergency_fund_months, tax_config` | `surplus = net_monthly_income - total_monthly_expenses - debt - emergency_contrib` | ⚠️ **FLAWED PIPELINE** | **1. Misclassified Savings**: Subtracts emergency fund contribution as if it were an expense rather than allocating it to liquid asset classes.<br>**2. Double Counting Risk**: Does not account for payroll deductions (EPF, Professional Tax) already in gross.<br>**3. No Safety Buffer**: Lacks standard 5–10% contingency buffer.<br>**4. Deficit Handling Missing**: When surplus <= 0, simply returns `surplus_is_positive: False` without a deficit reduction roadmap or levers. |
| `optimizer.py` | `optimize_allocation` | `monthly_surplus, risk_score, liquidity_need, goal_horizons, product_config` | Scipy `linprog` (HiGHS):<br>Minimize `-sum(return_i * w_i)`<br>subject to:<br>`sum(w_i) == 1`<br>`sum(w_i * risk_i) <= max_avg_risk`<br>`w_equity <= max_equity` | ❌ **DEGENERATE OUTPUT** | **1. Degenerate Allocations**: Linear programming with a linear return objective without variance/diversification constraints collapses into a single product! In Safe mode, it allocates **100% to FD** (0% Savings, 0% RD, 0% Debt Fund). In Growth mode, it allocates **75% Equity and 25% FD**.<br>**2. Dead Parameters**: Arguments `goal_horizons`, `risk_score`, and `liquidity_need` are completely ignored by the function body!<br>**3. Pre-tax Returns**: Uses nominal pre-tax returns; ignores post-tax return adjustment per slab. |
| `inflation.py` | `adjust_for_inflation` | `amount: float, years: int, config` | `amount * ((1 + rate) ** years)` | ⚠️ **INCOMPLETE** | Simple FV formula using floats. Missing SIP future value (annuity due/immediate), RD quarterly compounding, FD compounding, and Step-Up SIP. |
| `inflation.py` | `real_return` | `nominal_return_pct, config` | `((1 + nominal) / (1 + inflation)) - 1` | ✅ **CORRECT** | Correctly uses the Fisher equation, but outputs float rounded to 4 decimals. |

---

## 3. Hard-Coded Numbers Outside `config/`

The following numbers are hard-coded in source files rather than loaded from configuration:

| File | Line Number | Hard-Coded Value | Purpose / Problem |
|---|---|---|---|
| `app/engine/emergency_fund.py` | Line 13 | `target_months: int = 6` | Fixed heuristic not driven by user stability or config. |
| `app/engine/emergency_fund.py` | Line 14 | `contribution_period_months: int = 12` | Arbitrary 12-month shortfall funding duration. |
| `app/engine/max_investment.py` | Line 25 | `emergency_fund_months: int = 6` | Default emergency months hardcoded in surplus signature. |
| `app/engine/optimizer.py` | Line 23 | `risk_score: int = 5` | Default risk score hard-coded. |
| `app/engine/optimizer.py` | Line 24 | `liquidity_need: str = 'medium'` | Default liquidity hard-coded. |
| `app/engine/optimizer.py` | Line 57 | `{'very_low': 1, 'low': 2, 'moderate': 3, 'high': 4}` | Risk scale mapping hard-coded in function body. |
| `app/engine/optimizer.py` | Line 80 | `(0, 1)` | Product allocation upper bound hard-coded to 1.0 (no diversification cap). |
| `app/engine/optimizer.py` | Line 90 | `weight > 0.001` | Weight filtering threshold hard-coded. |
| `app/engine/optimizer.py` | Line 102 | `max_avg_risk=2.0, max_equity_weight=0.0` | Safe strategy constraints hard-coded. |
| `app/engine/optimizer.py` | Line 105 | `max_avg_risk=2.8, max_equity_weight=0.4` | Balanced strategy constraints hard-coded. |
| `app/engine/optimizer.py` | Line 108 | `max_avg_risk=3.5, max_equity_weight=0.8` | Growth strategy constraints hard-coded. |
| `app/llm/explain.py` | Line 9 | `"http://localhost:11434/api/generate"` | Ollama URL hard-coded; not configurable via env vars. |
| `app/llm/explain.py` | Line 10 | `"llama3.2"` | Model name hard-coded; not configurable via env vars. |
| `app/llm/explain.py` | Line 38 | `timeout=30` | Timeout hard-coded. |
| `app/routes/dashboard.py` | Line 31 | `risk_score=5` | Route passes static default risk score to optimizer. |
| `app/routes/dashboard.py` | Line 32 | `liquidity_need='medium'` | Route passes static default liquidity to optimizer. |

---

## 4. Float Money Representation

The codebase uses IEEE-754 binary floating-point numbers (`float`) for all monetary values, leading to potential representation and precision inaccuracies:
1. `app/engine/tax.py`: `gross_income: float`, `tax_before_cess = 0.0`, `round(..., 2)`.
2. `app/engine/expenses.py`: `amount: float`, `round(..., 2)`.
3. `app/engine/emergency_fund.py`: `monthly_expenses: float`, `existing_fund: float = 0.0`.
4. `app/engine/max_investment.py`: `gross_income: float`, `monthly_debt_payments: float = 0.0`.
5. `app/engine/optimizer.py`: `monthly_surplus: float`, `weights[i]`.
6. `app/engine/inflation.py`: `amount: float`.
7. `app/models/models.py`:
   - `FinancialProfile.gross_annual_income = db.Column(db.Float)`
   - `FinancialProfile.total_monthly_debt = db.Column(db.Float)`
   - `FinancialProfile.existing_emergency_fund = db.Column(db.Float)`
   - `Goal.target_amount = db.Column(db.Float)`
8. `app/routes/profile.py`: `float(request.form.get('income', 0))`.
9. `app/routes/dashboard.py`: `float(data.get('income', 0))`.

---

## 5. Architectural Leakage & Coupling

1. **Package Coupling via `app/__init__.py`**:
   - `app/engine` is located within the `app` package.
   - When any test or script executes `from app.engine... import ...`, Python executes `app/__init__.py`.
   - `app/__init__.py` unconditionally imports `Flask`, `SQLAlchemy`, and `LoginManager`.
   - **Consequence**: The financial engine cannot be imported or tested as a standalone library without Flask and Flask-SQLAlchemy installed, violating Phase 1 acceptance criteria.
2. **Missing Service Layer**:
   - Routes interact directly with engine functions (`calculate_surplus`, `optimize_allocation`).
   - Routes directly parse request payloads into dicts without validation schemas (Pydantic / dataclasses).
3. **Database Models Unused in Primary Flow**:
   - `User`, `FinancialProfile`, `Goal`, and `PlanResult` exist in `app/models/models.py` but are completely bypassed by `profile.py` and `dashboard.py` (which rely solely on raw cookie `session`).

---

## 6. AI Layer (Ollama) Audit

### Input Data
- Currently, `dashboard.js` posts:
  ```json
  {
    "monthly_surplus": 46875.0,
    "safe": {"FD": {"percentage": 100.0, "amount": 46875.0}},
    "balanced": {"...": "..."},
    "growth": {"FD": {"percentage": 25.0, "amount": 11718.75}, "Equity Fund": {"percentage": 75.0, "amount": 35156.25}}
  }
  ```
- **Missing from Input**: Calculation trace (`CalcStep`s), user goals, time horizons, tax regime, debt status, emergency fund targets.

### Prompt & Output Handling
- **Hallucination Vulnerability**: The prompt instructs `"Do NOT invent any new numbers"`, but there is **zero post-validation**. If the model hallucinates interest rates (e.g., "Equity will deliver 18%"), the application accepts and renders it.
- **No Deterministic Fallback**: If Ollama is offline or times out (30s), it returns an error string: `"AI explanation is currently unavailable (Ollama might not be running)..."` instead of rendering a deterministic template explanation.
- **XSS Vulnerability**: `dashboard/index.html` (Line 115) inserts raw response into the DOM via `.innerHTML`:
  ```javascript
  document.getElementById('ai-explanation').innerHTML = `<p>${data.explanation.replace(/\n/g, '<br>')}</p>`;
  ```
  If the LLM returns HTML or script tags, it executes unsanitized.

---

## 7. UX & Edge Case Audit

### Full User Flow Testing
1. **Missing Root Route (`/`)**:
   - Visiting `http://localhost:5000/` results in HTTP 404 (Not Found). There is no root redirect to `/profile/` or an onboarding page.
2. **Intake Form Limitations**:
   - Single-step 5-field form (`tier1.html`) captures only aggregate monthly expenses.
   - No breakdown for essential vs discretionary spending.
   - No field for existing debts or loan EMIs.
   - No field for current emergency fund savings.
   - No field for tax regime preference.
3. **Number Formatting**:
   - All numbers are rendered as raw floats (e.g., `₹46875.0` instead of Indian numbering `₹46,875`).
4. **Simulator Slider Limits**:
   - Sliders have arbitrary static maximums (`max="10000000"` for income, `max="1000000"` for expenses).

### Validation & Crash Edge Cases

| Scenario | Input | Current Behavior | Impact |
|---|---|---|---|
| **Non-numeric strings** | `income="abc"` | Uncaught `ValueError: could not convert string to float: 'abc'` in `app/routes/profile.py:14`. Returns **HTTP 500**. | App crashes. |
| **Negative Income** | `income=-50000` | Processed as `-50000.0`. Returns **HTTP 200** with `Monthly Surplus: ₹-3166.67`. | Nonsensical financial plan. |
| **Zero Income** | `income=0` | Processed as `0.0`. Displays zero tax, negative surplus if expenses exist. | No onboarding guidance. |
| **Deficit (Expenses > Income)** | `income=400000`, `expenses=45000` | Displays generic red alert: *"Shortfall Detected"*. | No actionable advice or levers to fix deficit. |
| **Huge Numbers** | `income=1e15` | Slabs evaluate without overflow, but no high-net-worth surcharge is applied. | Gross under-taxation. |
| **Direct Dashboard Access** | Access `/dashboard/` without session | Redirects to `/profile/`. | Handles gracefully. |

---

## 8. Test Suite Analysis

### Existing Test Execution
Command: `py -3.12 -m pytest --cov=app/engine tests/ -v`
- **Total Tests**: 27
- **Passed**: 27
- **Failed**: 0
- **Overall Coverage**: 94% on `app/engine/`

### Test Coverage Breakdown
- `test_emergency_fund.py` (4 tests): Tests 0 balance, partial balance, fully funded, custom months.
- `test_expenses.py` (4 tests): Tests fixed + variable, only fixed, empty, single item.
- `test_inflation.py` (5 tests): Tests FV after 1 yr, 5 yrs, 0 yrs, real return equity, real return savings.
- `test_max_investment.py` (5 tests): Tests 6L minimal, 15L with EMI, 30L high expense, 4L negative surplus, 12L rebate boundary.
- `test_optimizer.py` (2 tests): Tests zero surplus handling, strategy keys presence.
- `test_tax.py` (7 tests): Tests 6L full rebate, 15L, 30L, 4L below slab, 12L boundary, 12.75L cutoff, 0 income.

### Gaps in Existing Test Suite
1. **No Marginal Relief Tests**: Tests verify the incorrect cliff edge at ₹12.75L without asserting continuous marginal relief.
2. **No Property-Based Tests**: No Hypothesis property tests verifying invariants (e.g., `allocations_sum == investable_amount`).
3. **No Surcharge Tests**: Incomes of ₹50L and ₹1Cr have no surcharge test assertions.
4. **No Route / Integration Tests**: Zero automated tests for Flask routes, session handling, or API endpoints.

---

## 9. Baseline Golden Scenarios (Phase 0 Current Outputs)

The following 10 golden scenarios record the exact outputs produced by the **CURRENT** codebase. These outputs serve as the benchmark for comparison against the rebuilt Phase 1 engine.

```json
[
  {
    "name": "Scenario 1: Low Income (3L)",
    "gross_income": 300000,
    "total_tax": 0.0,
    "effective_tax_rate": 0.0,
    "net_monthly_income": 25000.0,
    "monthly_expenses": 15000,
    "monthly_debt": 0,
    "emergency_monthly": 7500.0,
    "monthly_surplus": 2500.0,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 2500.0 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 625.0 }, "Equity Fund": { "percentage": 75.0, "amount": 1875.0 } }
  },
  {
    "name": "Scenario 2: Rebate Zone (6L)",
    "gross_income": 600000,
    "total_tax": 0.0,
    "effective_tax_rate": 0.0,
    "net_monthly_income": 50000.0,
    "monthly_expenses": 25000,
    "monthly_debt": 0,
    "emergency_monthly": 10833.33,
    "monthly_surplus": 14166.67,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 14166.67 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 3541.67 }, "Equity Fund": { "percentage": 75.0, "amount": 10625.0 } }
  },
  {
    "name": "Scenario 3: Mid Income (9L)",
    "gross_income": 900000,
    "total_tax": 0.0,
    "effective_tax_rate": 0.0,
    "net_monthly_income": 75000.0,
    "monthly_expenses": 35000,
    "monthly_debt": 5000,
    "emergency_monthly": 13333.33,
    "monthly_surplus": 21666.67,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 21666.67 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 5416.67 }, "Equity Fund": { "percentage": 75.0, "amount": 16250.0 } }
  },
  {
    "name": "Scenario 4: Rebate Cutoff Exact (12.75L)",
    "gross_income": 1275000,
    "total_tax": 0.0,
    "effective_tax_rate": 0.0,
    "net_monthly_income": 106250.0,
    "monthly_expenses": 40000,
    "monthly_debt": 0,
    "emergency_monthly": 11666.67,
    "monthly_surplus": 54583.33,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 54583.33 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 13645.83 }, "Equity Fund": { "percentage": 75.0, "amount": 40937.5 } }
  },
  {
    "name": "Scenario 5: Just Above Rebate Cutoff (12.8L)",
    "gross_income": 1280000,
    "total_tax": 63180.0,
    "effective_tax_rate": 4.94,
    "net_monthly_income": 101401.67,
    "monthly_expenses": 40000,
    "monthly_debt": 0,
    "emergency_monthly": 11666.67,
    "monthly_surplus": 49735.0,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 49735.0 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 12433.75 }, "Equity Fund": { "percentage": 75.0, "amount": 37301.25 } }
  },
  {
    "name": "Scenario 6: Upper-Mid Income with EMI (15L)",
    "gross_income": 1500000,
    "total_tax": 97500.0,
    "effective_tax_rate": 6.5,
    "net_monthly_income": 116875.0,
    "monthly_expenses": 45000,
    "monthly_debt": 15000,
    "emergency_monthly": 10000.0,
    "monthly_surplus": 46875.0,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 46875.0 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 11718.75 }, "Equity Fund": { "percentage": 75.0, "amount": 35156.25 } }
  },
  {
    "name": "Scenario 7: Affluent Salaried (25L)",
    "gross_income": 2500000,
    "total_tax": 319800.0,
    "effective_tax_rate": 12.79,
    "net_monthly_income": 181683.33,
    "monthly_expenses": 70000,
    "monthly_debt": 40000,
    "emergency_monthly": 10000.0,
    "monthly_surplus": 61683.33,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 61683.33 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 15420.83 }, "Equity Fund": { "percentage": 75.0, "amount": 46262.5 } }
  },
  {
    "name": "Scenario 8: Surcharge Boundary (50L)",
    "gross_income": 5000000,
    "total_tax": 1099800.0,
    "effective_tax_rate": 22.0,
    "net_monthly_income": 325016.67,
    "monthly_expenses": 120000,
    "monthly_debt": 50000,
    "emergency_monthly": 18333.33,
    "monthly_surplus": 136683.34,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 136683.34 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 34170.83 }, "Equity Fund": { "percentage": 75.0, "amount": 102512.51 } }
  },
  {
    "name": "Scenario 9: Super HNI (1 Cr)",
    "gross_income": 10000000,
    "total_tax": 2659800.0,
    "effective_tax_rate": 26.6,
    "net_monthly_income": 611683.33,
    "monthly_expenses": 250000,
    "monthly_debt": 0,
    "emergency_monthly": 41666.67,
    "monthly_surplus": 320016.66,
    "safe_alloc": { "FD": { "percentage": 100.0, "amount": 320016.66 } },
    "growth_alloc": { "FD": { "percentage": 25.0, "amount": 80004.16 }, "Equity Fund": { "percentage": 75.0, "amount": 240012.49 } }
  },
  {
    "name": "Scenario 10: Deficit Case (4L income, high exp)",
    "gross_income": 400000,
    "total_tax": 0.0,
    "effective_tax_rate": 0.0,
    "net_monthly_income": 33333.33,
    "monthly_expenses": 45000,
    "monthly_debt": 0,
    "emergency_monthly": 22500.0,
    "monthly_surplus": -34166.67,
    "safe_alloc": {},
    "growth_alloc": {}
  }
]
```

---

## 10. Audit Summary & Readiness for Phase 1

The audit confirms:
1. **Math Engine Rebuild is Essential**: The Section 87A cliff edge is severe; optimizer allocations are degenerate; floats are used throughout; debt prioritization and emergency fund logic require restructuring.
2. **Acceptance Criteria for Phase 0 Met**:
   - Specific file names and line numbers identified.
   - All formulas mapped and critiqued.
   - Hard-coded constants cataloged.
   - 10 golden scenarios measured and recorded.
3. **Next Step**: Proceed to **Phase 1 - Math Engine Rebuild**.
