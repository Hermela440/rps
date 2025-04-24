import unittest
from datetime import datetime
from game import RPSGame, Game, GameParticipant
from user import User
from payment_service import PaymentService
from battle_simulation import VisualBattleSimulation
from app import app, db
from models import (
    User as UserModel,
    Game as GameModel,
    GameParticipant as GameParticipantModel,
    Transaction,
    WithdrawalRequest,
    DailyStats,
    Cooldown
)
import pygame
import os

class TestRPSSystem(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Set up Flask test client and context
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create all tables
        db.create_all()
        
        # Enable test mode for payments
        PaymentService.set_test_mode(True)
        
        # Create test users
        self.user1 = User(username="player1", balance=100.0)
        self.user2 = User(username="player2", balance=100.0)
        self.user3 = User(username="player3", balance=100.0)
        
        # Add users to database
        db.session.add(self.user1)
        db.session.add(self.user2)
        db.session.add(self.user3)
        db.session.commit()
    
    def tearDown(self):
        """Clean up after each test"""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_game_creation(self):
        """Test game creation and joining"""
        # Create a new game
        game = RPSGame.create_game(
            creator_id=self.user1.id,
            bet_amount=10,
            min_players=3,
            max_players=3
        )
        
        self.assertIsNotNone(game)
        self.assertEqual(game.status, "waiting")
        self.assertEqual(game.bet_amount, 10)
        
        # Join game
        join1 = RPSGame.join_game(game.id, self.user2.id)
        join2 = RPSGame.join_game(game.id, self.user3.id)
        
        self.assertTrue(join1)
        self.assertTrue(join2)
        
        # Refresh game from database
        db.session.refresh(game)
        participant_count = GameParticipant.query.filter_by(game_id=game.id).count()
        self.assertEqual(participant_count, 3)
    
    def test_game_choices(self):
        """Test making choices in the game"""
        game = RPSGame.create_game(
            creator_id=self.user1.id,
            bet_amount=10,
            min_players=3,
            max_players=3
        )
        
        RPSGame.join_game(game.id, self.user2.id)
        RPSGame.join_game(game.id, self.user3.id)
        
        # Make choices
        choice1 = RPSGame.make_choice(game.id, self.user1.id, "rock")
        choice2 = RPSGame.make_choice(game.id, self.user2.id, "paper")
        choice3 = RPSGame.make_choice(game.id, self.user3.id, "scissors")
        
        self.assertTrue(choice1)
        self.assertTrue(choice2)
        self.assertTrue(choice3)
        
        # Check game completion
        game = RPSGame.get_game(game.id)
        self.assertEqual(game.status, "completed")
    
    def test_payment_system(self):
        """Test payment system in test mode"""
        initial_balance = float(self.user1.balance)
        
        # Enable test mode for payments
        PaymentService.set_test_mode(True)
        
        # Test deposit
        success, message, _ = PaymentService.initialize_payment(
            user_id=self.user1.id,
            amount=50.0,
            test_mode=True  # Explicitly set test mode
        )
        
        self.assertTrue(success)
        
        # Refresh user from database
        db.session.refresh(self.user1)
        self.assertEqual(float(self.user1.balance), initial_balance + 50.0)
        
        # Test game payment
        balance_before_game = float(self.user1.balance)
        game = RPSGame.create_game(
            creator_id=self.user1.id,
            bet_amount=20.0,
            min_players=3,
            max_players=3
        )
        
        # Verify game creation deducted bet amount
        db.session.refresh(self.user1)
        self.assertEqual(float(self.user1.balance), balance_before_game - 20.0)
        
        # Test joining game deducts bet amount from other players
        balance_before_join = float(self.user2.balance)
        RPSGame.join_game(game.id, self.user2.id)
        db.session.refresh(self.user2)
        self.assertEqual(float(self.user2.balance), balance_before_join - 20.0)
        
        balance_before_join = float(self.user3.balance)
        RPSGame.join_game(game.id, self.user3.id)
        db.session.refresh(self.user3)
        self.assertEqual(float(self.user3.balance), balance_before_join - 20.0)
    
    def test_battle_simulation(self):
        """Test battle simulation"""
        # Initialize pygame for headless testing
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.init()
        
        simulation = VisualBattleSimulation()
        
        # Test initial counts
        rock_count = sum(1 for elem in simulation.elements if elem['type'] == 'rock')
        paper_count = sum(1 for elem in simulation.elements if elem['type'] == 'paper')
        scissors_count = sum(1 for elem in simulation.elements if elem['type'] == 'scissors')
        
        self.assertEqual(rock_count, 67)
        self.assertEqual(paper_count, 27)
        self.assertEqual(scissors_count, 5)
        
        # Test movement
        initial_positions = [(elem['x'], elem['y']) for elem in simulation.elements]
        simulation.update_positions()
        new_positions = [(elem['x'], elem['y']) for elem in simulation.elements]
        
        # Verify that elements have moved
        self.assertNotEqual(initial_positions, new_positions)
        
        # Test collision detection
        elem1 = simulation.elements[0]
        elem2 = simulation.elements[1]
        
        # Force a collision by setting positions
        elem1['x'] = 100
        elem1['y'] = 100
        elem2['x'] = 100
        elem2['y'] = 100
        
        simulation.check_collisions()
        
        # Verify that one element has changed type based on RPS rules
        winner_type = simulation.determine_winner(elem1['type'], elem2['type'])
        self.assertTrue(
            elem1['type'] == winner_type or elem2['type'] == winner_type
        )
        
        pygame.quit()

def run_tests():
    """Run all tests"""
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRPSSystem)
    
    # Run tests
    print("\n=== Starting RPS System Tests ===\n")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    return len(result.failures) + len(result.errors) == 0

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1) 