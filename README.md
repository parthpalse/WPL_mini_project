# BankEase

**AI-assisted personal financial planning and investment optimization web app.**

BankEase calculates your maximum sustainable monthly savings/investment capacity through a deterministic pipeline (income → tax → expenses → debt → emergency fund → surplus) and optimizes allocation across financial products (Savings / RD / FD / Debt Fund / Equity Fund).

Two AI layers work together:
- **Ollama** (local, offline) — deterministic financial explanations with strict number verification
- **Claude Haiku** (Anthropic API) — streaming conversational chatbot grounded in your live plan data + real-time market quotes

---

## Key Principles & Features

- **Math decides the numbers. AI only explains them.** The optimizer/rule engine is deterministic Python — no LLM ever computes a financial figure.
- **Anti-hallucination guardrails.** Every number in an AI response is cross-checked against engine ground truth before rendering.
- **Results Hierarchy:**
  - 📊 **Waterfall Chart:** Visual cash flow breakdown from gross/net income down to investable surplus.
  - ✅ **Ordered Action Checklist:** Prioritizes credit card payoff (36–42% interest), emergency reserves, and SIPs.
  - 💼 **Asset Class Allocation:** Diversification caps and horizon-driven glide paths.
  - 📈 **10-Year Wealth Projections:** 3 scenarios (Conservative 6%, Base 10%, Optimistic 14%) with "Future Rupees" vs "Today's Rupees (Real)" toggles.
  - 🧾 **Dual-Regime Tax Comparison:** Compares New vs Old regime under FY 2026-27 with Section 87A marginal relief and statutory surcharge tiers.
  - 🎛️ **What-If Sliders:** Live recalculation of surplus and deltas as income or expenses change.
  - 🔍 **Calculation Trace:** Full step-by-step audit trail (`CalcStep`).
  - 💡 **"Explain this number":** Interactive modal on figures and trace steps with verified plain-English explanations.
  - 💾 **Scenario Management:** Save custom plan scenarios and compare them side-by-side with difference tags.
  - 📄 **Print & PDF Export:** Clean print styling (`@media print`) for offline reports.
  - 🔐 **Authentication:** User registration, password hashing (PBKDF2:SHA256), login, and session persistence.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python + Flask (App Factory & Blueprints) |
| Database | SQLite (local dev) / **Supabase PostgreSQL** (production) |
| Optimization | scipy / PuLP |
| Charts | Chart.js |
| Market Data | Finnhub REST API (free tier, 60 calls/min) |
| AI — Explanations | Ollama (local Llama 3.2 / Mistral with verified fallback) |
| AI — Chat | Claude 3.5 Haiku (Anthropic API, streaming SSE) |

---

## Quick Setup (Local Development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment file
cp .env.example .env

# 3. Run the database setup script (creates all tables)
python scripts/setup_supabase.py

# 4. Start the application
python run.py

# 5. Run tests (70 passing tests)
python -m pytest
```

Visit **`http://localhost:5000`** in your browser.

---

## 🗄️ Supabase Database Setup

BankEase is pre-configured to connect directly to **Supabase** via PostgreSQL (`psycopg2-binary`):

1. Go to **[supabase.com](https://supabase.com)** and open your project dashboard.
2. Navigate to **Project Settings** (gear icon) → **Database**.
3. Under **Connection string**, select **URI** (or Connection Pooler on port `6543`).
4. In your `.env` file (or host environment variables), set:
   ```env
   DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
5. Run the verification script:
   ```bash
   python scripts/setup_supabase.py
   ```
   This will test your connection and create all tables (`users`, `financial_profiles`, `goals`, `plan_results`).

---

## 🚀 Deploying to Render

BankEase is pre-configured for **Render** via [`render.yaml`](render.yaml) and [`Procfile`](Procfile):

1. Push your repository to GitHub.
2. Go to **[dashboard.render.com](https://dashboard.render.com)** → Click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Render will detect the configuration:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 "run:app"`
5. In **Environment Variables**, set:
   - `DATABASE_URL`: Your Supabase connection string.
   - `SECRET_KEY`: A secure random secret string.
   - `ANTHROPIC_API_KEY`: *(Optional)* For the live chat assistant.
   - `FINNHUB_API_KEY`: *(Optional)* For live market quotes.
6. Click **Create Web Service** to launch your live site!

---

## Test Suite

The test suite contains **70 unit and integration tests** covering:
- Dual-regime Indian Tax calculations (FY 2026-27) with Section 87A marginal relief.
- 10 hand-calculated Golden Scenarios across all income bands (₹3L to ₹1Cr+).
- Property-based tests via Hypothesis.
- AI number verification across 20 diverse scenarios (zero hallucinations).
- Scenario comparison, saving, and single-step explanation endpoints.
- User registration, login, and session persistence.

```bash
python -m pytest -v
```

---

## Disclaimer

All interest rates, returns, and financial projections shown are **illustrative** and based on static snapshots. They do not constitute financial advice under SEBI (Investment Advisers) Regulations, 2013. Consult a SEBI-registered investment advisor for personalized guidance.

