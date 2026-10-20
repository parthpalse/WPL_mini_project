"""SPA + /api endpoints: login gating and per-user MongoDB persistence."""
from unittest.mock import patch

import pytest
from app import create_app


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'spa-test-secret',
        'MONGODB_URI': 'mongomock://localhost/bankease_spa_test',
    })
    yield app
    app.extensions['mongo_client'].close()


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, email='asha@example.com'):
    client.post('/auth/register', data={'email': email, 'password': 'pw12345', 'confirm_password': 'pw12345'})


def test_spa_and_api_require_login(client):
    res = client.get('/profile')
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']

    res = client.get('/api/profile')
    assert res.status_code == 401
    assert res.get_json()['error'] == 'Login required'


def test_login_lands_on_spa_with_account_bar(client):
    _register(client)
    res = client.get('/auth/login')
    assert res.headers['Location'] == '/'
    html = client.get('/profile').get_data(as_text=True)
    assert 'asha@example.com' in html
    assert '/auth/logout' in html


def test_profile_and_goals_persist_per_user(app, client):
    _register(client)
    assert client.get('/api/profile').get_json()['name'] == 'asha'

    client.put('/api/profile', json={'monthlyGrossIncome': 99000})
    client.put('/api/goals', json=[{'id': 'x', 'title': 'Bike', 'target': 90000, 'saved': 0, 'deadline': '2027-01'}])

    doc = app.extensions['mongo_db'].user_data.find_one({})
    assert doc['profile']['monthlyGrossIncome'] == 99000
    assert [g['title'] for g in doc['goals']] == ['Bike']

    # A second user starts from defaults and can't see the first user's data
    client.get('/auth/logout')
    _register(client, 'ravi@example.com')
    assert client.get('/api/profile').get_json()['monthlyGrossIncome'] == 150000
    assert 'Bike' not in [g['title'] for g in client.get('/api/goals').get_json()]

    # Deleting every goal is saved as an empty list, not reset to defaults
    client.put('/api/goals', json=[])
    assert client.get('/api/goals').get_json() == []


def test_put_goals_rejects_non_list(client):
    _register(client)
    assert client.put('/api/goals', json={'title': 'nope'}).status_code == 400


@patch('app.routes.api.is_configured', return_value=True)
@patch('app.routes.api.chat_sync')
def test_assistant_chat_uses_llm(mock_chat, _configured, client):
    mock_chat.return_value = {'response': 'Put ₹20,000 into SIPs.', 'guardrail_warnings': []}
    _register(client)
    res = client.post('/api/assistant/chat', json={'messages': [
        {'role': 'user', 'content': 'hi'},
        {'role': 'assistant', 'content': 'hello'},
        {'role': 'user', 'content': 'Where should I invest?'},
    ]})
    assert res.get_json()['content'] == 'Put ₹20,000 into SIPs.'
    args = mock_chat.call_args
    assert args.args[0] == 'Where should I invest?'
    assert len(args.args[1]) == 2  # prior turns passed as history
    assert 'Equity MFs' in args.kwargs['allocation_summary']


@patch('app.routes.api.is_configured', return_value=True)
@patch('app.routes.api.chat_sync')
def test_assistant_chat_falls_back_when_llm_fails(mock_chat, _configured, client):
    mock_chat.return_value = {'response': '\n\n⚠️ Chat unavailable — could not reach the LLM provider.', 'guardrail_warnings': []}
    _register(client)
    res = client.post('/api/assistant/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]})
    assert 'Net Investable Surplus' in res.get_json()['content']
