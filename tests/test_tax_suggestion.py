"""Suggested monthly tax (FY 2026-27), planner projection params and market statuses."""
from unittest.mock import patch

from app.engine.tax_suggestion import suggest_monthly_tax
from tests.test_spa_api import app, client, _register  # noqa: F401  (fixtures)


def test_zero_tax_up_to_12_75_lakh_salary():
    res = suggest_monthly_tax(100_000)  # 12 L a year, taxable 11.25 L, under the 87A limit
    assert res['monthlyTax'] == 0
    assert res['zeroTaxUpToAnnual'] == 1_275_000


def test_tax_above_rebate_with_marginal_relief_and_high_income():
    just_over = suggest_monthly_tax(110_000)  # 13.2 L a year, taxable 12.45 L
    assert just_over['annualTax'] == 46_800  # relief caps tax at the 45,000 excess over 12 L taxable, plus 4% cess
    rich = suggest_monthly_tax(200_000)  # 24 L a year
    assert rich['annualTax'] == 292_500  # slabs 20k+40k+60k+80k+81,250 = 2,81,250, plus 4% cess
    assert rich['monthlyTax'] == round(rich['annualTax'] / 12)


def test_negative_income_clamped():
    assert suggest_monthly_tax(-5)['monthlyTax'] == 0


def test_tax_suggestion_endpoint(client):
    _register(client)
    assert client.get('/api/tax-suggestion?monthlyGross=200000').get_json()['regime'] == 'new'
    assert client.get('/api/tax-suggestion?monthlyGross=abc').status_code == 400
    assert client.get('/api/tax-suggestion?monthlyGross=-1').status_code == 400


def test_projection_follows_monthly_and_allocation(client):
    _register(client)
    def final(qs):
        return client.get('/api/projection?' + qs).get_json()[-1]['expected']
    equity = final('monthly=10000&alloc=equity:100')
    debt = final('monthly=10000&alloc=debt:100')
    assert equity > debt > 0
    assert final('monthly=20000&alloc=equity:100') > equity
    assert final('monthly=10000&alloc=bogus:1') > 0  # unparseable mix falls back to the risk-based one


@patch('app.routes.api.get_quote')
def test_market_statuses(mock_quote, client):
    _register(client)
    mock_quote.side_effect = lambda sym: {'current': 100.0, 'change_pct': 1.5} if sym == 'TCS.NS' else {}
    data = {m['symbol']: m for m in client.get('/api/market').get_json()}
    assert data['TCS.NS']['status'] == 'ok' and data['TCS.NS']['value'] == 100.0
    assert data['INFY.NS']['status'] == 'unavailable' and data['INFY.NS']['value'] is None
