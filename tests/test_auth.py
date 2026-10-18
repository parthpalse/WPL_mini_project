import pytest
from app import create_app, db
from app.models.models import User


@pytest.fixture
def auth_app():
    app = create_app({
        'TESTING': True,
        'LOGIN_DISABLED': False,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'auth-test-secret',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


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
