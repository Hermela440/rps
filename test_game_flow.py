import sys
from app import app, db
from models import User, Game, GameParticipant
from game import RPSGame
import time
from datetime import datetime

def create_test_users():
    """Create test users A, B, and C"""
    users = []
    for i, username in enumerate(['A', 'B', 'C']):
        user = User(
            username=username,
            telegram_id=1000 + i,  # Using dummy telegram IDs for testing
            balance=1000,
            games_played=0,
            games_won=0,
            total_winnings=0
        )
        db.session.add(user)
    db.session.commit()
    return User.query.all()

def print_game_status(game_id):
    """Print the current status of the game"""
    game = db.session.get(Game, game_id)
    if game:
        print(f"Room {game_id} Status: {game.status}")
        participants = GameParticipant.query.filter_by(game_id=game_id).all()
        for p in participants:
            user = db.session.get(User, p.user_id)
            print(f"Player {user.username}: {p.choice if p.choice else 'not chosen'}")
    else:
        print("Game not found")

def simulate_basic_game():
    """Simulate a basic game flow with three players"""
    # Clean up any existing data
    GameParticipant.query.delete()
    Game.query.delete()
    User.query.delete()
    db.session.commit()
    
    # Create test users
    users = create_test_users()
    print("Created test users:", [u.username for u in users])
    
    # Player A creates a game with bet amount 100
    game, message = RPSGame.create_game(bet_amount=100, created_by_user_id=users[0].id)
    if not game:
        print(f"Failed to create game: {message}")
        return
    game_id = game.id
    print(f"Player A created game {game_id}")
    print_game_status(game_id)
    
    # Player B joins the game
    success, message = RPSGame.join_game(game_id, users[1].id)
    if not success:
        print(f"Failed to join game: {message}")
        return
    print("Player B joined the game")
    print_game_status(game_id)
    
    # Player C joins the game
    success, message = RPSGame.join_game(game_id, users[2].id)
    if not success:
        print(f"Failed to join game: {message}")
        return
    print("Player C joined the game")
    print_game_status(game_id)
    
    # Players make their choices
    time.sleep(1)  # Small delay to ensure game status is updated
    
    # Player A chooses Rock
    success, message = RPSGame.make_choice(game_id, users[0].id, 'rock')
    if not success:
        print(f"Player A failed to make choice: {message}")
        return
    print("Player A chose Rock")
    print_game_status(game_id)
    
    # Player B chooses Paper
    success, message = RPSGame.make_choice(game_id, users[1].id, 'paper')
    if not success:
        print(f"Player B failed to make choice: {message}")
        return
    print("Player B chose Paper")
    print_game_status(game_id)
    
    # Player C chooses Scissors
    success, message = RPSGame.make_choice(game_id, users[2].id, 'scissors')
    if not success:
        print(f"Player C failed to make choice: {message}")
        return
    print("Player C chose Scissors")
    print_game_status(game_id)
    
    # Check if game is completed and determine winner
    game = db.session.get(Game, game_id)
    if game.status == 'playing':
        winner = RPSGame.determine_winner(game_id)
        if winner:
            winner_user = db.session.get(User, winner.user_id)
            total_pot = game.bet_amount * 3
            game.status = 'completed'
            game.winner_id = winner.user_id
            game.completed_at = datetime.utcnow()
            
            # Update winner stats
            winner_user.balance += total_pot
            winner_user.games_won += 1
            winner_user.total_winnings += total_pot
            
            # Update all players' games_played
            for p in game.participants:
                user = db.session.get(User, p.user_id)
                user.games_played += 1
            
            db.session.commit()
    
    # Check final game state
    game = db.session.get(Game, game_id)
    if game.status == 'completed':
        winner = db.session.get(User, game.winner_id)
        print(f"\nGame completed! Winner: Player {winner.username}")
        print(f"Winner's balance: {winner.balance}")
    else:
        print("\nGame did not complete as expected")
        print(f"Final game status: {game.status}")

def simulate_insufficient_balance():
    """Simulate a game where a player has insufficient balance"""
    # Clean up any existing data
    GameParticipant.query.delete()
    Game.query.delete()
    User.query.delete()
    db.session.commit()
    
    # Create test users with low balance
    users = []
    for i, username in enumerate(['A', 'B', 'C']):
        user = User(
            username=username,
            telegram_id=2000 + i,
            balance=50 if username == 'B' else 1000,  # User B has insufficient balance
            games_played=0,
            games_won=0,
            total_winnings=0
        )
        db.session.add(user)
    db.session.commit()
    users = User.query.all()
    print("\nTesting Insufficient Balance Scenario:")
    print("Created test users with User B having low balance")
    
    # Player A creates a game with bet amount 100
    game, message = RPSGame.create_game(bet_amount=100, created_by_user_id=users[0].id)
    if not game:
        print(f"Failed to create game: {message}")
        return
    game_id = game.id
    print(f"Player A created game {game_id}")
    
    # Player B tries to join with insufficient balance
    success, message = RPSGame.join_game(game_id, users[1].id)
    print(f"Player B attempt to join result: {message}")

def simulate_duplicate_choices():
    """Simulate a game where players try to make duplicate choices"""
    # Clean up any existing data
    GameParticipant.query.delete()
    Game.query.delete()
    User.query.delete()
    db.session.commit()
    
    # Create test users
    users = create_test_users()
    print("\nTesting Duplicate Choices Scenario:")
    print("Created test users:", [u.username for u in users])
    
    # Create and setup game
    game, _ = RPSGame.create_game(bet_amount=100, created_by_user_id=users[0].id)
    game_id = game.id
    RPSGame.join_game(game_id, users[1].id)
    RPSGame.join_game(game_id, users[2].id)
    
    # Players try to make duplicate choices
    success, message = RPSGame.make_choice(game_id, users[0].id, 'rock')
    print(f"Player A chooses Rock: {message}")
    
    success, message = RPSGame.make_choice(game_id, users[1].id, 'rock')
    print(f"Player B tries to choose Rock: {message}")

if __name__ == '__main__':
    with app.app_context():
        print("\n=== Basic Game Flow Test ===")
        simulate_basic_game()
        
        print("\n=== Insufficient Balance Test ===")
        simulate_insufficient_balance()
        
        print("\n=== Duplicate Choices Test ===")
        simulate_duplicate_choices() 