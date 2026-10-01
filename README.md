# BankEase

**AI-assisted personal financial planning and investment optimization web app.**

BankEase calculates your maximum sustainable monthly savings/investment capacity through a deterministic pipeline (income → tax → expenses → debt → emergency fund → surplus) and optimizes allocation across financial products (Savings / RD / FD / Debt Fund / Equity Fund).

Two AI layers work together:
- **Ollama** (local, offline) — deterministic financial explanations with strict number verification
- **Claude Haiku** (Anthropic API) — streaming conversational chatbot grounded in your live plan data + real-time market quotes

## Key Principles

- **Math decides the numbers. AI only explains them.** The optimizer/rule engine is deterministic Python — no LLM ever computes a financial figure.
- **Anti-hallucination guardrails.** Every number in an AI response is cross-checked against engine/market ground truth before rendering.
- **Cache-first market data.** Finnhub quotes are cached with TTL (90s quotes, 300s metrics, 600s news) — the chatbot reads from cache, never makes a live API call mid-conversation.
- **All financial parameters live in versioned JSON config files** (`config/` directory).

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python + Flask |
| Database | SQLite (dev) / PostgreSQL (deploy) |
| Optimization | scipy / PuLP |
| Charts | Chart.js |
| Market Data | Finnhub REST API (free tier, 60 calls/min) |
| AI — Explanations | Ollama (local, Llama 3.2 / Mistral) |
| AI — Chat | Claude 3.5 Haiku (Anthropic API, streaming SSE) |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env and add your API keys
cp .env.example .env
# Edit .env → set FINNHUB_API_KEY and ANTHROPIC_API_KEY

# Run the app
python run.py

# Run tests
python -m pytest tests/ -v
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session secret |
| `DATABASE_URL` | No | Defaults to SQLite |
| `FINNHUB_API_KEY` | For market data | Free key from [finnhub.io](https://finnhub.io) |
| `ANTHROPIC_API_KEY` | For chatbot | From [console.anthropic.com](https://console.anthropic.com) |
| `CLAUDE_CHAT_MODEL` | No | Defaults to `claude-3-5-haiku-20241022` |
| `CLAUDE_MAX_TOKENS` | No | Defaults to `512` |
| `OLLAMA_URL` | For explanations | Defaults to `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | No | Defaults to `llama3.2` |

> **Note:** The chat FAB button only appears on the dashboard when `ANTHROPIC_API_KEY` is configured. Without it, the rest of the app works normally.

## Project Structure

```
bankease/
├── app/
│   ├── engine/          # Deterministic financial calculators
│   │   ├── max_investment.py   # Income → surplus pipeline
│   │   ├── optimizer.py        # Portfolio allocation (scipy/PuLP)
│   │   ├── tax.py              # Indian tax engine (FY2026-27)
│   │   ├── emergency_fund.py   # Emergency fund calculator
│   │   ├── inflation.py        # Inflation-adjusted projections
│   │   └── models.py           # Domain dataclasses (CalcStep, etc.)
│   ├── market/          # Live market data layer
│   │   ├── finnhub_client.py   # Finnhub REST API client
│   │   └── cache.py            # Thread-safe TTL cache
│   ├── llm/             # AI layers (separated by concern)
│   │   ├── explain.py          # Ollama — deterministic explanations
│   │   └── chat.py             # Claude Haiku — streaming chat
│   ├── routes/          # Flask blueprints
│   │   ├── dashboard.py        # Main dashboard + explain endpoints
│   │   ├── chat.py             # SSE streaming + sync chat API
│   │   ├── wizard.py           # Onboarding wizard
│   │   └── profile.py          # User profile
│   ├── static/js/       # Frontend JavaScript
│   │   ├── dashboard.js        # Charts + AI explanation fetch
│   │   ├── chat.js             # Streaming chat widget (SSE)
│   │   └── formatters.js       # Indian currency formatting
│   └── templates/       # Jinja2 templates
├── config/              # Versioned financial parameters (tax rules, product rates)
├── tests/               # 52 unit tests with hand-calculated golden scenarios
├── scripts/             # Utility scripts (uptime bot, etc.)
└── requirements.txt
```

## Chat Architecture

The chatbot is designed for **speed** as the primary constraint:

1. **Model:** Claude 3.5 Haiku — lowest latency in the Claude family
2. **Lean context:** ~200-token structured `[CONTEXT]` block per turn (not full profile + full history)
3. **Streaming:** SSE (`text/event-stream`) delivers tokens to the UI as they're generated
4. **History trimming:** Last 6 turn-pairs only, hard-capped at 2000 chars per message
5. **Guardrail:** Post-generation numeric cross-check against engine + Finnhub ground truth
6. **Cache-only market reads:** Chat context pulls from TTL cache, never triggers a live Finnhub call

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/chat/stream` | POST | SSE streaming chat response |
| `/chat/sync` | POST | JSON response (testing/fallback) |
| `/chat/health` | GET | API key status + cache stats |
| `/dashboard/explain` | POST | Ollama deterministic explanation |

## Disclaimer

All interest rates, returns, and financial projections shown are **illustrative** and based on static snapshots. They do not constitute financial advice. Consult a SEBI-registered investment advisor for personalized guidance.
