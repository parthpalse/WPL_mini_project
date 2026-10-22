"""Tax grounding for the chat LLM.

The model is never trusted to know current tax law or to do tax arithmetic. When a
question looks tax-related this module builds a compact text block with:
  • the FY 2026-27 rules, read from config/tax_rules_fy2026_27.json
  • a computed tax result from app.engine.tax for any income the user mentions
    (e.g. "1 lakh monthly") and for the income saved in their profile
The block is injected into the chat [CONTEXT], so the model only has to explain it.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from app.engine.tax import calculate_tax_regime, load_config

TAX_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "tax_rules_fy2026_27.json"
)

TAX_KEYWORDS = re.compile(
    r"\b(tax|taxes|taxable|slab|slabs|rebate|87a|regime|itr|tds|cess|surcharge|"
    r"deduction|deductions|80c|80d|income[- ]tax|take[- ]home|in[- ]hand)\b",
    re.IGNORECASE,
)

_UNITS = {
    "k": 1_000, "thousand": 1_000,
    "l": 100_000, "lac": 100_000, "lacs": 100_000, "lakh": 100_000, "lakhs": 100_000, "lpa": 100_000,
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
}
_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(lakhs?|lacs?|lpa|crores?|cr|thousand|k|l)?\b",
    re.IGNORECASE,
)
_MONTHLY = re.compile(r"\b(month|monthly|per month|pm|a month|/m|/month)\b", re.IGNORECASE)
_ANNUAL = re.compile(r"\b(year|yearly|annual|annually|per annum|pa|p\.a|lpa|a year|/yr|/year|ctc)\b", re.IGNORECASE)


SAVINGS_KEYWORDS = re.compile(r"\b(save|saving|savings|surplus|invest|investable|left over)\b", re.IGNORECASE)
_MONTHS = re.compile(r"\b(\d{1,3})\s*months?\b", re.IGNORECASE)


def is_tax_question(message: str) -> bool:
    return bool(TAX_KEYWORDS.search(message or ""))


def _wants_tax_context(message: str) -> bool:
    """Tax words, or a savings question that states an income (needs the post-tax figure)."""
    return is_tax_question(message) or (
        bool(SAVINGS_KEYWORDS.search(message or "")) and extract_annual_income(message) is not None
    )


def extract_annual_income(message: str) -> Optional[tuple[float, str]]:
    """Find an income figure in the message. Returns (annual_amount, matched_text) or None.

    A period (monthly / yearly) must be stated or implied by the unit (LPA); an amount
    with no period is ambiguous, so it is skipped rather than guessed.
    """
    for m in _AMOUNT.finditer(message or ""):
        number = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        amount = number * _UNITS.get(unit, 1)
        if amount < 10_000:  # ignore counts like "2 years", "80c", "5 lakh" is fine (>=10k)
            continue
        matched = m.group(0).strip()
        if unit == "lpa":
            return amount, matched
        # The period word right after the amount wins ("2 lakh a month then my year salary" is monthly).
        after = message[m.end(): m.end() + 14]
        if _MONTHLY.search(after):
            return amount * 12, matched
        if _ANNUAL.search(after):
            return amount, matched
        window = message[max(0, m.start() - 25): m.end() + 25]
        if _ANNUAL.search(window):
            return amount, matched
        if _MONTHLY.search(window):
            return amount * 12, matched
    return None


def _inr(value: float) -> str:
    """Indian digit grouping: 1125000 -> ₹11,25,000."""
    n = int(round(abs(value)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"₹{s}"


def _slab_text(slabs: list[dict]) -> str:
    parts, prev = [], 0
    for slab in slabs:
        upper = slab["upto"]
        rate = f"{slab['rate'] * 100:g}%"
        parts.append(f"above {_inr(prev)}: {rate}" if upper is None else f"{_inr(prev)}-{_inr(upper)}: {rate}")
        prev = upper or prev
    return "; ".join(parts)


def _other_rules(cfg: dict) -> list[str]:
    cg = cfg.get("capital_gains")
    if not cg:
        return []
    return [
        f"Capital gains: listed-equity LTCG {cg['equity_ltcg_rate'] * 100:g}% on gains above {_inr(cg['equity_ltcg_exemption'])} a year; "
        f"STCG {cg['equity_stcg_rate'] * 100:g}%; debt-fund gains and FD interest are taxed at slab rate; "
        f"savings-account interest deduction (80TTA, old regime) up to {_inr(cg['savings_interest_deduction_80tta'])}.",
        "New regime allows only employer NPS (80CCD(2)) as a deduction besides the standard deduction; 80C/80D/HRA/24(b) need the old regime.",
    ]


def rules_summary(cfg: dict) -> str:
    new, old = cfg["new_regime"], cfg["old_regime"]
    rebate = new["rebate_87a"]
    zero_tax_salary = rebate["max_taxable_income"] + new["standard_deduction"]
    return "\n".join([
        f"[TAX RULES FY{cfg['financial_year']}, resident individual below 60]",
        f"New regime (default): standard deduction {_inr(new['standard_deduction'])}. Slabs on taxable income: {_slab_text(new['slabs'])}.",
        f"New regime Sec 87A: no tax if taxable income is up to {_inr(rebate['max_taxable_income'])} "
        f"(rebate up to {_inr(rebate['max_rebate'])}); marginal relief just above it. "
        f"So a salaried person earning up to {_inr(zero_tax_salary)} a year pays zero income tax. Cess {cfg['cess_rate'] * 100:g}%.",
        f"Old regime: standard deduction {_inr(old['standard_deduction'])}, slabs: {_slab_text(old['slabs'])}; "
        f"87A rebate only up to taxable income {_inr(old['rebate_87a']['max_taxable_income'])}; "
        f"allows 80C (cap {_inr(old['caps']['sec_80c'])}), 80D, 24(b), NPS 80CCD(1B).",
        "Salary is gross income, not taxable income: the standard deduction is subtracted first.",
        *_other_rules(cfg),
    ])


def _calc_line(label: str, result: dict) -> str:
    return (
        f"{label}: taxable income {_inr(result['taxable_income'])}, tax before rebate {_inr(result['tax_before_cess'])}, "
        f"87A rebate/relief {_inr(result['rebate_87a'])}, total tax incl. cess {_inr(result['total_tax'])} "
        f"(effective {result['effective_rate_pct']:g}%)"
    )


def _calc_block(title: str, annual_gross: float, cfg: dict, monthly_outgo: float = 0.0, months: int = 0) -> str:
    new = calculate_tax_regime(annual_gross, "new", cfg)
    old = calculate_tax_regime(annual_gross, "old", cfg)
    lines = [
        f"[TAX CALC {title}: annual gross {_inr(annual_gross)}, salaried, no other deductions]",
        _calc_line("New regime", new),
        _calc_line("Old regime", old),
        f"Monthly take-home after tax (new regime): {_inr((annual_gross - new['total_tax']) / 12)}",
    ]
    if monthly_outgo > 0:
        surplus = max(0.0, (annual_gross - new["total_tax"]) / 12 - monthly_outgo)
        lines.append(
            f"With the user's current monthly expenses and EMIs of {_inr(monthly_outgo)}, the monthly surplus at this income "
            f"would be {_inr(surplus)}"
            + (f", so {months} months of saving = {_inr(surplus * months)}." if months else ".")
        )
    return "\n".join(lines)


def build_tax_context(
    message: str,
    annual_gross_from_profile: float = 0.0,
    monthly_outgo: float = 0.0,
    history: Optional[list[dict]] = None,
) -> str:
    """Return the tax block for this question, or "" when it isn't about tax.

    `history` (prior chat turns) lets a follow-up like "so I pay no tax then?" reuse the
    income stated earlier in the conversation. `monthly_outgo` (expenses + EMIs from the
    profile) enables an engine-computed savings figure for a hypothetical income.
    """
    if not _wants_tax_context(message):
        return ""
    cfg = load_config(TAX_CONFIG_PATH)
    blocks = [rules_summary(cfg)]

    mentioned = extract_annual_income(message)
    if mentioned is None:
        for turn in reversed(history or []):
            if turn.get("role") == "user":
                mentioned = extract_annual_income(str(turn.get("content", "")))
                if mentioned:
                    break
    months = 0
    for text in [message] + [str(t.get("content", "")) for t in reversed(history or []) if t.get("role") == "user"]:
        m = _MONTHS.search(text)
        if m:
            months = int(m.group(1))
            break

    if mentioned:
        annual, text = mentioned
        blocks.append(_calc_block(f'for the income stated in the conversation ("{text}")', annual, cfg, monthly_outgo, months))
    if annual_gross_from_profile > 0 and (not mentioned or abs(mentioned[0] - annual_gross_from_profile) > 1):
        blocks.append(_calc_block("for the user's saved profile", annual_gross_from_profile, cfg))
    return "\n".join(blocks)
