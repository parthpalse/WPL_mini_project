# BankEase

**AI-assisted personal financial planning and investment optimization web app.**

BankEase calculates your maximum sustainable monthly savings/investment capacity through a deterministic pipeline (income → tax → expenses → debt → emergency fund → surplus) and optimizes allocation across financial products (Savings / RD / FD / Debt Fund / Equity Fund).

Two AI layers work together:
- **Ollama** (local, offline) — deterministic financial explanations with strict number verification
- **Open-source chat LLM** (Llama 3.2 via local Ollama, or gpt-oss-20b on Groq for the hosted site) — streaming conversational chatbot grounded in your live plan data + real-time market quotes

**Live demo:** https://bankease-mdpa.onrender.com *(Render free tier — the first request after idle can take up to a minute to wake the server.)*

---

## How the app works (user flow)

1. **Sign up or log in** (`/auth/register`, `/auth/login`). Every page requires a login.
2. **New account → Financial Profile first, no exceptions.** A new user lands on `/profile` with an empty form (no sample data). Every other page (`/`, `/savings`, `/planner`, `/market`, `/assistant`, `/goals`, `/settings`) redirects back to `/profile` — enforced on the server, and on in-app navigation by a small guard script — until a profile with a monthly income above ₹0 is saved.
3. **First successful save → the report.** The user is sent to the dashboard (overview, savings capacity, planner, market, goals, AI assistant).
4. **Returning user with a saved profile → straight to the dashboard** on login. A returning user who never finished the profile is sent back to `/profile`.
5. **AI Assistant** answers questions using that user's own saved profile numbers (computed by the engine) plus the open-source LLM; if the LLM is unreachable the user gets a deterministic summary instead. UI errors (expired session, timeout, server error) are shown as real messages — the app never falls back to fake/mock data.

Profile and goals are stored **per user in MongoDB** (`user_data` collection), so each account only ever sees its own data.

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
| Database | **MongoDB** (local `mongod` or Docker for dev / **MongoDB Atlas** in production) via `pymongo` |
| Optimization | scipy / PuLP |
| Charts | Chart.js |
| Market Data | Finnhub REST API (free tier, 60 calls/min) |
| AI — Explanations | Ollama (local Llama 3.2 / Mistral with verified fallback) |
| AI — Chat | Open-source LLM via any OpenAI-compatible API — Llama 3.2 on Ollama locally, gpt-oss-20b on Groq in production (streaming SSE) |

---

## Quick Setup (Local Development)

```bash
# 1. Install dependencies
pip install -r requirements-dev.txt

# 2. Copy environment file
cp .env.example .env

# 3. Point MONGODB_URI in .env at a MongoDB server (local or Atlas), then verify
python scripts/setup_mongodb.py

# 4. Start the application
python run.py

# 5. Run tests (uses in-memory mongomock — no server needed)
python -m pytest
```

Visit **`http://localhost:5000`** in your browser.

---

## 🗄️ MongoDB Atlas Setup

BankEase stores users and saved wizard profiles in MongoDB (collections `users` and `financial_profiles`, created automatically on first write):

1. Create a free **M0** cluster at **[cloud.mongodb.com](https://cloud.mongodb.com)**.
2. **Database Access** → add a database user with a password.
3. **Network Access** → add `0.0.0.0/0` (Render's outbound IPs are not fixed on the free plan).
4. **Connect** → **Drivers** → **Python** → copy the `mongodb+srv://` string, and add `/bankease` before the `?`:
   ```env
   MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/bankease?retryWrites=true&w=majority
   ```
5. Put it in `.env` and run the verification script (pings the server and creates the indexes):
   ```bash
   python scripts/setup_mongodb.py
   ```

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
   - `MONGODB_URI`: Your MongoDB Atlas connection string.
   - `SECRET_KEY`: A secure random secret string.
   - `LLM_API_KEY`: *(Optional)* Free Groq key (https://console.groq.com/keys) for the chat assistant. `LLM_BASE_URL` / `LLM_MODEL` default to Groq + `openai/gpt-oss-20b` (open-weight, Apache 2.0) via `render.yaml`; without a key the chat falls back to a deterministic summary.
   - `FINNHUB_API_KEY`: *(Optional)* For live market quotes.
6. Click **Create Web Service** to launch your live site!

---

## Status & verification

Last verified end-to-end against the live deployment:

| Check | Result |
|---|---|
| Signup lands on `/profile`; all other pages redirect to `/profile` until profile saved | ✅ |
| Profile / goals empty for a new account (no sample data) | ✅ |
| Saving a profile unlocks every page; login then lands on `/` | ✅ |
| Login without a saved profile lands on `/profile` | ✅ |
| AI chat (Groq `openai/gpt-oss-20b`) answers from the user's own figures | ✅ |
| Automated test suite (`python -m pytest`) | ✅ 85 passed |

Known limits: the free Render tier sleeps when idle; market quotes come from Finnhub when `FINNHUB_API_KEY` is set, otherwise from Yahoo Finance's unofficial public endpoint (delayed, may rate-limit); the suggested monthly tax assumes a salaried resident under 60 with no deductions beyond the standard deduction. The prebuilt React SPA in `app/static/spa/` ships compiled only (its source is not in this repo), so frontend fixes are patched into the compiled bundle and the account bar / profile-first guard are injected by `app/routes/spa.py`.

---

## Test Suite

The test suite contains **85 unit and integration tests** covering:
- Dual-regime Indian Tax calculations (FY 2026-27) with Section 87A marginal relief.
- 10 hand-calculated Golden Scenarios across all income bands (₹3L to ₹1Cr+).
- Property-based tests via Hypothesis.
- AI number verification across 20 diverse scenarios (zero hallucinations).
- Scenario comparison, saving, and single-step explanation endpoints.
- User registration, login, and session persistence.
- Profile-first onboarding: page gating, login routing, per-user data isolation.

```bash
python -m pytest -v
```

---

## Disclaimer

All interest rates, returns, and financial projections shown are **illustrative** and based on static snapshots. They do not constitute financial advice under SEBI (Investment Advisers) Regulations, 2013. Consult a SEBI-registered investment advisor for personalized guidance.

