"""Start command handler for the bot"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models import User
from extensions import db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        # Get user info from Telegram
        user = update.effective_user
        if not user:
            await update.message.reply_text("Error: Could not get user information.")
            return

        # Check if user exists in database
        db_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not db_user:
            # Create new user
            db_user = User(
                telegram_id=user.id,
                username=user.username or f"user_{user.id}",
                full_name=user.full_name or user.username or f"User {user.id}",
                email=f"{user.username}@rpsbot.com" if user.username else f"user_{user.id}@rpsbot.com",
                balance=0.0,
                wins=0,
                losses=0,
                is_admin=False
            )
            db.session.add(db_user)
            db.session.commit()
            
            welcome_message = (
                f"👋 Welcome to Rock Paper Scissors Game, {user.first_name}!\n\n"
                "🎮 How to play:\n"
                "1. Create a game room or join an existing one\n"
                "2. Place your bet\n"
                "3. Make your move\n"
                "4. Win and collect your prize!\n\n"
                "💰 To get started, you'll need to deposit some funds.\n"
                "Use /deposit to add funds to your account.\n\n"
                "📝 Available commands:\n"
                "/help - Show all commands\n"
                "/balance - Check your balance\n"
                "/deposit - Add funds\n"
                "/withdraw - Withdraw funds\n"
                "/create - Create a game room\n"
                "/join - Join a game room"
            )
        else:
            welcome_message = (
                f"👋 Welcome back, {user.first_name}!\n\n"
                f"💰 Your current balance: {db_user.balance} ETB\n\n"
                "📝 Available commands:\n"
                "/help - Show all commands\n"
                "/balance - Check your balance\n"
                "/deposit - Add funds\n"
                "/withdraw - Withdraw funds\n"
                "/create - Create a game room\n"
                "/join - Join a game room"
            )

        # Create keyboard with main actions
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton("🎮 Create Game", callback_data="create_game"),
                InlineKeyboardButton("🎲 Join Game", callback_data="join_game")
            ],
            [
                InlineKeyboardButton("📊 Balance", callback_data="balance"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send welcome message with keyboard
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in start handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred while starting the bot. Please try again later."
        )

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = (
        "🎮 Rock Paper Scissors Game - Help\n\n"
        "💰 Financial Commands:\n"
        "/deposit <amount> - Add funds to your account\n"
        "/withdraw <amount> <wallet> - Withdraw funds\n"
        "/balance - Check your balance\n\n"
        "🎲 Game Commands:\n"
        "/create <bet> - Create a new game room\n"
        "/join <room_code> - Join an existing game\n"
        "/leave - Leave current game\n"
        "/move <rock/paper/scissors> - Make your move\n\n"
        "📊 Other Commands:\n"
        "/stats - View your game statistics\n"
        "/leaderboard - View top players\n"
        "/help - Show this help message\n\n"
        "❓ Need more help? Contact support."
    )
    
    await update.message.reply_text(help_message) 