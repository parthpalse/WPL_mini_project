# BankEase

**AI-assisted personal financial planning and investment optimization web app.**

BankEase calculates your maximum sustainable monthly savings/investment capacity through a deterministic pipeline (income → tax → expenses → debt → emergency fund → surplus) and optimizes allocation across financial products (Savings / RD / FD / Debt Fund / Equity Fund).

A local open-source LLM (via Ollama) explains results in plain language. **No external API keys** — fully self-contained and reproducible offline.

## Key Principles

- **Math decides the numbers. AI only explains them.** The optimizer/rule engine is deterministic Python.
- **No external API calls.** LLM calls go to a local Ollama instance only.
- **All financial parameters live in versioned JSON config files** (`config/` directory).
- **No live/scraped data.** Rates are illustrative snapshots.

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python + Flask |
| Database | SQLite (dev) / PostgreSQL (deploy) |
| Optimization | scipy / PuLP |
| Charts | Chart.js |
| AI Layer | Ollama (local, Llama 3.2 / Mistral) |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
flask run

# Run tests
python -m pytest tests/ -v
```

## Project Structure

```
bankease/
├── app/
│   ├── engine/      # Deterministic financial calculators
│   ├── llm/         # AI explanation layer (Ollama)
│   ├── models/      # DB models
│   ├── routes/      # Flask blueprints
│   ├── static/      # CSS, JS
│   └── templates/   # Jinja2 templates
├── config/          # Versioned financial parameters
├── tests/           # Unit tests with hand-calculated cases
└── requirements.txt
```

## Disclaimer

All interest rates, returns, and financial projections shown are **illustrative** and based on static snapshots. They do not constitute financial advice. Consult a qualified financial advisor for personalized guidance.
