"""Integration tests for payment routes"""
import json
from unittest.mock import patch
from decimal import Decimal
from app import app, db
from models import User, Transaction
from config import TEST_MODE, TEST_USER_BALANCE

def setup_test_client():
    """Set up test client with test database"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        db.create_all()
        # Create test user
        test_user = User(
            username="testuser",
            telegram_id=1000,
            balance=TEST_USER_BALANCE,
            full_name="Test User",
            email="test@example.com"
        )
        db.session.add(test_user)
        db.session.commit()
        
        return app.test_client(), test_user

def test_get_payment_methods(client, auth_headers):
    """Test getting supported payment methods"""
    with patch('chapa_payment.chapa.get_payment_methods') as mock_get_methods:
        # Mock Chapa API response
        mock_get_methods.return_value = {
            "status": "success",
            "data": [
                {
                    "code": "telebirr",
                    "name": "Telebirr",
                    "description": "Ethio Telecom"
                }
            ]
        }
        
        # Test API endpoint
        response = client.get('/payment/methods', headers=auth_headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert len(data['data']) == 1
        assert data['data'][0]['code'] == 'telebirr'

def test_initiate_deposit_get(client, auth_headers):
    """Test deposit form page"""
    with patch('chapa_payment.chapa.get_payment_methods') as mock_get_methods:
        # Mock Chapa API response
        mock_get_methods.return_value = {
            "status": "success",
            "data": [
                {
                    "code": "telebirr",
                    "name": "Telebirr",
                    "description": "Ethio Telecom"
                }
            ]
        }
        
        # Test GET request
        response = client.get('/payment/deposit', headers=auth_headers)
        
        assert response.status_code == 200
        assert b'Deposit Funds' in response.data
        assert b'Telebirr' in response.data

def test_initiate_deposit_post(client, auth_headers, test_user):
    """Test deposit initiation"""
    with patch('chapa_payment.chapa.initialize') as mock_initialize:
        # Mock Chapa API response
        mock_initialize.return_value = {
            "status": "success",
            "data": {
                "checkout_url": "https://checkout.chapa.co/test"
            }
        }
        
        # Test POST request
        response = client.post('/payment/deposit',
                             headers=auth_headers,
                             data={
                                 'user_id': test_user.id,
                                 'amount': '100.00',
                                 'email': 'test@example.com',
                                 'first_name': 'Test',
                                 'last_name': 'User',
                                 'preferred_payment': 'telebirr'
                             },
                             follow_redirects=True)
        
        assert response.status_code == 200
        assert b'checkout.chapa.co' in response.data

def test_payment_callback(client, auth_headers, test_user):
    """Test payment callback handling"""
    with patch('chapa_payment.chapa.verify') as mock_verify:
        # Mock Chapa API response
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "status": "success",
                "payment_type": "telebirr",
                "amount": "100.00",
                "currency": "ETB"
            }
        }
        
        # Test callback
        response = client.post('/payment/callback',
                             headers=auth_headers,
                             json={
                                 'tx_ref': 'test-ref-123',
                                 'status': 'success'
                             })
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'success'

def test_payment_success(client, auth_headers):
    """Test successful payment redirect"""
    with patch('chapa_payment.chapa.verify') as mock_verify:
        # Mock Chapa API response
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "status": "success",
                "payment_type": "telebirr",
                "amount": "100.00",
                "currency": "ETB"
            }
        }
        
        # Test success redirect
        response = client.get('/payment/success?tx_ref=test-ref-123',
                            headers=auth_headers,
                            follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Payment completed successfully' in response.data

def test_payment_error(client, auth_headers):
    """Test payment error page"""
    # Test error page
    response = client.get('/payment/error?message=Payment%20failed',
                         headers=auth_headers)
    
    assert response.status_code == 200
    assert b'Payment failed' in response.data

def test_payment_complete(client, auth_headers):
    """Test payment completion page"""
    with patch('chapa_payment.chapa.verify') as mock_verify:
        # Mock Chapa API response
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "status": "success",
                "payment_type": "telebirr",
                "amount": "100.00",
                "currency": "ETB"
            }
        }
        
        # Test completion page
        response = client.get('/payment/complete?tx_ref=test-ref-123',
                            headers=auth_headers)
        
        assert response.status_code == 200
        assert b'Payment completed successfully' in response.data 