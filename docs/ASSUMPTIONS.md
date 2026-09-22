# BankEase — Assumptions

Every assumption used in this application is listed below with its source and confidence level.

| Parameter | Value | Source | As Of | Confidence |
|---|---|---|---|---|
| New Regime tax slabs | See METHODOLOGY.md § 1.1 | Finance Act 2026-27 | Apr 2026 | High |
| Section 87A rebate limit | ₹25,000 on income ≤ ₹12,75,000 | Finance Act 2026-27 | Apr 2026 | High |
| Surcharge thresholds | ₹50L / ₹1Cr / ₹2Cr / ₹5Cr | Finance Act 2026-27 | Apr 2026 | High |
| Health & Education Cess | 4% | Finance Act 2026-27 | Apr 2026 | High |
| Emergency fund months | 6 months | RBI financial literacy guidelines | 2024 | Medium |
| PPF return | 7.1% p.a. | India Post / Govt. notification | Q1 2026 | High |
| EPF return | 8.25% p.a. | EPFO circular | FY 2025-26 | High |
| Fixed Deposit (base) | 7.0% p.a. | SBI / major bank average | Q1 2026 | Medium |
| Recurring Deposit | 6.5% p.a. | SBI / major bank average | Q1 2026 | Medium |
| Equity index (base) | 10% p.a. (nominal) | BSE Sensex 20-year CAGR | 2024 | Medium |
| Equity index (conservative) | 6% p.a. | Downside scenario | — | Low |
| Equity index (optimistic) | 14% p.a. | Bull scenario | — | Low |
| Inflation (RBI target) | 6% p.a. | RBI Monetary Policy, target band 4±2% | 2025 | Medium |
| Risk-free rate | 7.1% p.a. (10-yr G-Sec) | RBI / Bloomberg | Q1 2026 | High |
| Liquid fund return | 7% p.a. | AMFI category average | Q1 2026 | Medium |

## Notes
- All rate assumptions are **illustrative** and reviewed periodically. See `config/_meta.json` for last review date.
- Equity return assumptions do not guarantee future performance. Past returns ≠ future returns.
- This application does **not** constitute financial advice. Consult a SEBI-registered investment advisor.
- Data last reviewed: FY 2026-27. Update rates in `config/products.json` and `config/macro.json` to refresh.
