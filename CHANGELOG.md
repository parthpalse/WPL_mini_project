# BankEase Engine Changelog: Phase 0 vs Phase 1

This changelog documents the exact numerical differences between the Phase 0 baseline and the rebuilt Phase 1 math engine across the 10 Golden Scenarios, distinguishing between bug fixes and intentional methodology improvements.

---

## Golden Scenario Comparison Table

| Scenario | Metric | Phase 0 Baseline | Phase 1 Rebuilt | Change Classification | Reasoning |
|---|---|---|---|---|---|
| **Scenario 1: Low Income (3L)** | Total Tax | ₹0.00 | ₹0.00 | Identical | Below taxable threshold in both regimes. |
| | Monthly Surplus | ₹2,500.00 | ₹1,250.00 | Intended Improvement | Deducted 5% monthly contingency buffer (₹1,250) to protect against irregular cash flows. |
| | Safe Allocation | 100% FD | 60% FD, 30% RD, 5% Savings, 5% Debt | Bug Fix | Fixed degenerate LP solver collapsing into a single product. Enforced 60% single-product diversification cap. |
| **Scenario 2: Rebate Zone (6L)** | Total Tax | ₹0.00 | ₹0.00 | Identical | Covered by Section 87A rebate. |
| | Monthly Surplus | ₹14,166.67 | ₹11,666.67 | Intended Improvement | Deducted 5% safety buffer (₹2,500). |
| | Safe Allocation | 100% FD | 60% FD, 30% RD, 5% Savings, 5% Debt | Bug Fix | Diversification caps enforced. |
| **Scenario 3: Mid Income (9L)** | Total Tax | ₹0.00 | ₹0.00 | Identical | Covered by Section 87A rebate. |
| | Monthly Surplus | ₹21,666.67 | ₹17,916.67 | Intended Improvement | Deducted 5% safety buffer (₹3,750). |
| **Scenario 4: Rebate Cutoff Exact (12.75L)** | Total Tax | ₹0.00 | ₹0.00 | Identical | Standard deduction ₹75k + ₹12L slab rebate = ₹0 tax. |
| | Monthly Surplus | ₹54,583.33 | ₹49,270.83 | Intended Improvement | Deducted 5% safety buffer (₹5,312.50). |
| **Scenario 5: Above Rebate Cutoff (12.8L)** | **Total Tax** | **₹63,180.00** | **₹5,200.00** | **CRITICAL BUG FIX** | **Section 87A Marginal Relief**: Earning ₹5,000 above the ₹12L threshold previously caused tax to jump to ₹63,180. Marginal relief caps tax to excess income (₹5,000) + 4% cess (₹200) = ₹5,200, saving the user ₹57,980. |
| | Net Monthly Income | ₹1,01,401.67 | ₹1,06,233.33 | Critical Bug Fix | Take-home pay increased by ₹4,831.66/month. |
| **Scenario 6: Upper-Mid Salaried (15L)** | Total Tax | ₹97,500.00 | ₹97,500.00 | Identical | Standard New Regime calculation above rebate zone. |
| | Monthly Surplus | ₹46,875.00 | ₹41,031.25 | Intended Improvement | Deducted 5% safety buffer (₹5,843.75). |
| **Scenario 7: Affluent Salaried (25L)** | Total Tax | ₹319,800.00 | ₹319,800.00 | Identical | New Regime default; dual regime comparison active. |
| | Monthly Surplus | ₹61,683.33 | ₹52,599.16 | Intended Improvement | Deducted 5% safety buffer (₹9,084.17). |
| **Scenario 8: Surcharge Boundary (50L)** | Total Tax | ₹1,099,800.00 | ₹1,099,800.00 | Identical | Surcharge kicks in at taxable income > ₹50L (gross ₹50.75L). |
| | Monthly Surplus | ₹136,683.34 | ₹120,432.51 | Intended Improvement | Deducted 5% safety buffer (₹16,250.83). |
| **Scenario 9: Super HNI (1 Cr)** | **Total Tax** | **₹2,659,800.00** | **₹2,925,780.00** | **CRITICAL BUG FIX** | **15% Surcharge Applied**: Income > ₹1 Crore triggers a 15% surcharge tier under Indian Tax law. Previously omitted, resulting in gross under-taxation. |
| | Net Monthly Income | ₹611,683.33 | ₹589,518.33 | Critical Bug Fix | Reflects statutory surcharge obligations. |
| **Scenario 10: Deficit Case (4L)** | Monthly Surplus | -₹34,166.67 | -₹35,833.34 | Intended Improvement | Includes safety buffer; triggers comprehensive Deficit Plan with top 3 levers to restore break-even. |

---

## Summary of Math Upgrades
1. **Decimal Precision**: Eliminated IEEE float money representation across all engine calculations.
2. **Tax Law Compliance**: Implemented Section 87A marginal relief and high-earner surcharge tiers.
3. **Decoupled Architecture**: Financial engine can now be imported and run with zero Flask dependencies.
4. **Transparent Pipeline**: Traceable `CalcStep` sequence produced for every calculation.
5. **Robust Optimization**: Enforced diversification caps and horizon-driven glide paths.
6. **Expense Scaling Bug Fix**: Corrected route translation that previously passed `monthly_expenses * 12` into monthly engine buckets.
7. **Accurate Gross/Net Inversion**: Replaced rough `x * 1.25` income heuristic with monotonic bisection search matching user take-home to the exact rupee.
8. **End-to-End Debt & Emergency Alignment**: Wired credit cards, loan EMIs, and existing savings into cash flow allocation and emergency fund shortfall calculations.

