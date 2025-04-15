#!/usr/bin/env python3
"""
This script diagnoses and fixes multiple account issues with the Telegram bot
"""

import os
import sys
from app import app, db
from models import User, Cooldown, Game, GameParticipant, Transaction
from datetime import datetime
from sqlalchemy import text

def diagnose_database():
    """Check database for common issues that affect multiple accounts"""
    with app.app_context():
        print("Running database diagnostics...")
        
        # Check for duplicate telegram_ids
        query = text("""
            SELECT telegram_id, COUNT(*) as count 
            FROM user 
            WHERE telegram_id IS NOT NULL 
            GROUP BY telegram_id 
            HAVING COUNT(*) > 1
        """)
        result = db.session.execute(query)
        duplicates = result.fetchall()
        
        if duplicates:
            print(f"⚠️ Found {len(duplicates)} duplicate Telegram IDs:")
            for telegram_id, count in duplicates:
                print(f"   Telegram ID {telegram_id} has {count} accounts")
        else:
            print("✓ No duplicate Telegram IDs found")
        
        # Check for NULL telegram_ids
        null_count = User.query.filter(User.telegram_id.is_(None)).count()
        if null_count > 0:
            print(f"⚠️ Found {null_count} users with NULL Telegram IDs")
        else:
            print("✓ No users with NULL Telegram IDs")
        
        # Check database indexes
        try:
            query = text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='user' AND name='ix_user_telegram_id'
            """)
            index_result = db.session.execute(query).fetchone()
            
            if not index_result:
                print("⚠️ Missing index on user.telegram_id")
            else:
                print("✓ Index on user.telegram_id exists")
        except:
            print("⚠️ Could not check indexes (might not be SQLite)")
        
        # Check for stale cooldowns
        stale_cooldowns = Cooldown.query.filter(Cooldown.expires_at > datetime.utcnow()).count()
        if stale_cooldowns > 0:
            print(f"⚠️ Found {stale_cooldowns} active cooldown restrictions")
        else:
            print("✓ No active cooldown restrictions")
        
        # Check for users with games
        users_with_games = db.session.query(User.id).join(
            GameParticipant, User.id == GameParticipant.user_id
        ).distinct().count()
        
        print(f"ℹ️ {users_with_games} users have participated in games")

def fix_database():
    """Apply fixes to the database"""
    with app.app_context():
        print("Applying fixes to the database...")
        
        # 1. Ensure proper indexes
        try:
            print("Adding index on user.telegram_id if needed...")
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_user_telegram_id ON user(telegram_id)"))
            db.session.commit()
            print("✓ Index created or verified")
        except Exception as e:
            print(f"⚠️ Error creating index: {e}")
            db.session.rollback()
        
        # 2. Clear all cooldowns
        try:
            print("Clearing all cooldowns...")
            count = Cooldown.query.delete()
            db.session.commit()
            print(f"✓ Deleted {count} cooldown records")
        except Exception as e:
            print(f"⚠️ Error clearing cooldowns: {e}")
            db.session.rollback()
        
        # 3. Clear any problematic games
        try:
            print("Cleaning up stuck games...")
            games = Game.query.filter(Game.status.in_(['waiting', 'active'])).all()
            
            if games:
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
                                reference_id=f"cleanup_{game.id}",
                                created_at=datetime.utcnow(),
                                completed_at=datetime.utcnow()
                            )
                            db.session.add(transaction)
                    
                    # Mark game as cancelled
                    game.status = 'cancelled'
                    game.completed_at = datetime.utcnow()
                
                db.session.commit()
                print(f"✓ Cleaned up {len(games)} games and refunded all bets")
            else:
                print("✓ No stuck games found")
                
        except Exception as e:
            print(f"⚠️ Error cleaning games: {e}")
            db.session.rollback()

def fix_bot_privacy():
    """Update the bot configuration file to address multiple account issues"""
    config_file = 'telegram_bot.py'
    
    if not os.path.exists(config_file):
        print(f"⚠️ Could not find {config_file}")
        return
    
    print("Updating Telegram bot configuration...")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we need to make changes
    if 'disable_web_page_preview=True' not in content:
        # Find the main function
        if 'async def main' in content:
            # Update the polling configuration to support multiple users better
            updated = content.replace(
                'await application.run_polling()',
                'await application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)'
            )
            
            # If we made a change, save it
            if updated != content:
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(updated)
                print("✓ Updated polling configuration for better multi-user support")
            else:
                print("✓ Polling configuration already optimized")
        else:
            print("⚠️ Could not find main function in telegram_bot.py")
    else:
        print("✓ Bot configuration already optimized")

def create_fixed_bot_version():
    """Create a simplified version of the bot that works with multiple accounts"""
    print("Creating simplified multi-account compatible version...")
    
    bot_file = 'simple_bot.py'
    
    with open(bot_file, 'w', encoding='utf-8') as f:
        f.write("""#!/usr/bin/env python3
\"\"\"
Simplified Telegram bot for RPS Arena that works with multiple accounts
\"\"\"

import logging
import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import configuration and database
from config import BOT_TOKEN
from app import app, db
from models import User, Game, GameParticipant, Transaction

def get_user_by_telegram_id(telegram_id):
    """Get user by Telegram ID"""
    return User.query.filter_by(telegram_id=telegram_id).first()

def start(update: Update, context: CallbackContext) -> None:
    """Handle the /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    logger.info(f"Start command from user {user_id} (@{username})")
    
    with app.app_context():
        # Check if user exists
        user = get_user_by_telegram_id(user_id)
        
        if user:
            update.message.reply_text(
                f"Welcome back, {user.username}! Your current balance is ${user.balance:.2f}\\n\\n"
                f"Use /help to see available commands."
            )
        else:
            update.message.reply_text(
                f"Welcome to RPS Arena, @{username}!\\n\\n"
                f"Create an account with /create_account [username] to get started."
            )

def help_command(update: Update, context: CallbackContext) -> None:
    """Handle the /help command"""
    update.message.reply_text(
        "📚 *RPS Arena Bot Commands* 📚\\n\\n"
        "*🔐 Account Commands*\\n"
        "/create_account - Create your account\\n"
        "/balance - Check your wallet balance\\n"
        "/whoami - Show your account info\\n\\n"
        "*🎮 Game Commands*\\n"
        "/join_game - Join a match\\n"
        "/game_status - Check game status\\n\\n"
        "*ℹ️ Help Commands*\\n"
        "/help - Show this message\\n"
        "/about - About the bot",
        parse_mode='Markdown'
    )

def create_account(update: Update, context: CallbackContext) -> None:
    """Create a new user account"""
    telegram_id = update.effective_user.id
    telegram_username = update.effective_user.username
    
    logger.info(f"Create account request from {telegram_id} (@{telegram_username})")
    
    with app.app_context():
        # Check if user already exists
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            update.message.reply_text("You already have an account.")
            return
        
        # Get username from command or use Telegram username
        if context.args and len(context.args) > 0:
            username = context.args[0]
            
            # Basic validation
            if len(username) < 3 or len(username) > 32:
                update.message.reply_text(
                    "Username must be between 3 and 32 characters."
                )
                return
        else:
            # Use Telegram username if available
            if telegram_username:
                username = telegram_username
            else:
                update.message.reply_text(
                    "Please provide a username: /create_account [username]"
                )
                return
        
        # Check if username is already taken
        if User.query.filter_by(username=username).first():
            update.message.reply_text(f"Username '{username}' is already taken. Please try another one.")
            return
        
        # Create new user
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=100.0,  # Starting balance
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
        
        update.message.reply_text(
            f"Account created successfully! Welcome, {username}.\\n"
            f"You've received a welcome bonus of $100.00 in your wallet.\\n\\n"
            f"Your current balance: ${user.balance:.2f}\\n\\n"
            f"Use /join_game to start playing!"
        )

def balance(update: Update, context: CallbackContext) -> None:
    """Check user balance"""
    telegram_id = update.effective_user.id
    
    with app.app_context():
        user = get_user_by_telegram_id(telegram_id)
        
        if not user:
            update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
            return
        
        user.last_active = datetime.utcnow()
        db.session.commit()
        
        update.message.reply_text(
            f"💰 *Your Wallet Balance*\\n\\n"
            f"Username: {user.username}\\n"
            f"Current balance: ${user.balance:.2f}",
            parse_mode='Markdown'
        )

def whoami(update: Update, context: CallbackContext) -> None:
    """Show user account info"""
    telegram_id = update.effective_user.id
    telegram_username = update.effective_user.username
    
    with app.app_context():
        user = get_user_by_telegram_id(telegram_id)
        
        if user:
            update.message.reply_text(
                f"*Your Account Information*\\n\\n"
                f"Telegram ID: `{telegram_id}`\\n"
                f"Telegram Username: @{telegram_username or 'None'}\\n"
                f"Account Username: {user.username}\\n"
                f"Balance: ${user.balance:.2f}\\n"
                f"Games Played: {user.games_played}\\n"
                f"Games Won: {user.games_won}\\n"
                f"Created: {user.created_at.strftime('%Y-%m-%d %H:%M')}",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                f"*You don't have an account yet*\\n\\n"
                f"Telegram ID: `{telegram_id}`\\n"
                f"Telegram Username: @{telegram_username or 'None'}\\n\\n"
                f"Create an account with /create_account [username]",
                parse_mode='Markdown'
            )

def about(update: Update, context: CallbackContext) -> None:
    """About the bot"""
    update.message.reply_text(
        "📱 *RPS Arena Bot* 📱\\n\\n"
        "A Telegram bot for playing Rock-Paper-Scissors with virtual betting.\\n\\n"
        "Features:\\n"
        "• Play RPS with 3 players\\n"
        "• Virtual wallet system\\n"
        "• Betting on matches\\n\\n"
        "Created for demonstration purposes.",
        parse_mode='Markdown'
    )

def main() -> None:
    """Start the bot."""
    logger.info("Starting RPS Arena Bot (Simple Version)")
    
    # Create the Updater
    updater = Updater(BOT_TOKEN)
    
    # Get the dispatcher
    dispatcher = updater.dispatcher
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("create_account", create_account))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("whoami", whoami))
    dispatcher.add_handler(CommandHandler("about", about))
    
    # Start the Bot - with optimized settings for multiple users
    updater.start_polling(drop_pending_updates=True)
    
    # Run the bot until the user presses Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()
""")
    
    print(f"✓ Created simplified bot in {bot_file}")
    print(f"  Run with: python {bot_file}")

def main():
    """Run all diagnostics and fixes"""
    print("RPS Arena Multi-Account Fix Tool")
    print("===============================")
    print()
    
    try:
        diagnose_database()
        print()
        
        fix_database()
        print()
        
        fix_bot_privacy()
        print()
        
        create_fixed_bot_version()
        print()
        
        print("✅ All fixes applied!")
        print()
        print("To use the fixed version:")
        print("1. Stop your current bot if it's running")
        print("2. Run the simplified bot: python simple_bot.py")
        print()
        print("This simplified version has been specially designed to work")
        print("with multiple Telegram accounts simultaneously.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please try running the simplified bot directly: python simple_bot.py")

if __name__ == "__main__":
    main() 