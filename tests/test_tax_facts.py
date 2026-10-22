from unittest.mock import patch, MagicMock

from app.llm import chat
from app.llm.tax_facts import build_tax_context, extract_annual_income, is_tax_question


def test_monthly_income_is_annualised():
    assert extract_annual_income("if I earn 1 lakh monthly is there any tax")[0] == 1_200_000


def test_lpa_and_per_annum_and_comma_amounts():
    assert extract_annual_income("12 LPA tax?")[0] == 1_200_000
    assert extract_annual_income("30 lakh per annum which regime")[0] == 3_000_000
    assert extract_annual_income("salary 50,000 per month tax")[0] == 600_000


def test_amount_without_period_is_not_guessed():
    assert extract_annual_income("I earn 5 lakh, tax?") is None


def test_non_tax_question_adds_no_context():
    assert not is_tax_question("How should I split my surplus?")
    assert build_tax_context("How should I split my surplus?") == ""


def test_one_lakh_monthly_pays_zero_tax_in_new_regime():
    ctx = build_tax_context("if I earn 1 lakh monthly is there any tax i have to pay?")
    assert "annual gross ₹12,00,000" in ctx
    assert "New regime: taxable income ₹11,25,000" in ctx
    assert "total tax incl. cess ₹0" in ctx
    assert "up to ₹12,75,000 a year pays zero income tax" in ctx


def test_profile_income_is_used_when_question_has_no_figure():
    ctx = build_tax_context("how much tax do I pay?", annual_gross_from_profile=2_400_000)
    assert "saved profile: annual gross ₹24,00,000" in ctx


@patch("app.llm.chat.requests.post")
def test_tax_context_reaches_the_model_and_verifies(mock_post):
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.iter_lines.return_value = iter([
        'data: {"choices":[{"delta":{"content":"Your taxable income is ₹11,25,000 so tax is ₹0."}}]}',
        "data: [DONE]",
    ])
    mock_post.return_value = resp
    msg = "if I earn 1 lakh monthly is there any tax?"
    tax_ctx = build_tax_context(msg)

    result = chat.chat_sync(msg, [], {"monthly_surplus": 1}, tax_context=tax_ctx)

    sent = mock_post.call_args.kwargs["json"]["messages"][-1]["content"]
    assert "[TAX CALC" in sent and "₹11,25,000" in sent
    assert result["guardrail_warnings"] == []


def test_guardrail_accepts_space_grouped_indian_numbers():
    ctx = build_tax_context("if I earn 1 lakh monthly is there any tax?")
    block = chat._build_context_block({"monthly_surplus": 1}, "", "", ctx)
    reply = "Taxable income is ₹11\u202f25\u202f000 after the ₹75 000 deduction, so tax is ₹0."
    assert chat.validate_response_numbers(reply, block) == []


def test_period_word_after_amount_beats_nearby_year():
    msg = "but if 2 lakhs a month then my year salary is double still i dont have any taxes"
    assert extract_annual_income(msg)[0] == 2_400_000


def test_followup_reuses_income_from_history():
    history = [{"role": "user", "content": "if my income per month is 2 lakh what will be my tax"}]
    ctx = build_tax_context("so do I pay no taxes then?", history=history)
    assert "annual gross ₹24,00,000" in ctx


def test_savings_figure_is_computed_by_engine():
    ctx = build_tax_context("how much can i save in 2 months if I earn 2 lakh per month", monthly_outgo=62000)
    assert "Monthly take-home after tax (new regime): ₹1,75,625" in ctx
    assert "monthly surplus at this income would be ₹1,13,625, so 2 months of saving = ₹2,27,250" in ctx


def test_rules_include_capital_gains():
    ctx = build_tax_context("what tax on equity gains? 12 LPA")
    assert "LTCG 12.5%" in ctx


def test_guardrail_accepts_mixed_space_and_comma_grouping():
    ctx = build_tax_context("tax if I earn 2 lakh per month, how much can I save in 2 months?", monthly_outgo=62000)
    block = chat._build_context_block({"monthly_surplus": 1}, "", "", ctx)
    reply = "Tax is ₹2 92,500, take-home ₹1 75,625, surplus ₹1,13,625, two months ₹2 27,250."
    assert chat.validate_response_numbers(reply, block) == []
