import unittest
from decimal import Decimal
from datetime import datetime
from app import app, db
from models import User, Transaction, WithdrawalRequest
from payments import PaymentSystem

class TestTransactions(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            
            # Create test user
            self.test_user = User(
                username='test_user',
                balance=1000.0,
                created_at=datetime.utcnow()
            )
            db.session.add(self.test_user)
            db.session.commit()

    def tearDown(self):
        """Clean up after each test"""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_deposit(self):
        """Test creating a deposit transaction"""
        with app.app_context():
            amount = 500.0
            success, result = PaymentSystem.create_deposit(self.test_user.id, amount)
            
            self.assertTrue(success)
            self.assertIn('payment_url', result)
            self.assertIn('reference', result)
            
            # Verify transaction was created
            transaction = Transaction.query.filter_by(
                user_id=self.test_user.id,
                transaction_type='deposit'
            ).first()
            
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.amount, amount)
            self.assertEqual(transaction.status, 'pending')

    def test_process_deposit_callback(self):
        """Test processing a successful deposit callback"""
        with app.app_context():
            # Create initial transaction
            transaction = Transaction(
                user_id=self.test_user.id,
                amount=500.0,
                transaction_type='deposit',
                status='pending',
                reference_id='test_deposit_123'
            )
            db.session.add(transaction)
            initial_balance = self.test_user.balance
            
            # Process callback
            success = PaymentSystem.process_deposit_callback('test_deposit_123', 'success')
            self.assertTrue(success)
            
            # Verify transaction was updated
            transaction = Transaction.query.filter_by(reference_id='test_deposit_123').first()
            self.assertEqual(transaction.status, 'completed')
            
            # Verify user balance was updated
            user = User.query.get(self.test_user.id)
            self.assertEqual(user.balance, initial_balance + 500.0)

    def test_create_withdrawal(self):
        """Test creating a withdrawal request"""
        with app.app_context():
            amount = 200.0
            wallet_address = 'test_wallet_123'
            
            success, result = PaymentSystem.create_withdrawal(
                self.test_user.id,
                amount,
                wallet_address
            )
            
            self.assertTrue(success)
            self.assertIn('reference', result)
            
            # Verify transaction and withdrawal request were created
            transaction = Transaction.query.filter_by(
                user_id=self.test_user.id,
                transaction_type='withdraw'
            ).first()
            
            withdrawal = WithdrawalRequest.query.filter_by(
                user_id=self.test_user.id,
                amount=amount
            ).first()
            
            self.assertIsNotNone(transaction)
            self.assertIsNotNone(withdrawal)
            self.assertEqual(transaction.amount, -amount)  # Negative for withdrawals
            self.assertEqual(withdrawal.wallet_address, wallet_address)
            
            # Verify user balance was updated
            user = User.query.get(self.test_user.id)
            self.assertEqual(user.balance, 800.0)  # 1000 - 200

    def test_withdrawal_limits(self):
        """Test withdrawal amount validation"""
        with app.app_context():
            # Test amount too low
            success, result = PaymentSystem.create_withdrawal(
                self.test_user.id,
                0.5,  # Below minimum
                'test_wallet'
            )
            self.assertFalse(success)
            self.assertIn('minimum', result.lower())
            
            # Test amount too high
            success, result = PaymentSystem.create_withdrawal(
                self.test_user.id,
                1000000.0,  # Above maximum
                'test_wallet'
            )
            self.assertFalse(success)
            self.assertIn('maximum', result.lower())
            
            # Test insufficient balance
            success, result = PaymentSystem.create_withdrawal(
                self.test_user.id,
                2000.0,  # More than user balance
                'test_wallet'
            )
            self.assertFalse(success)
            self.assertIn('insufficient', result.lower())

    def test_daily_transaction_limits(self):
        """Test daily transaction limits"""
        with app.app_context():
            # Create multiple deposits to hit daily limit
            for _ in range(5):
                success, result = PaymentSystem.create_deposit(
                    self.test_user.id,
                    200.0
                )
                self.assertTrue(success)
            
            # Try one more deposit
            success, result = PaymentSystem.create_deposit(
                self.test_user.id,
                200.0
            )
            self.assertFalse(success)
            self.assertIn('daily limit', result.lower())

if __name__ == '__main__':
    unittest.main() 