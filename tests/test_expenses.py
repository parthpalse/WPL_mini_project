"""Expense aggregation tests."""
from app.engine.expenses import calculate_expenses


class TestExpenses:
    def test_basic_fixed_and_variable(self):
        fixed = [
            {'name': 'Rent', 'amount': 15000},
            {'name': 'Insurance', 'amount': 2000}
        ]
        variable = [
            {'name': 'Groceries', 'amount': 8000},
            {'name': 'Transport', 'amount': 3000}
        ]
        result = calculate_expenses(fixed, variable)
        assert result['total_fixed_monthly'] == 17000
        assert result['total_variable_monthly'] == 11000
        assert result['total_monthly'] == 28000
        assert result['total_annual'] == 336000

    def test_only_fixed(self):
        fixed = [{'name': 'Rent', 'amount': 20000}]
        result = calculate_expenses(fixed=fixed)
        assert result['total_fixed_monthly'] == 20000
        assert result['total_variable_monthly'] == 0
        assert result['total_monthly'] == 20000

    def test_empty_expenses(self):
        result = calculate_expenses()
        assert result['total_monthly'] == 0
        assert result['total_annual'] == 0

    def test_single_expense(self):
        result = calculate_expenses(fixed=[{'name': 'Rent', 'amount': 10000}])
        assert result['total_monthly'] == 10000
        assert result['total_annual'] == 120000
