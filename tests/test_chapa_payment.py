"""Test suite for Chapa payment integration"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from decimal import Decimal
import json

from app import create_app, db
from models import User, Transaction
from chapa_payment import ChapaPayment
from config import MIN_DEPOSIT_AMOUNT, MAX_DEPOSIT_AMOUNT

class TestChapaPayment(unittest.TestCase):
    """Test cases for Chapa payment integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        self.user = User(
            username='testuser',
            email='test@example.com',
            balance=Decimal('0.00')
        )
        db.session.add(self.user)
        db.session.commit()
    
    def tearDown(self):
        """Clean up test environment"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    @patch('chapa_payment.chapa.initialize')
    def test_initialize_payment_success(self, mock_initialize):
        """Test successful payment initialization"""
        # Mock Chapa API response
        mock_initialize.return_value = {
            "status": "success",
            "data": {
                "checkout_url": "https://checkout.chapa.co/test"
            }
        }
        
        # Test payment initialization
        success, message, checkout_url = ChapaPayment.initialize_payment(
            user_id=self.user.id,
            amount=100.00,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            callback_url="https://example.com/callback",
            return_url="https://example.com/return"
        )
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Payment initialized successfully")
        self.assertEqual(checkout_url, "https://checkout.chapa.co/test")
        
        # Check transaction record
        transaction = Transaction.query.filter_by(user_id=self.user.id).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.status, "pending")
    
    @patch('chapa_payment.chapa.initialize')
    def test_initialize_payment_with_wallet(self, mock_initialize):
        """Test payment initialization with preferred wallet"""
        # Mock Chapa API response
        mock_initialize.return_value = {
            "status": "success",
            "data": {
                "checkout_url": "https://checkout.chapa.co/test"
            }
        }
        
        # Test payment initialization with Telebirr
        success, message, checkout_url = ChapaPayment.initialize_payment(
            user_id=self.user.id,
            amount=100.00,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            callback_url="https://example.com/callback",
            return_url="https://example.com/return",
            preferred_payment="telebirr"
        )
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Payment initialized successfully")
        
        # Check payment data
        transaction = Transaction.query.filter_by(user_id=self.user.id).first()
        payment_data = json.loads(transaction.payment_data)
        self.assertEqual(payment_data.get("preferred_payment"), "telebirr")
    
    def test_initialize_payment_amount_validation(self):
        """Test payment amount validation"""
        # Test minimum amount
        success, message, _ = ChapaPayment.initialize_payment(
            user_id=self.user.id,
            amount=MIN_DEPOSIT_AMOUNT - 1,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            callback_url="https://example.com/callback",
            return_url="https://example.com/return"
        )
        self.assertFalse(success)
        self.assertIn("Minimum deposit amount", message)
        
        # Test maximum amount
        success, message, _ = ChapaPayment.initialize_payment(
            user_id=self.user.id,
            amount=MAX_DEPOSIT_AMOUNT + 1,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            callback_url="https://example.com/callback",
            return_url="https://example.com/return"
        )
        self.assertFalse(success)
        self.assertIn("Maximum deposit amount", message)
    
    @patch('chapa_payment.chapa.verify')
    def test_verify_payment_success(self, mock_verify):
        """Test successful payment verification"""
        # Create test transaction
        transaction = Transaction(
            user_id=self.user.id,
            amount=Decimal('100.00'),
            type="deposit",
            status="pending",
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        
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
        
        # Test payment verification
        success, message, payment_data = ChapaPayment.verify_payment(transaction.reference)
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Payment verified successfully")
        self.assertEqual(payment_data["status"], "completed")
        self.assertEqual(payment_data["payment_method"], "telebirr")
        
        # Check transaction and user balance
        transaction = Transaction.query.get(transaction.id)
        self.assertEqual(transaction.status, "completed")
        self.assertIsNotNone(transaction.completed_at)
        
        user = User.query.get(self.user.id)
        self.assertEqual(user.balance, Decimal('100.00'))
    
    @patch('chapa_payment.chapa.verify')
    def test_verify_payment_pending(self, mock_verify):
        """Test pending payment verification"""
        # Create test transaction
        transaction = Transaction(
            user_id=self.user.id,
            amount=Decimal('100.00'),
            type="deposit",
            status="pending",
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Mock Chapa API response
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "status": "pending",
                "payment_type": "telebirr",
                "amount": "100.00",
                "currency": "ETB"
            }
        }
        
        # Test payment verification
        success, message, payment_data = ChapaPayment.verify_payment(transaction.reference)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "Payment is still pending")
        self.assertEqual(payment_data["status"], "pending")
        
        # Check transaction status
        transaction = Transaction.query.get(transaction.id)
        self.assertEqual(transaction.status, "pending")
    
    @patch('chapa_payment.chapa.get_payment_methods')
    def test_get_payment_methods(self, mock_get_methods):
        """Test getting supported payment methods"""
        # Mock Chapa API response
        mock_get_methods.return_value = {
            "status": "success",
            "data": [
                {
                    "code": "telebirr",
                    "name": "Telebirr",
                    "description": "Ethio Telecom"
                },
                {
                    "code": "cbe_birr",
                    "name": "CBE Birr",
                    "description": "Commercial Bank"
                }
            ]
        }
        
        # Test getting payment methods
        methods = ChapaPayment.get_supported_payment_methods()
        
        # Assertions
        self.assertEqual(len(methods), 2)
        self.assertEqual(methods[0]["code"], "telebirr")
        self.assertEqual(methods[1]["code"], "cbe_birr")
    
    @patch('chapa_payment.chapa.get_transaction_logs')
    def test_get_transaction_logs(self, mock_get_logs):
        """Test getting transaction logs"""
        # Create test transaction
        transaction = Transaction(
            user_id=self.user.id,
            amount=Decimal('100.00'),
            type="deposit",
            status="pending",
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Mock Chapa API response
        mock_get_logs.return_value = {
            "status": "success",
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "status": "pending",
                    "message": "Payment initiated"
                },
                {
                    "timestamp": "2024-01-01T00:01:00Z",
                    "status": "success",
                    "message": "Payment completed"
                }
            ]
        }
        
        # Test getting transaction logs
        logs = ChapaPayment.get_transaction_logs(transaction.reference)
        
        # Assertions
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["status"], "pending")
        self.assertEqual(logs[1]["status"], "success")

if __name__ == '__main__':
    unittest.main() 