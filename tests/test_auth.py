import pytest
from app import create_app


@pytest.fixture
def auth_app():
    app = create_app({
        'TESTING': True,
        'LOGIN_DISABLED': False,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'auth-test-secret',
        'MONGODB_URI': 'mongomock://localhost/bankease_test'
    })
    yield app
    app.extensions['mongo_client'].close()


@pytest.fixture
def auth_client(auth_app):
    return auth_app.test_client()


def test_register_and_login_flow(auth_client):
    # 1. Register
    reg_res = auth_client.post('/auth/register', data={
        'email': 'user@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert reg_res.status_code == 200

    # 2. Logout
    logout_res = auth_client.get('/auth/logout', follow_redirects=True)
    assert logout_res.status_code == 200

    # 3. Login
    login_res = auth_client.post('/auth/login', data={
        'email': 'user@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert login_res.status_code == 200


def test_login_invalid_credentials(auth_client):
    res = auth_client.post('/auth/login', data={
        'email': 'wrong@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Please check your login details' in html


def test_register_duplicate_email(auth_client):
    data = {'email': 'dup@example.com', 'password': 'pw12345', 'confirm_password': 'pw12345'}
    auth_client.post('/auth/register', data=data)
    auth_client.get('/auth/logout')
    res = auth_client.post('/auth/register', data=data, follow_redirects=True)
    assert 'Email address already exists' in res.get_data(as_text=True)


def test_quick_wizard_saves_profile(auth_app, auth_client):
    auth_client.post('/auth/register', data={
        'email': 'saver@example.com', 'password': 'pw12345', 'confirm_password': 'pw12345'
    })
    auth_client.post('/wizard/quick', data={'monthly_income': '80000', 'monthly_rent': '20000'})

    db = auth_app.extensions['mongo_db']
    user = db.users.find_one({'email': 'saver@example.com'})
    profile = db.financial_profiles.find_one({'user_id': user['_id']})
    assert profile is not None
    assert profile['wizard_data']['income_amount'] == '80000'
