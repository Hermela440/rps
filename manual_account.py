#!/usr/bin/env python3
"""
Manually create an account for a specific user
"""

from app import app, db
from models import User, Transaction
from datetime import datetime
import sys

def create_account_for_user(telegram_id, username):
    """Manually create an account for a specific user"""
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(telegram_id=telegram_id).first()
        if existing_user:
            print(f"User already exists: {existing_user.username} (ID: {existing_user.id})")
            return
        
        # Check if username is taken
        if User.query.filter_by(username=username).first():
            print(f"Username '{username}' is already taken. Please choose another.")
            return
        
        # Create the user
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=100.0,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create initial bonus transaction
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
        
        print(f"✅ Account created successfully!")
        print(f"Username: {username}")
        print(f"Telegram ID: {telegram_id}")
        print(f"Initial balance: $100.00")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python manual_account.py <telegram_id> <username>")
        print("Example: python manual_account.py 1234567890 Hermi_73")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
        
        if len(username) < 3 or len(username) > 32:
            print("Error: Username must be 3-32 characters long")
            sys.exit(1)
        
        create_account_for_user(telegram_id, username)
    except ValueError:
        print("Error: Telegram ID must be a number")
        sys.exit(1)
