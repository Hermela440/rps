"""Test configuration and fixtures"""
import pytest
from app import create_app, db
from models import User
from decimal import Decimal

@pytest.fixture
def app():
    """Create and configure a Flask app for testing"""
    app = create_app('testing')
    
    # Create test database
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()

@pytest.fixture
def test_user(app):
    """Create a test user"""
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            balance=Decimal('0.00')
        )
        db.session.add(user)
        db.session.commit()
        return user

@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user"""
    return {
        'Authorization': f'Bearer {test_user.generate_token()}'
    } 