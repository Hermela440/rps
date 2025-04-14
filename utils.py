import time
from datetime import datetime, timedelta
from functools import wraps
# Temporarily disable telegram imports for web interface
# from telegram import Update
# from telegram.ext import CallbackContext
from config import COOLDOWN_SECONDS, LOGGER
from models import User, Cooldown
from app import db

# Create dummy classes for web interface compatibility
class Update:
    """Dummy Update class for web interface compatibility"""
    class User:
        def __init__(self, id=None):
            self.id = id
    
    class Message:
        async def reply_text(self, text):
            """Dummy reply_text method"""
            pass
    
    def __init__(self):
        self.effective_user = self.User()
        self.message = self.Message()

class CallbackContext:
    """Dummy CallbackContext class for web interface compatibility"""
    pass


def get_user_by_telegram_id(telegram_id):
    """Get a user by their Telegram ID"""
    return User.query.filter_by(telegram_id=telegram_id).first()


def get_user_by_username(username):
    """Get a user by their username"""
    return User.query.filter_by(username=username).first()


def format_currency(amount):
    """Format currency to two decimal places"""
    return f"${amount:.2f}"


def user_exists(update: Update) -> bool:
    """Check if a user exists in the database"""
    if not update.effective_user:
        return False
    
    user = get_user_by_telegram_id(update.effective_user.id)
    return user is not None


def cooldown(seconds=None):
    """
    Decorator to implement a cooldown on commands
    """
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
            user_id = update.effective_user.id
            command_name = func.__name__
            
            # Check if user exists
            user = get_user_by_telegram_id(user_id)
            if not user:
                await update.message.reply_text("You need to create an account first. Use /create_account.")
                return
                
            # Check for cooldown
            cooldown_time = seconds if seconds is not None else COOLDOWN_SECONDS
            now = datetime.utcnow()
            
            # Check if user is on cooldown for this command
            cooldown_entry = Cooldown.query.filter_by(
                user_id=user.id, 
                command=command_name
            ).filter(Cooldown.expires_at > now).first()
            
            if cooldown_entry:
                # User is on cooldown
                time_left = (cooldown_entry.expires_at - now).seconds
                await update.message.reply_text(
                    f"Please wait {time_left} seconds before using this command again."
                )
                return
            
            # Create or update cooldown
            cooldown_entry = Cooldown.query.filter_by(
                user_id=user.id, 
                command=command_name
            ).first()
            
            if cooldown_entry:
                cooldown_entry.expires_at = now + timedelta(seconds=cooldown_time)
            else:
                cooldown_entry = Cooldown(
                    user_id=user.id,
                    command=command_name,
                    expires_at=now + timedelta(seconds=cooldown_time)
                )
                db.session.add(cooldown_entry)
            
            db.session.commit()
            
            # Call the original function
            return await func(update, context, *args, **kwargs)
        
        return wrapped
    
    return decorator


def admin_required(func):
    """
    Decorator to check if a user is an admin
    """
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
    """
    Update the last_active field for a user
    """
    user = User.query.get(user_id)
    if user:
        user.last_active = datetime.utcnow()
        db.session.commit()


def get_leaderboard(limit=10):
    """
    Get the top users by win rate
    """
    users = User.query.filter(User.games_played > 0).all()
    
    # Calculate win rate for each user
    user_stats = []
    for user in users:
        win_rate = (user.games_won / user.games_played) * 100 if user.games_played > 0 else 0
        user_stats.append({
            'username': user.username,
            'games_played': user.games_played,
            'games_won': user.games_won,
            'win_rate': win_rate
        })
    
    # Sort by win rate (descending)
    sorted_stats = sorted(user_stats, key=lambda x: x['win_rate'], reverse=True)
    
    return sorted_stats[:limit]


def validate_username(username):
    """
    Validate a username
    - Must be 3-32 characters
    - Alphanumeric characters, underscores, and hyphens only
    """
    import re
    if not re.match(r"^[a-zA-Z0-9_-]{3,32}$", username):
        return False
    return True
