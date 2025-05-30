"""Test suite for RPS game system"""
import sqlalchemy_patch  # Import patch before SQLAlchemy
import unittest
from flask import Flask
from extensions import db
from app import create_app
from models import User, Room, RoomPlayer, Transaction
import json

class TestRPSSystem(unittest.TestCase):
    """Test cases for RPS game system"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            # Create test user
            self.test_user = User(
                username='testuser',
                email='test@example.com',
                password='testpass',
                full_name='Test User',
                balance=100.0
            )
            db.session.add(self.test_user)
            db.session.commit()
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_game_creation(self):
        """Test game creation and joining"""
        with self.app.app_context():
            # Create a new room
            room = Room(
                room_code='TEST123',
                bet_amount=10.0,
                creator_id=self.test_user.id
            )
            db.session.add(room)
            db.session.commit()
            
            # Verify room was created
            self.assertIsNotNone(room.id)
            self.assertEqual(room.room_code, 'TEST123')
            self.assertEqual(room.bet_amount, 10.0)
    
    def test_game_choices(self):
        """Test making choices in the game"""
        with self.app.app_context():
            # Create a room
            room = Room(
                room_code='TEST123',
                bet_amount=10.0,
                creator_id=self.test_user.id
            )
            db.session.add(room)
            db.session.commit()
            
            # Add player to room
            player = RoomPlayer(
                room_id=room.id,
                user_id=self.test_user.id,
                move='rock'
            )
            db.session.add(player)
            db.session.commit()
            
            # Verify player was added
            self.assertIsNotNone(player.id)
            self.assertEqual(player.move, 'rock')
    
    def test_battle_simulation(self):
        """Test battle simulation"""
        with self.app.app_context():
            # Create two players
            player1 = User(
                username='player1',
                email='player1@example.com',
                password='testpass',
                full_name='Player One',
                balance=100.0
            )
            player2 = User(
                username='player2',
                email='player2@example.com',
                password='testpass',
                full_name='Player Two',
                balance=100.0
            )
            db.session.add_all([player1, player2])
            db.session.commit()
            
            # Create a room
            room = Room(
                room_code='BATTLE',
                bet_amount=20.0,
                creator_id=player1.id
            )
            db.session.add(room)
            db.session.commit()
            
            # Add players to room
            room_player1 = RoomPlayer(
                room_id=room.id,
                user_id=player1.id,
                move='rock'
            )
            room_player2 = RoomPlayer(
                room_id=room.id,
                user_id=player2.id,
                move='scissors'
            )
            db.session.add_all([room_player1, room_player2])
            db.session.commit()
            
            # Verify players were added
            self.assertEqual(room.players.count(), 2)
    
    def test_payment_system(self):
        """Test payment system in test mode"""
        with self.app.app_context():
            # Create a deposit transaction
            transaction = Transaction(
                user_id=self.test_user.id,
                tx_ref='TEST123',
                type='deposit',
                amount=50.0,
                status='completed'
            )
            db.session.add(transaction)
            db.session.commit()
            
            # Verify transaction was created
            self.assertIsNotNone(transaction.id)
            self.assertEqual(transaction.amount, 50.0)
            self.assertEqual(transaction.status, 'completed')

if __name__ == '__main__':
    unittest.main() 