import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    CallbackContext
)
from rps_simulation import create_rps_simulation
from datetime import datetime
import os

from app import db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest
from game import RPSGame
from payments import PaymentSystem
from utils import (
    get_user_by_telegram_id,
    format_currency,
    user_exists,
    cooldown,
    admin_required,
    update_user_activity,
    get_leaderboard,
    validate_username
)
from admin import AdminService
from config import (
    BOT_TOKEN,
    ADMIN_USERS,
    LOGGER,
    BET_AMOUNT_DEFAULT,
    MIN_DEPOSIT_AMOUNT,
    MAX_DEPOSIT_AMOUNT,
    MIN_WITHDRAW_AMOUNT,
    MAX_WITHDRAW_AMOUNT
)

# Platform fee percentage for game winnings
PLATFORM_FEE_PERCENT = 5.0

@cooldown()
def create_account(update: Update, context: CallbackContext) -> None:
    """Create a new user account."""
    try:
        telegram_id = update.effective_user.id
        telegram_username = update.effective_user.username
        
        # Log the request
        LOGGER.info(f"Account creation request from Telegram ID: {telegram_id}, Username: {telegram_username}")
    
        # Check if user already exists
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            update.message.reply_text("You already have an account.")
            return
        
        # Get username from message or use Telegram username
        if context.args and len(context.args) > 0:
            username = context.args[0]
            LOGGER.info(f"Provided username: {username}")
        else:
            # Use Telegram username if available
            if telegram_username:
                username = telegram_username
                LOGGER.info(f"Using Telegram username: {username}")
            else:
                update.message.reply_text(
                    "Please provide a username: /create_account [username]"
                )
                return
        
        # Simple username validation (3-32 chars, alphanumeric, underscores, hyphens)
        if len(username) < 3 or len(username) > 32:
            update.message.reply_text(
                f"Username '{username}' must be between 3 and 32 characters."
            )
            return
            
        # Simplified validation to avoid regex issues
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not all(c in valid_chars for c in username):
            update.message.reply_text(
                f"Username '{username}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed."
            )
            return
        
        # Check if username is already taken (with error handling)
        try:
            existing_name = User.query.filter_by(username=username).first()
            if existing_name:
                update.message.reply_text(f"Username '{username}' is already taken. Please try another one.")
                return
        except Exception as e:
            LOGGER.error(f"Database error checking username: {e}")
            update.message.reply_text("Error checking username availability. Please try again later.")
            return
        
        # Create new user with error handling
        try:
            # Create user
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=100.0,  # Starting balance
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                is_admin=telegram_id in ADMIN_USERS  # Set admin status if in admin list
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Get user ID after commit
            user_id = user.id
    
            # Create initial bonus transaction
            transaction = Transaction(
                user_id=user_id,
                amount=100.0,
                transaction_type='bonus',
                status='completed',
                reference_id='welcome_bonus',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            LOGGER.info(f"Account created successfully for {username} (ID: {user_id})")
            
            # Success message - without Markdown to avoid $ parsing issues
            update.message.reply_text(
                f"Account created successfully! Welcome, {username}.\n"
                f"You've received a welcome bonus of $100.00 in your wallet.\n"
                f"Your current balance: ${user.balance:.2f}\n\n"
                f"Use /join_game to start playing!"
            )

        except Exception as e:
            LOGGER.error(f"Error creating account: {e}")
            db.session.rollback()
            update.message.reply_text("Error creating account. Please try again later.")

    except Exception as e:
        LOGGER.error(f"Unexpected error in create_account: {e}")
        update.message.reply_text("An unexpected error occurred. Please try again.")

def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    keyboard = [
        [KeyboardButton("💰 Account"), KeyboardButton("🎮 Game")],
        [KeyboardButton("📊 Stats"), KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "🎮 Welcome to Rock Paper Scissors Bot! 🎮\n\n"
        "Here you can play Rock Paper Scissors with other players and win rewards!\n\n"
        "To get started:\n"
        "1. Create an account with /create_account\n"
        "2. Join a game with /join_game\n"
        "3. Make your choice and wait for an opponent!\n\n"
        "Use /help to see all available commands."
    )
    
    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a help message when the command /help is issued."""
    help_text = "📚 *Rock Paper Scissors Commands* 📚\n\n"
    
    for category, commands in COMMANDS.items():
        help_text += f"{category}:\n"
        for cmd, desc in commands.items():
            help_text += f"{cmd} - {desc}\n"
        help_text += "\n"
    
    update.message.reply_text(help_text, parse_mode='Markdown')

def about(update: Update, context: CallbackContext) -> None:
    """Send information about the bot."""
    update.message.reply_text(
        "🎮 *Rock Paper Scissors Bot* 🎮\n\n"
        "A fun and interactive bot that lets you play Rock Paper Scissors with other players!\n\n"
        "Features:\n"
        "• Play with custom bet amounts\n"
        "• Win rewards for victories\n"
        "• Track your stats and history\n"
        "• Compete on the leaderboard\n\n"
        "Created with ❤️ by @YourUsername",
        parse_mode='Markdown'
    )

@cooldown()
def delete_account(update: Update, context: CallbackContext) -> None:
    """Delete a user account."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with confirm/cancel buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=f"delete_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"delete_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store user ID in context for callback handling
        context.user_data['pending_delete'] = user.id
        
        update.message.reply_text(
            "⚠️ *Are you sure you want to delete your account?* ⚠️\n\n"
            "This action cannot be undone. All your data, including:\n"
            "• Balance\n"
            "• Game history\n"
            "• Statistics\n\n"
            "Will be permanently deleted.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in delete_account: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def balance(update: Update, context: CallbackContext) -> None:
    """Check user balance."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with deposit/withdraw buttons
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"💰 *Your Balance*\n\n"
            f"Current balance: ${user.balance:.2f}\n\n"
            f"Use the buttons below to manage your funds:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error checking balance: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def deposit(update: Update, context: CallbackContext) -> None:
    """Handle deposit command."""
    if not user_exists(update):
        return
    
    try:
        # Create inline keyboard with preset amounts
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="deposit_10"),
                InlineKeyboardButton("$20", callback_data="deposit_20"),
                InlineKeyboardButton("$50", callback_data="deposit_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="deposit_100"),
                InlineKeyboardButton("$200", callback_data="deposit_200"),
                InlineKeyboardButton("$500", callback_data="deposit_500")
            ],
            [InlineKeyboardButton("Custom Amount", callback_data="deposit_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "💰 *Deposit Funds*\n\n"
            "Choose an amount to deposit or select custom amount:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in deposit command: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def withdraw(update: Update, context: CallbackContext) -> None:
    """Handle withdraw command."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with preset amounts
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="withdraw_10"),
                InlineKeyboardButton("$20", callback_data="withdraw_20"),
                InlineKeyboardButton("$50", callback_data="withdraw_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="withdraw_100"),
                InlineKeyboardButton("$200", callback_data="withdraw_200"),
                InlineKeyboardButton("$500", callback_data="withdraw_500")
            ],
            [InlineKeyboardButton("Custom Amount", callback_data="withdraw_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"💸 *Withdraw Funds*\n\n"
            f"Current balance: ${user.balance:.2f}\n\n"
            f"Choose an amount to withdraw or select custom amount:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in withdraw command: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def history(update: Update, context: CallbackContext) -> None:
    """Show user transaction history."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Get last 10 transactions
        transactions = get_user_transactions(user.id, limit=10)
        
        if not transactions:
            update.message.reply_text(
                "📜 *Transaction History*\n\n"
                "No transactions found.",
                parse_mode='Markdown'
            )
            return
        
        history_text = "📜 *Transaction History*\n\n"
        for tx in transactions:
            amount = f"+${tx.amount:.2f}" if tx.type == 'deposit' else f"-${tx.amount:.2f}"
            status = "✅" if tx.status == 'completed' else "⏳"
            history_text += f"{status} {amount} - {tx.type.title()} - {tx.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Create navigation buttons
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Previous", callback_data="history_prev"),
                InlineKeyboardButton("Next ➡️", callback_data="history_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error showing history: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        LOGGER.error("No BOT_TOKEN provided. Please set the BOT_TOKEN environment variable.")
        return
    
    try:
        # Initialize the updater and dispatcher
        updater = Updater(BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # Basic commands
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("about", about))
        
        # Account commands
        dispatcher.add_handler(CommandHandler("create_account", create_account))
        dispatcher.add_handler(CommandHandler("delete_account", delete_account))
        dispatcher.add_handler(CommandHandler("balance", balance))
        dispatcher.add_handler(CommandHandler("deposit", deposit))
        dispatcher.add_handler(CommandHandler("withdraw", withdraw))
        dispatcher.add_handler(CommandHandler("history", history))
        
        # Game commands
        dispatcher.add_handler(CommandHandler("join_game", join_game))
        dispatcher.add_handler(CommandHandler("game_status", game_status))
        dispatcher.add_handler(CommandHandler("simulate", simulate_rps))
        
        # Stats commands
        dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
        dispatcher.add_handler(CommandHandler("profile", profile))
        
        # Add callback query handler for buttons
        dispatcher.add_handler(CallbackQueryHandler(button_callback))
        
        # Add message handler for menu buttons
        dispatcher.add_handler(MessageHandler(
            Filters.regex("^(💰 Account|🎮 Game|📊 Stats|ℹ️ Help)$"),
            handle_menu_button
        ))
        
        # Add handler for unknown commands
        dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))
        
        LOGGER.info("All command handlers registered successfully")
        
        # Start the bot
        LOGGER.info("Starting bot...")
        updater.start_polling()
        
        # Run the bot until you press Ctrl-C
        updater.idle()
        
    except Exception as e:
        LOGGER.error(f"Error in bot startup: {e}")
        LOGGER.exception("Full traceback:")


if __name__ == "__main__":
    main() 