"""Test suite for account creation and management"""
import unittest
from unittest.mock import patch
from datetime import datetime
from decimal import Decimal
import json

from app import create_app, db
from models import User, Transaction
from config import MIN_DEPOSIT_AMOUNT

class TestAccount(unittest.TestCase):
    """Test cases for account management"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Test client
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up test environment"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_create_account_success(self):
        """Test successful account creation"""
        # Test data
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        # Create account
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['message'], 'Account created successfully')
        
        # Check user in database
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.balance, Decimal('0.00'))
    
    def test_create_account_duplicate_username(self):
        """Test account creation with duplicate username"""
        # Create first user
        user = User(
            username='existinguser',
            email='existing@example.com',
            password='Test123!'
        )
        db.session.add(user)
        db.session.commit()
        
        # Try to create duplicate user
        data = {
            'username': 'existinguser',
            'email': 'new@example.com',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Username already exists', data['message'])
    
    def test_create_account_duplicate_email(self):
        """Test account creation with duplicate email"""
        # Create first user
        user = User(
            username='user1',
            email='existing@example.com',
            password='Test123!'
        )
        db.session.add(user)
        db.session.commit()
        
        # Try to create user with duplicate email
        data = {
            'username': 'user2',
            'email': 'existing@example.com',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Email already exists', data['message'])
    
    def test_create_account_invalid_password(self):
        """Test account creation with invalid password"""
        # Test data with weak password
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'weak',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Password must be at least 8 characters', data['message'])
    
    def test_create_account_missing_fields(self):
        """Test account creation with missing required fields"""
        # Test data missing email
        data = {
            'username': 'newuser',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Missing required field', data['message'])
    
    def test_create_account_with_initial_deposit(self):
        """Test account creation with initial deposit"""
        # Test data with initial deposit
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User',
            'initial_deposit': '100.00'
        }
        
        with patch('chapa_payment.chapa.initialize') as mock_initialize:
            # Mock Chapa API response
            mock_initialize.return_value = {
                "status": "success",
                "data": {
                    "checkout_url": "https://checkout.chapa.co/test"
                }
            }
            
            # Create account with deposit
            response = self.client.post('/account/create',
                                      data=json.dumps(data),
                                      content_type='application/json')
            
            # Assertions
            self.assertEqual(response.status_code, 201)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'success')
            self.assertIn('checkout_url', data)
            
            # Check user in database
            user = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.balance, Decimal('0.00'))  # Balance should be 0 until deposit is verified
            
            # Check transaction record
            transaction = Transaction.query.filter_by(user_id=user.id).first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.amount, Decimal('100.00'))
            self.assertEqual(transaction.status, 'pending')
    
    def test_create_account_invalid_initial_deposit(self):
        """Test account creation with invalid initial deposit amount"""
        # Test data with invalid deposit amount
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'Test123!',
            'first_name': 'New',
            'last_name': 'User',
            'initial_deposit': str(MIN_DEPOSIT_AMOUNT - 1)
        }
        
        response = self.client.post('/account/create',
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Minimum deposit amount', data['message'])

if __name__ == '__main__':
    unittest.main() 