#!/usr/bin/env python3
"""
Create an account directly in the database
"""

from app import app, db
from models import User, Transaction
from datetime import datetime
import sys

def create_account(telegram_id, username):
    """Create an account directly in the database"""
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(telegram_id=telegram_id).first()
        if existing_user:
            print(f"User already exists: {existing_user.username} (ID: {existing_user.id})")
            return
        
        # Check if username is taken
        existing_name = User.query.filter_by(username=username).first()
        if existing_name:
            print(f"Username '{username}' is already taken by user ID: {existing_name.id}")
            return
        
        # Create user
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=100.0,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow()
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
        
        print(f"✅ Account created successfully for {username}")
        print(f"Telegram ID: {telegram_id}")
        print(f"Username: {username}")
        print(f"Initial balance: $100.00")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_direct_account.py <telegram_id> <username>")
        print("Example: python create_direct_account.py 1234567890 test_user")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
        
        create_account(telegram_id, username)
    except ValueError:
        print(f"Error: Invalid Telegram ID '{sys.argv[1]}'. Must be a number.")
        sys.exit(1)
