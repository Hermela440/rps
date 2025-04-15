#!/usr/bin/env python3
"""
Admin tool for managing the RPS Arena database
"""

import sys
import os
from datetime import datetime

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Import app and models
from app import app, db
from models import User, Game, GameParticipant, Transaction, Cooldown
from config import ADMIN_USERS

def help_message():
    """Print help message"""
    print("RPS Arena Admin Tool")
    print("===================")
    print()
    print("Usage: python admin_tool.py <command> [arguments]")
    print()
    print("Commands:")
    print("  help                 - Show this help message")
    print("  list_users           - List all users")
    print("  add_admin <telegram_id> - Add user to admin list")
    print("  remove_admin <telegram_id> - Remove user from admin list")
    print("  reset_cooldowns <telegram_id> - Reset cooldowns for a user")
    print("  clear_games          - Clear all waiting/active games")
    print("  give_balance <telegram_id> <amount> - Add balance to a user")
    print("  set_debug <true/false> - Enable/disable debug mode")
    print("  create_user <telegram_id> <username> - Manually create a user")
    print()

def list_users():
    """List all users in the database"""
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("No users found.")
            return
        
        print(f"Found {len(users)} users:")
        print()
        print(f"{'ID':<5} {'Telegram ID':<15} {'Username':<20} {'Balance':<10} {'Admin':<6} {'Games':<6}")
        print("-" * 70)
        
        for user in users:
            print(f"{user.id:<5} {user.telegram_id:<15} {user.username:<20} ${user.balance:<8.2f} "
                  f"{'Yes' if user.is_admin else 'No':<6} {user.games_played:<6}")

def add_admin(telegram_id):
    """Add a user to the admin list in config.py"""
    try:
        telegram_id = int(telegram_id)
        
        # Check if user exists
        with app.app_context():
            user = User.query.filter_by(telegram_id=telegram_id).first()
            if not user:
                print(f"Error: No user found with Telegram ID {telegram_id}")
                return
            
            # Update user in database
            user.is_admin = True
            db.session.commit()
            
            print(f"User {user.username} (Telegram ID: {telegram_id}) is now an admin.")
            print("Note: This change is only in the database. To make it permanent, add the ID to ADMIN_USERS in config.py")
        
    except ValueError:
        print(f"Error: Invalid Telegram ID: {telegram_id}")

def remove_admin(telegram_id):
    """Remove a user from the admin list"""
    try:
        telegram_id = int(telegram_id)
        
        with app.app_context():
            user = User.query.filter_by(telegram_id=telegram_id).first()
            if not user:
                print(f"Error: No user found with Telegram ID {telegram_id}")
                return
            
            # Update user in database
            user.is_admin = False
            db.session.commit()
            
            print(f"User {user.username} (Telegram ID: {telegram_id}) is no longer an admin.")
            print("Note: This change is only in the database. To make it permanent, remove the ID from ADMIN_USERS in config.py")
        
    except ValueError:
        print(f"Error: Invalid Telegram ID: {telegram_id}")

def reset_cooldowns(telegram_id):
    """Reset all cooldowns for a user"""
    try:
        telegram_id = int(telegram_id)
        
        with app.app_context():
            user = User.query.filter_by(telegram_id=telegram_id).first()
            if not user:
                print(f"Error: No user found with Telegram ID {telegram_id}")
                return
            
            # Delete cooldowns
            count = Cooldown.query.filter_by(user_id=user.id).delete()
            db.session.commit()
            
            print(f"Reset {count} cooldowns for user {user.username}")
        
    except ValueError:
        print(f"Error: Invalid Telegram ID: {telegram_id}")

def clear_games():
    """Clear all waiting or active games"""
    with app.app_context():
        games = Game.query.filter(Game.status.in_(['waiting', 'active'])).all()
        
        if not games:
            print("No waiting or active games found.")
            return
        
        for game in games:
            # Refund participants
            for participant in GameParticipant.query.filter_by(game_id=game.id).all():
                user = User.query.get(participant.user_id)
                if user:
                    user.balance += game.bet_amount
                    
                    # Create refund transaction
                    transaction = Transaction(
                        user_id=user.id,
                        amount=game.bet_amount,
                        transaction_type='refund',
                        status='completed',
                        reference_id=f"admin_cancel_{game.id}",
                        created_at=datetime.utcnow(),
                        completed_at=datetime.utcnow()
                    )
                    db.session.add(transaction)
            
            # Mark game as cancelled
            game.status = 'cancelled'
            game.completed_at = datetime.utcnow()
        
        db.session.commit()
        print(f"Cleared {len(games)} games and refunded all bets.")

def give_balance(telegram_id, amount):
    """Add balance to a user's account"""
    try:
        telegram_id = int(telegram_id)
        amount = float(amount)
        
        if amount <= 0:
            print("Error: Amount must be positive")
            return
        
        with app.app_context():
            user = User.query.filter_by(telegram_id=telegram_id).first()
            if not user:
                print(f"Error: No user found with Telegram ID {telegram_id}")
                return
            
            # Add balance
            old_balance = user.balance
            user.balance += amount
            
            # Create transaction
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                transaction_type='admin_credit',
                status='completed',
                reference_id=f"admin_credit_{int(datetime.utcnow().timestamp())}",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            print(f"Added ${amount:.2f} to {user.username}'s balance")
            print(f"Old balance: ${old_balance:.2f}")
            print(f"New balance: ${user.balance:.2f}")
        
    except ValueError:
        print(f"Error: Invalid arguments. Telegram ID must be an integer and amount must be a number.")

def set_debug(value):
    """Enable/disable debug mode by setting environment variable"""
    if value.lower() in ('true', 'yes', '1', 'on'):
        os.environ['DEBUG'] = 'True'
        print("Debug mode enabled")
    elif value.lower() in ('false', 'no', '0', 'off'):
        os.environ['DEBUG'] = 'False'
        print("Debug mode disabled")
    else:
        print(f"Error: Invalid value: {value}. Use 'true' or 'false'")

def create_user(telegram_id, username):
    """Manually create a user"""
    try:
        telegram_id = int(telegram_id)
        
        with app.app_context():
            # Check if user already exists
            existing = User.query.filter_by(telegram_id=telegram_id).first()
            if existing:
                print(f"Error: User with Telegram ID {telegram_id} already exists: {existing.username}")
                return
            
            # Check if username is taken
            if User.query.filter_by(username=username).first():
                print(f"Error: Username '{username}' is already taken")
                return
            
            # Create user
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=100.0,
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                is_admin=(telegram_id in ADMIN_USERS)
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Create welcome bonus transaction
            transaction = Transaction(
                user_id=user.id,
                amount=100.0,
                transaction_type='bonus',
                status='completed',
                reference_id='welcome_bonus',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            print(f"Created user {username} with Telegram ID {telegram_id}")
            print(f"Initial balance: $100.00")
            print(f"Admin: {'Yes' if user.is_admin else 'No'}")
        
    except ValueError:
        print(f"Error: Invalid Telegram ID: {telegram_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        help_message()
        sys.exit(0)
        
    command = sys.argv[1].lower()
    
    if command == 'list_users':
        list_users()
    
    elif command == 'add_admin' and len(sys.argv) >= 3:
        add_admin(sys.argv[2])
    
    elif command == 'remove_admin' and len(sys.argv) >= 3:
        remove_admin(sys.argv[2])
    
    elif command == 'reset_cooldowns' and len(sys.argv) >= 3:
        reset_cooldowns(sys.argv[2])
    
    elif command == 'clear_games':
        clear_games()
    
    elif command == 'give_balance' and len(sys.argv) >= 4:
        give_balance(sys.argv[2], sys.argv[3])
    
    elif command == 'set_debug' and len(sys.argv) >= 3:
        set_debug(sys.argv[2])
    
    elif command == 'create_user' and len(sys.argv) >= 4:
        create_user(sys.argv[2], sys.argv[3])
    
    else:
        print(f"Error: Unknown command or missing arguments: {command}")
        print()
        help_message()
        sys.exit(1) 