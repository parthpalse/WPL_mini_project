import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    with app.test_client() as client:
        yield client


def test_health_check_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get('status') == 'healthy'
    assert data.get('service') == 'bankease'
