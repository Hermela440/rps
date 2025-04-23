import time
from datetime import datetime, timedelta
from functools import wraps
import os
import requests
from typing import Optional, List, Dict, Any
from decimal import Decimal

# Temporarily disable telegram imports for web interface
# from telegram import Update
# from telegram.ext import CallbackContext

from config import LOGGER, CREATE_ACCOUNT_COOLDOWN, DELETE_ACCOUNT_COOLDOWN, DEPOSIT_COOLDOWN, WITHDRAW_COOLDOWN, JOIN_GAME_COOLDOWN
from models import User, Cooldown, Game, GameParticipant, Transaction
from extensions import db  # ✅ Fixed circular import

# Dummy classes for compatibility
class Update:
    class User:
        def __init__(self, id=None):
            self.id = id
    
    class Message:
        async def reply_text(self, text):
            pass
    
    def __init__(self):
        self.effective_user = self.User()
        self.message = self.Message()

class CallbackContext:
    pass


def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Get a user by their Telegram ID."""
    return User.query.filter_by(telegram_id=telegram_id).first()


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()


def format_currency(amount: float) -> str:
    """Format currency amount with commas and 2 decimal places."""
    return "{:,.2f}".format(amount)


def user_exists(update) -> bool:
    """Check if user exists and send message if not."""
    telegram_id = update.effective_user.id
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        update.message.reply_text(
            "❌ You don't have an account yet!\n"
            "Use /create_account to create one."
        )
        return False
    return True


def cooldown():
    """Decorator to add cooldown to commands."""
    def decorator(func):
        @wraps(func)
        def wrapper(update, context, *args, **kwargs):
            try:
                command_name = func.__name__
                telegram_id = update.effective_user.id
                user = get_user_by_telegram_id(telegram_id)
                
                if not user:
                    return func(update, context, *args, **kwargs)
                
                # Get cooldown duration based on command
                duration = {
                    'create_account': CREATE_ACCOUNT_COOLDOWN,
                    'delete_account': DELETE_ACCOUNT_COOLDOWN,
                    'deposit': DEPOSIT_COOLDOWN,
                    'withdraw': WITHDRAW_COOLDOWN
                }.get(command_name, 60)  # Default 60 seconds
                
                # Check for active cooldown
                active_cooldown = Cooldown.get_active_cooldown(user.id, command_name)
                if active_cooldown:
                    remaining = (active_cooldown.expires_at - datetime.utcnow()).seconds
                    update.message.reply_text(
                        f"⏳ Please wait {remaining} seconds before using this command again."
                    )
                    return
                
                # Create new cooldown
                Cooldown.create_cooldown(user.id, command_name, duration)
                
                return func(update, context, *args, **kwargs)
                
            except Exception as e:
                LOGGER.error(f"Error in cooldown decorator: {e}")
                return func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def admin_required(func):
    """Decorator to restrict commands to admin users only."""
    @wraps(func)
    def wrapper(update, context, *args, **kwargs):
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        if not user or not user.is_admin:
            update.message.reply_text("❌ This command is for admins only.")
            return
        
        return func(update, context, *args, **kwargs)
    
    return wrapper


def update_user_activity(user_id: int):
    """Update user's last active timestamp."""
    try:
        user = User.query.get(user_id)
        if user:
            user.last_active = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        LOGGER.error(f"Error updating user activity: {e}")


def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get global leaderboard data."""
    try:
        top_players = User.query.filter(
            User.games_played > 0
        ).order_by(
            User.total_winnings.desc()
        ).limit(limit).all()
        
        return [
            {
                'username': player.username,
                'games_played': player.games_played,
                'games_won': player.games_won,
                'total_winnings': float(player.total_winnings),
                'win_rate': (player.games_won / player.games_played * 100) if player.games_played > 0 else 0
            }
            for player in top_players
        ]
    except Exception as e:
        LOGGER.error(f"Error getting leaderboard: {e}")
        return []


def validate_username(username: str) -> bool:
    """Validate username format."""
    if len(username) < 3 or len(username) > 32:
        return False
    
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return all(c in valid_chars for c in username)


def process_chapa_payment(amount, email, first_name, last_name, tx_ref):
    """Process a payment using Chapa Wallet."""
    url = f"{CHAPA_API_URL}/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {CHAPA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "amount": amount,
        "currency": "ETB",  # Ethiopian Birr
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "tx_ref": tx_ref,  # Unique transaction reference
        "callback_url": "http://localhost:5000/payment_status",  # Update with your callback URL
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()  # Return the payment response
    else:
        return {"error": response.json()}
