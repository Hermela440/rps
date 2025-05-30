"""Integration tests for all endpoints"""
import unittest
import json
from decimal import Decimal
from datetime import datetime
from app import app, db
from models import User, Transaction, Game, GameParticipant
from config import TEST_MODE, TEST_USER_BALANCE, MIN_DEPOSIT_AMOUNT

class TestEndpoints(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test user
        self.test_user = User(
            username="testuser",
            telegram_id=1000,
            balance=Decimal(str(TEST_USER_BALANCE)),
            full_name="Test User",
            email="test@example.com"
        )
        db.session.add(self.test_user)
        db.session.commit()
        
        # Login user
        with self.client.session_transaction() as session:
            session['user_id'] = self.test_user.id

    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_account_endpoints(self):
        """Test account management endpoints"""
        # Test account creation form
        response = self.client.get('/account/create')
        self.assertEqual(response.status_code, 200)
        
        # Test account creation
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123',
            'first_name': 'New',
            'last_name': 'User'
        }
        response = self.client.post('/account/create', json=data)
        self.assertEqual(response.status_code, 201)
        
        # Test profile endpoint
        response = self.client.get('/account/profile')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')

    def test_payment_endpoints(self):
        """Test payment related endpoints"""
        # Test payment methods
        response = self.client.get('/payment/methods')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Test deposit form
        response = self.client.get('/payment/deposit')
        self.assertEqual(response.status_code, 200)
        
        # Test deposit process
        data = {
            'user_id': self.test_user.id,
            'amount': str(MIN_DEPOSIT_AMOUNT),
            'email': self.test_user.email,
            'first_name': 'Test',
            'last_name': 'User'
        }
        response = self.client.post('/payment/deposit', data=data)
        self.assertEqual(response.status_code, 200)
        
        # Test payment initialization
        response = self.client.post('/payment/initialize', json=data)
        self.assertEqual(response.status_code, 200)
        
        # Test payment callback
        callback_data = {
            'tx_ref': 'test_ref_123',
            'status': 'success'
        }
        response = self.client.post('/payment/callback', json=callback_data)
        self.assertEqual(response.status_code, 200)
        
        # Test payment success
        response = self.client.get('/payment/success?tx_ref=test_ref_123')
        self.assertEqual(response.status_code, 200)
        
        # Test payment complete
        response = self.client.get('/payment/complete?tx_ref=test_ref_123')
        self.assertEqual(response.status_code, 200)
        
        # Test payment error
        response = self.client.get('/payment/error?message=test_error')
        self.assertEqual(response.status_code, 200)

    def test_main_endpoints(self):
        """Test main application endpoints"""
        # Test deposit page
        response = self.client.get('/deposit')
        self.assertEqual(response.status_code, 200)
        
        # Test deposit process
        data = {'amount': str(MIN_DEPOSIT_AMOUNT)}
        response = self.client.post('/deposit', data=data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Test withdraw page
        response = self.client.get('/withdraw')
        self.assertEqual(response.status_code, 200)
        
        # Test withdraw process
        data = {
            'amount': '10.00',
            'wallet_address': 'test_wallet_123'
        }
        response = self.client.post('/withdraw', data=data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Test payment status
        response = self.client.get('/payment/status/test_payment_123')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('status', data)
        
        # Test process payment
        response = self.client.get('/process_payment/1')
        self.assertEqual(response.status_code, 200)

    def test_admin_endpoints(self):
        """Test admin endpoints"""
        # Test transaction verification
        response = self.client.post('/admin/api/transaction/1/verify?admin=true')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('status', data)

    def test_game_endpoints(self):
        """Test game related endpoints"""
        # Create a test game
        game = Game(
            creator_id=self.test_user.id,
            bet_amount=Decimal('10.00'),
            status='waiting',
            min_players=3,
            max_players=3
        )
        db.session.add(game)
        db.session.commit()
        
        # Test game creation
        self.assertIsNotNone(game.id)
        self.assertEqual(game.status, 'waiting')
        
        # Test game participant
        participant = GameParticipant(
            game_id=game.id,
            user_id=self.test_user.id,
            move='rock'
        )
        db.session.add(participant)
        db.session.commit()
        
        # Verify participant was added
        self.assertIsNotNone(participant.id)
        self.assertEqual(participant.move, 'rock')

def run_tests():
    """Run all endpoint tests"""
    unittest.main()

if __name__ == '__main__':
    run_tests() 