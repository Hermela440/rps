import time
from datetime import datetime, timedelta
from functools import wraps
import os

# Temporarily disable telegram imports for web interface
# from telegram import Update
# from telegram.ext import CallbackContext

from config import LOGGER, CREATE_ACCOUNT_COOLDOWN, DELETE_ACCOUNT_COOLDOWN, DEPOSIT_COOLDOWN, WITHDRAW_COOLDOWN, JOIN_GAME_COOLDOWN
from models import User, Cooldown
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


def get_user_by_telegram_id(telegram_id):
    return User.query.filter_by(telegram_id=telegram_id).first()


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()


def format_currency(amount):
    return f"${amount:.2f}"


def user_exists(update: Update) -> bool:
    if not update.effective_user:
        return False
    user = get_user_by_telegram_id(update.effective_user.id)
    return user is not None


def cooldown(seconds=None):
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
            try:
                user_id = update.effective_user.id
                command_name = func.__name__
                user = get_user_by_telegram_id(user_id)

                # Only apply cooldown for users who have accounts
                if not user:
                    # Don't block create_account command
                    if command_name == 'create_account':
                        return await func(update, context, *args, **kwargs)
                    
                    await update.message.reply_text("You need to create an account first. Use /create_account.")
                    return

                default_cooldown = 5  # Reduce default cooldown to 5 seconds for testing
                if command_name == 'create_account':
                    default_cooldown = 10  # Reduced from 86400 (24 hours)
                elif command_name == 'delete_account':
                    default_cooldown = 10  # Reduced from 86400 (24 hours)
                elif command_name == 'deposit':
                    default_cooldown = 5  # Reduced from 300 (5 minutes)
                elif command_name == 'withdraw':
                    default_cooldown = 5  # Reduced from 3600 (1 hour)
                elif command_name == 'join_game':
                    default_cooldown = 5  # Reduced from 60 (1 minute)

                cooldown_time = seconds if seconds is not None else default_cooldown
                
                # Skip cooldown in development mode
                if os.environ.get('DEBUG', 'true').lower() == 'true':
                    # For debugging, log but don't enforce cooldowns
                    LOGGER.debug(f"Cooldown skipped for {command_name} (development mode)")
                    return await func(update, context, *args, **kwargs)
                
                now = datetime.utcnow()

                cooldown_entry = Cooldown.query.filter_by(
                    user_id=user.id, command=command_name
                ).filter(Cooldown.expires_at > now).first()

                if cooldown_entry:
                    time_left = (cooldown_entry.expires_at - now).seconds
                    await update.message.reply_text(f"Please wait {time_left} seconds before using this command again.")
                    return

                cooldown_entry = Cooldown.query.filter_by(user_id=user.id, command=command_name).first()
                expires_at = now + timedelta(seconds=cooldown_time)

                if cooldown_entry:
                    cooldown_entry.expires_at = expires_at
                else:
                    db.session.add(Cooldown(user_id=user.id, command=command_name, expires_at=expires_at))

                db.session.commit()
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                LOGGER.error(f"Error in cooldown decorator: {e}")
                # Let the command run anyway if there's an error in the cooldown logic
                return await func(update, context, *args, **kwargs)
                
        return wrapped
    return decorator


def admin_required(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        user = get_user_by_telegram_id(user_id)

        if not user or not user.is_admin:
            await update.message.reply_text("This command is only available to administrators.")
            return

        return await func(update, context, *args, **kwargs)
    return wrapped


def update_user_activity(user_id):
    user = User.query.get(user_id)
    if user:
        user.last_active = datetime.utcnow()
        db.session.commit()


def get_leaderboard(limit=10):
    users = User.query.filter(User.games_played > 0).all()
    user_stats = []

    for user in users:
        win_rate = (user.games_won / user.games_played) * 100 if user.games_played > 0 else 0
        user_stats.append({
            'username': user.username,
            'games_played': user.games_played,
            'games_won': user.games_won,
            'win_rate': win_rate
        })

    sorted_stats = sorted(user_stats, key=lambda x: x['win_rate'], reverse=True)
    return sorted_stats[:limit]


def validate_username(username):
    """
    Validate a username.
    Username must be 3-32 characters and contain only letters, numbers, underscores, and hyphens.
    """
    import re
    
    # Basic length check
    if not username or len(username) < 3 or len(username) > 32:
        return False
    
    # Simple character validation - more permissive than regex
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return all(c in valid_chars for c in username)
