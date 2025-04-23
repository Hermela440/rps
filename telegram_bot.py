import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Update, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters
)
from rps_simulation import simulate_game, process_simulation_result
from datetime import datetime
import os
import random
from decimal import Decimal

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
from rps_game_animation import RPSGameAnimator

# Platform fee percentage for game winnings
PLATFORM_FEE_PERCENT = 5.0

@cooldown()
async def create_account(update: Update, context: CallbackContext) -> None:
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

def escape_markdown(text):
    """
    Helper function to escape Markdown special characters in text.
    This allows using dollar signs and other special characters in messages.
    """
    if not text:
        return ""
    
    # Characters that need escaping in Markdown V2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escape backslash first to avoid double-escaping
    text = text.replace('\\', '\\\\')
    
    # Escape all other special characters
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    # Special handling for $ which is problematic in Telegram Markdown
    text = text.replace('$', '\\$')
    
    return text



# GIF URLs for game animations
ROCK_GIF = "https://media.giphy.com/media/3o7TKNjg8dxB5ysRnW/giphy.gif"
PAPER_GIF = "https://media.giphy.com/media/3o7527Rn1HxXWqgxuo/giphy.gif"
SCISSORS_GIF = "https://media.giphy.com/media/3o7TKRXwArnzrW52MM/giphy.gif"
ROCK_WINS_GIF = "https://media.giphy.com/media/3oxHQfvDdo6OrXwOPK/giphy.gif"
PAPER_WINS_GIF = "https://media.giphy.com/media/3o7TKH6gFrV1TCxfgs/giphy.gif"
SCISSORS_WINS_GIF = "https://media.giphy.com/media/3o7TKB3yoARvULNBmM/giphy.gif"
DRAW_GIF = "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif"

# Commands dictionary for help message
COMMANDS = {
    "🔐 Account Commands": {
        "/create_account": "Create a new account",
        "/delete_account": "Delete your account",
        "/balance": "Check your balance",
        "/deposit": "Add funds to your wallet",
        "/withdraw": "Withdraw funds from your wallet",
        "/history": "View your game and transaction history"
    },
    "🎮 Game Commands": {
        "/join_game": "Join a match with default bet",
        "/join_game [amount]": "Join a match with custom bet",
        "/game_status": "Check status of current game",
        "/simulate": "Watch RPS battle simulation",
        "/simulate [rock] [paper] [scissors]": "Custom simulation with specific counts"
    },
    "📊 Stats Commands": {
        "/leaderboard": "View top players",
        "/profile": "View your profile stats"
    },
    "ℹ️ Help Commands": {
        "/help": "Show this help message",
        "/about": "About the Rock Paper Scissors bot"
    }
}

# Admin commands
ADMIN_COMMANDS = {
    "/admin_stats": "View system statistics",
    "/admin_users": "View and manage users",
    "/admin_games": "View recent games",
    "/admin_withdrawals": "Manage withdrawal requests"
}

# Initialize game choices keyboard
GAME_CHOICES = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🗿 Rock", callback_data="choice_rock"),
        InlineKeyboardButton("📄 Paper", callback_data="choice_paper"),
        InlineKeyboardButton("✂️ Scissors", callback_data="choice_scissors")
    ]
])


# Command handlers
async def start(update: Update, context: CallbackContext) -> None:
    """Start the bot and show welcome message."""
    try:
        # Create keyboard layout
        keyboard = [
            [KeyboardButton("🎮 Join Game"), KeyboardButton("💰 Balance")],
            [KeyboardButton("📊 Leaderboard"), KeyboardButton("👤 Profile")],
            [KeyboardButton("❓ Help"), KeyboardButton("ℹ️ About")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Send welcome message
        update.message.reply_text(
            "Welcome to Rock Paper Scissors Bot! 🎮\n\n"
            "Here you can play Rock Paper Scissors with other players "
            "and win real money! 💰\n\n"
            "To get started:\n"
            "1. Create an account with /create_account\n"
            "2. Join a game with /join_game\n"
            "3. Make your choice when the game starts!\n\n"
            "Use /help to see all available commands.",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        LOGGER.error(f"Error in start command: {e}")
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    try:
        commands = [
            "🎮 Game Commands:",
            "/join_game - Join or create a game",
            "/simulate - Play against AI players",
            "/cancel_game - Cancel your current game",
            "",
            "💰 Account Commands:",
            "/create_account - Create a new account",
            "/delete_account - Delete your account",
            "/balance - Check your balance",
            "/deposit - Add funds to your account",
            "/withdraw - Withdraw your funds",
            "",
            "📊 Stats Commands:",
            "/profile - View your profile",
            "/leaderboard - View top players",
            "/history - View your game history",
            "",
            "ℹ️ Other Commands:",
            "/start - Start the bot",
            "/help - Show this help message",
            "/about - About this bot"
        ]
        update.message.reply_text("\n".join(commands))
    except Exception as e:
        LOGGER.error(f"Error in help command: {e}")
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

def about(update: Update, context: CallbackContext) -> None:
    """Send information about the bot."""
    try:
        about_text = (
            "🎮 *Rock Paper Scissors Bot*\n\n"
            "Play Rock Paper Scissors with other players and win real money! "
            "Create an account, join games, and compete in the leaderboard.\n\n"
            "Features:\n"
            "• Play with real players or AI\n"
            "• Deposit and withdraw real money\n"
            "• Track your stats and history\n"
            "• Compete on the leaderboard\n\n"
            "Made with ❤️ by @YourUsername"
        )
        update.message.reply_text(about_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.error(f"Error in about command: {e}")
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

def delete_account(update: Update, context: CallbackContext) -> None:
    """Handle account deletion request."""
    try:
        user_id = update.effective_user.id
        user = get_user_by_telegram_id(user_id)
        
        if not user:
            update.message.reply_text(
                "You don't have an account to delete! Use /create_account to create one."
            )
            return
    
    # Create confirmation keyboard
    keyboard = [
        [
                InlineKeyboardButton("Yes, delete my account", callback_data="delete_confirm"),
                InlineKeyboardButton("No, keep my account", callback_data="delete_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
        update.message.reply_text(
            "⚠️ *WARNING: Account Deletion*\n\n"
            "Are you sure you want to delete your account?\n"
            "This will:\n"
            "• Delete all your account data\n"
            "• Remove you from any active games\n"
            "• Forfeit any remaining balance\n\n"
            "This action cannot be undone!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Error in delete_account command: {e}")
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

def balance(update: Update, context: CallbackContext) -> None:
    """Show user balance and transaction options."""
    try:
        user_id = update.effective_user.id
        user = get_user_by_telegram_id(user_id)
        
        if not user:
            update.message.reply_text(
                "You don't have an account! Use /create_account to create one."
            )
        return
    
        # Create keyboard with deposit/withdraw options
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💳 Withdraw", callback_data="withdraw")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"💰 *Your Balance*\n\n"
            f"Current Balance: ETB {user.balance:.2f}\n\n"
            f"What would you like to do?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Error in balance command: {e}")
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
    )


@cooldown()
async def deposit(update: Update, context: CallbackContext) -> None:
    """Add funds to user wallet."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check if amount is provided
    if not context.args or len(context.args) == 0:
        # Provide quick deposit options
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="deposit_10"),
                InlineKeyboardButton("$25", callback_data="deposit_25"),
                InlineKeyboardButton("$50", callback_data="deposit_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="deposit_100"),
                InlineKeyboardButton("$200", callback_data="deposit_200"),
                InlineKeyboardButton("$500", callback_data="deposit_500")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💳 *Rock Paper Scissors - Deposit Funds*\n\n"
            "Select an amount to deposit or use /deposit [amount] to specify a custom amount.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Process custom amount
    try:
        amount = float(context.args[0])
        
        # Validate amount
        if amount <= 0:
            await update.message.reply_text("Deposit amount must be greater than zero.")
            return
            
        from config import MIN_DEPOSIT_AMOUNT, MAX_DEPOSIT_AMOUNT
        
        # Check min/max limits
        if amount < MIN_DEPOSIT_AMOUNT:
            await update.message.reply_text(escape_markdown(f"Minimum deposit amount is ${MIN_DEPOSIT_AMOUNT}."))
            return
            
        if amount > MAX_DEPOSIT_AMOUNT:
            await update.message.reply_text(escape_markdown(f"Maximum deposit amount is ${MAX_DEPOSIT_AMOUNT}."))
            return
        
        # Generate payment link with Capa Wallet
        success, result = PaymentSystem.deposit(user.id, amount)
        
        if not success:
            # If result is a string, it's an error message
            if isinstance(result, str):
                await update.message.reply_text(f"Error: {result}")
            else:
                await update.message.reply_text("Payment service temporarily unavailable. Please try again later.")
            return
            
        # If result is a dictionary, it has payment info
        if isinstance(result, dict):
            payment_url = result.get('payment_url', '')
            message = result.get('message', f"Please complete your payment of ${amount:.2f} using Capa Wallet")
            
            # Create payment button
            if payment_url:
                keyboard = [[InlineKeyboardButton("Pay Now", url=payment_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"💰 *Deposit Funds*\n\n"
                    f"{message}\n\n"
                    f"Amount: ${amount:.2f}\n"
                    f"Click the button below to complete your payment.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(escape_markdown(f"{message}"))
        else:
            await update.message.reply_text(f"{result}")
        
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a valid number.")


@cooldown()
async def withdraw(update: Update, context: CallbackContext) -> None:
    """Withdraw funds from user wallet."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check if amount is provided
    if not context.args or len(context.args) == 0:
        # Provide quick withdrawal options
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="withdraw_10"),
                InlineKeyboardButton("$25", callback_data="withdraw_25"),
                InlineKeyboardButton("$50", callback_data="withdraw_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="withdraw_100"),
                InlineKeyboardButton("All", callback_data=f"withdraw_{user.balance}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💸 *Withdraw Funds*\n\n"
            f"Current balance: ${user.balance:.2f}\n\n"
            "Select an amount to withdraw or use /withdraw [amount] to specify a custom amount.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Process custom amount
    try:
        amount = float(context.args[0])
        
        # Validate amount
        if amount <= 0:
            await update.message.reply_text("Withdrawal amount must be greater than zero.")
            return
            
        from config import MIN_WITHDRAW_AMOUNT, MAX_WITHDRAW_AMOUNT
        
        # Check min/max limits
        if amount < MIN_WITHDRAW_AMOUNT:
            await update.message.reply_text(escape_markdown(f"Minimum withdrawal amount is ${MIN_WITHDRAW_AMOUNT}."))
            return
            
        if amount > MAX_WITHDRAW_AMOUNT:
            await update.message.reply_text(escape_markdown(f"Maximum withdrawal amount is ${MAX_WITHDRAW_AMOUNT}."))
            return
            
        # Check if user has enough balance
        if user.balance < amount:
            await update.message.reply_text(f"Insufficient balance. You have ${user.balance:.2f}.")
            return
            
        # Ask for wallet address
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel_withdrawal")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the withdrawal amount in context.user_data
        if not hasattr(context, 'user_data'):
            context.user_data = {}
        context.user_data['withdrawal_amount'] = amount
        
        await update.message.reply_text(
            "Please enter your Capa Wallet address to receive the funds.\n"
            "Reply directly with your wallet address or click Cancel.",
            reply_markup=reply_markup
        )
        
        # In a real implementation, we would await the user's wallet address input
        # For now, we'll use a placeholder address for demonstration
        # This is where we would register a conversation handler in a production bot
        wallet_address = "capa_wallet_address_placeholder"
        
        # Process withdrawal request
        success, result = PaymentSystem.request_withdrawal(user.id, amount)
        
        if not success:
            # If result is a string, it's an error message
            if isinstance(result, str):
                await update.message.reply_text(f"Error: {result}")
            else:
                await update.message.reply_text("Payment service temporarily unavailable. Please try again later.")
            return
            
        # If result is a dictionary, it has withdrawal info
        if isinstance(result, dict):
            message = result.get('message', f"Withdrawal request for ${amount:.2f} has been submitted and is awaiting approval.")
            await update.message.reply_text(
                f"💸 *Withdrawal Request*\n\n"
                f"{message}\n\n"
                f"You will be notified once your withdrawal is processed.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(escape_markdown(f"{result}"))
        
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a valid number.")


@cooldown()
async def history(update: Update, context: CallbackContext) -> None:
    """View user transaction and game history."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Get transactions
    transactions = PaymentSystem.get_transactions(user.id)
    transaction_text = "*Recent Transactions:*\n"
    
    if not transactions:
        transaction_text += "No transactions found.\n"
    else:
        for tx in transactions[:5]:  # Limit to 5 for display
            tx_type = tx.transaction_type.capitalize()
            amount_str = f"+${tx.amount:.2f}" if tx.amount >= 0 else f"-${abs(tx.amount):.2f}"
            date_str = tx.created_at.strftime("%Y-%m-%d %H:%M")
            
            transaction_text += f"{date_str}: {tx_type} {amount_str} ({tx.status})\n"
    
    # Get games
    games = RPSGame.get_user_games(user.id)
    game_text = "\n*Recent Games:*\n"
    
    if not games:
        game_text += "No games played yet.\n"
    else:
        for game in games[:5]:  # Limit to 5 for display
            date_str = game.created_at.strftime("%Y-%m-%d %H:%M")
            result = "Won" if game.winner_id == user.id else "Lost" if game.winner_id else "Draw"
            
            game_text += f"{date_str}: Game #{game.id} - {result} (Bet: ${game.bet_amount:.2f})\n"
    
    # Stats summary
    stats_text = "\n*Your Stats:*\n"
    stats_text += f"Total games: {user.games_played}\n"
    win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
    stats_text += f"Wins: {user.games_won} ({win_rate:.1f}%)\n"
    stats_text += f"Current balance: ${user.balance:.2f}\n"
    
    # Combine all sections
    full_text = transaction_text + game_text + stats_text
    
    await update.message.reply_text(full_text, parse_mode='Markdown')


@cooldown()
async def join_game(update: Update, context: CallbackContext) -> None:
    """Join or create a game."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check for custom bet amount
    bet_amount = BET_AMOUNT_DEFAULT
    if context.args:
        try:
            bet_amount = float(context.args[0])
            if bet_amount <= 0:
                await update.message.reply_text("Bet amount must be greater than 0.")
                return
        except ValueError:
            await update.message.reply_text("Invalid bet amount. Please provide a valid number.")
            return
    
    # Check user balance
    if user.balance < bet_amount:
        await update.message.reply_text(
            f"Insufficient balance. You need ${bet_amount:.2f}, but your balance is ${user.balance:.2f}."
        )
        return
    
    # Look for a waiting game with same bet amount
    game = Game.query.filter_by(status='waiting', bet_amount=bet_amount).first()
    
    # If no game exists, create one
    if not game:
        game = Game(
            bet_amount=bet_amount,
            status='waiting',
            created_at=datetime.utcnow()
        )
        db.session.add(game)
        db.session.commit()

    # Check if user is already in this game
    existing_participant = GameParticipant.query.filter_by(
        game_id=game.id,
        user_id=user.id
    ).first()

    if existing_participant:
        await update.message.reply_text(f"You are already in Game #{game.id}.")
        return
    
    # Join the game
    participant = GameParticipant(
        game_id=game.id,
        user_id=user.id,
        choice=None
    )
    db.session.add(participant)
    db.session.commit()

        participants = GameParticipant.query.filter_by(game_id=game.id).count()
        
        await update.message.reply_text(
        f"You joined Game #{game.id} with a bet of ${bet_amount:.2f}.\n"
        f"Waiting for more players... ({participants}/3)"
    )

    # If game is now full (3 players), start it
        if participants >= 3:
        game.status = 'active'
        db.session.commit()

        # Notify all players
        for p in GameParticipant.query.filter_by(game_id=game.id).all():
            user_obj = User.query.get(p.user_id)
            if user_obj and user_obj.telegram_id:
                        try:
                            await context.bot.send_message(
                                chat_id=user_obj.telegram_id,
                                text=(
                                    f"🎮 Game #{game.id} is starting!\n\n"
                                    f"Bet amount: ${game.bet_amount:.2f}\n"
                                    f"Make your choice:"
                                ),
                                reply_markup=GAME_CHOICES
                            )
                        except Exception as e:
                    LOGGER.error(f"Error notifying user {user_obj.telegram_id}: {e}")


@cooldown()
async def game_status(update: Update, context: CallbackContext) -> None:
    """Check status of current games."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Get user's active games
    active_games = db.session.query(Game).join(
        GameParticipant, Game.id == GameParticipant.game_id
    ).filter(
        GameParticipant.user_id == user.id,
        Game.status.in_(['waiting', 'active'])
    ).all()
    
    if not active_games:
        # Show available games to join
        waiting_games = Game.query.filter_by(status='waiting').all()
        
        if waiting_games:
            text = "🎮 *Available Games*\n\n"
            for game in waiting_games:
                participants = GameParticipant.query.filter_by(game_id=game.id).count()
                text += (
                    f"Game #{game.id}\n"
                    f"Bet: ${game.bet_amount:.2f}\n"
                    f"Players: {participants}/3\n"
                    f"Created: {game.created_at.strftime('%H:%M:%S')}\n\n"
                )
            
            text += "Use /join_game [amount] to join a game."
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "There are no active games at the moment.\n"
                "Start a new game with /join_game!"
            )
        return
    
    # Display user's active games
    text = "🎮 *Your Active Games*\n\n"
    
    for game in active_games:
        participants = GameParticipant.query.filter_by(game_id=game.id).count()
        participant = GameParticipant.query.filter_by(game_id=game.id, user_id=user.id).first()
        
        text += (
            f"Game #{game.id}\n"
            f"Status: {game.status.capitalize()}\n"
            f"Bet: ${game.bet_amount:.2f}\n"
            f"Players: {participants}/3\n"
        )
        
        if game.status == 'active':
            if participant.choice:
                text += f"Your choice: {participant.choice.capitalize()}\n"
            else:
                text += "You need to make your choice!\n"
        
        text += "\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


@cooldown()
async def leaderboard(update: Update, context: CallbackContext) -> None:
    """Display the leaderboard."""
    leaderboard_data = get_leaderboard(10)
    
    text = "🏆 *Rock Paper Scissors Leaderboard* 🏆\n\n"
    
    if not leaderboard_data:
        text += "No players on the leaderboard yet."
    else:
        for i, player in enumerate(leaderboard_data, 1):
            text += (
                f"{i}. {player['username']}\n"
                f"   Games: {player['games_played']} | Wins: {player['games_won']} | "
                f"Win Rate: {player['win_rate']:.1f}%\n\n"
            )
    
    await update.message.reply_text(text, parse_mode='Markdown')


@cooldown()
async def profile(update: Update, context: CallbackContext) -> None:
    """Display user profile with recent transactions and games."""
    if not user_exists(update):
        update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Get transactions
    transactions = PaymentSystem.get_transactions(user.id)
    transaction_text = "*Recent Transactions:*\n"
    
    if not transactions:
        transaction_text += "No transactions found.\n"
    else:
        for tx in transactions[:5]:  # Limit to 5 for display
            tx_type = tx.transaction_type.capitalize()
            amount_str = f"+${tx.amount:.2f}" if tx.amount >= 0 else f"-${abs(tx.amount):.2f}"
            date_str = tx.created_at.strftime("%Y-%m-%d %H:%M")
            transaction_text += f"{date_str}: {tx_type} {amount_str} ({tx.status})\n"
    
    # Get games
    games = RPSGame.get_user_games(user.id)
    game_text = "\n*Recent Games:*\n"
    
    if not games:
        game_text += "No games played yet.\n"
    else:
        for game in games[:5]:  # Limit to 5 for display
            date_str = game.created_at.strftime("%Y-%m-%d %H:%M")
            result = "Won" if game.winner_id == user.id else "Lost" if game.winner_id else "Draw"
            game_text += f"{date_str}: Game #{game.id} - {result} (Bet: ${game.bet_amount:.2f})\n"
    
    # Stats summary
    stats_text = "\n*Your Stats:*\n"
    stats_text += f"Total games: {user.games_played}\n"
    win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
    stats_text += f"Wins: {user.games_won} ({win_rate:.1f}%)\n"
    stats_text += f"Current balance: ${user.balance:.2f}\n"
    
    # Combine all sections
    full_text = transaction_text + game_text + stats_text
    
    try:
        update.message.reply_text(full_text, parse_mode='Markdown')
    except Exception as e:
        LOGGER.error(f"Error sending profile message: {e}")
        update.message.reply_text("An error occurred while displaying your profile. Please try again later.")


# Admin commands
@admin_required
async def admin_stats(update: Update, context: CallbackContext) -> None:
    """Admin command to view system statistics."""
    stats = AdminService.get_system_stats()
    
    text = (
        "📊 *System Statistics*\n\n"
        f"Total Users: {stats['total_users']} (+{stats['new_users_24h']} in 24h)\n"
        f"Total Games: {stats['total_games']} (+{stats['games_24h']} in 24h)\n"
        f"Transaction Volume: ${stats['total_volume']:.2f}\n"
        f"Volume (24h): ${stats['volume_24h']:.2f}\n\n"
        f"Active Users (24h): {stats['active_users_24h']}\n"
        f"Pending Withdrawals: {stats['pending_withdrawals']}\n"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')


@admin_required
async def admin_users(update: Update, context: CallbackContext) -> None:
    """Admin command to view and manage users."""
    # Check if a search query is provided
    if context.args and len(context.args) > 0:
        query = context.args[0]
        users = AdminService.search_user(query)
        
        if not users:
            await update.message.reply_text(escape_markdown(f"No users found matching '{query}'."))
            return
        
        text = f"🔍 *Search Results for '{query}'*\n\n"
        
        for user in users:
            text += (
                f"ID: {user.id}\n"
                f"Username: {user.username}\n"
                f"Balance: ${user.balance:.2f}\n"
                f"Games: {user.games_played} (Won: {user.games_won})\n\n"
            )
            
            # Add admin action buttons
            keyboard = [
                [
                    InlineKeyboardButton(f"View {user.username}", callback_data=f"admin_view_user_{user.id}"),
                ]
            ]
            
            if user.is_admin:
                keyboard[0].append(InlineKeyboardButton("Remove Admin", callback_data=f"admin_remove_admin_{user.id}"))
            else:
                keyboard[0].append(InlineKeyboardButton("Make Admin", callback_data=f"admin_make_admin_{user.id}"))
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            return
    
    # No search query, show recent users
    recent_users = AdminService.get_recent_users(5)
    
    text = "👥 *Recent Users*\n\n"
    
    for user in recent_users:
        text += (
            f"Username: {user.username}\n"
            f"Created: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Games: {user.games_played}\n\n"
        )
    
    # Add search instruction
    text += "Use /admin_users [query] to search for users."
    
    await update.message.reply_text(text, parse_mode='Markdown')


@admin_required
async def admin_games(update: Update, context: CallbackContext) -> None:
    """Admin command to view recent games."""
    recent_games = AdminService.get_recent_games(5)
    
    text = "🎮 *Recent Games*\n\n"
    
    if not recent_games:
        text += "No completed games found."
    else:
        for game in recent_games:
            participants = GameParticipant.query.filter_by(game_id=game.id).all()
            
            text += (
                f"Game #{game.id}\n"
                f"Bet: ${game.bet_amount:.2f}\n"
                f"Players: {len(participants)}\n"
            )
            
            # List participants and their choices
            for p in participants:
                user = User.query.get(p.user_id)
                winner_text = " (Winner)" if game.winner_id == p.user_id else ""
                text += f"  - {user.username}: {p.choice.capitalize() if p.choice else 'No choice'}{winner_text}\n"
            
            text += f"Completed: {game.completed_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


@admin_required
async def admin_withdrawals(update: Update, context: CallbackContext) -> None:
    """Admin command to manage withdrawal requests."""
    pending_withdrawals = AdminService.get_pending_withdrawals()
    
    if not pending_withdrawals:
        await update.message.reply_text("No pending withdrawal requests.")
        return
    
    for withdrawal in pending_withdrawals:
        user = User.query.get(withdrawal.user_id)
        transaction = Transaction.query.get(withdrawal.transaction_id)
        
        text = (
            f"💸 *Withdrawal Request #{withdrawal.id}*\n\n"
            f"User: {user.username} (ID: {user.id})\n"
            f"Amount: ${withdrawal.amount:.2f}\n"
            f"Requested: {withdrawal.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
        
        # Add approval/rejection buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_withdrawal_{withdrawal.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_withdrawal_{withdrawal.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# Callback query handlers

async def send_game_animation(chat_id, game_id, context):
    """Send animated game results to a chat"""
    # Get game details
    game = Game.query.get(game_id)
    if not game or game.status != 'completed':
        return
    
    participants = GameParticipant.query.filter_by(game_id=game_id).all()
    if len(participants) < 2:
            return
        
    # Show participants making their choices
    choices_text = "🎮 *Game Results* 🎮\n\n"
    
    # Send loading message
    message = await context.bot.send_message(
        chat_id=chat_id,
        text="🎲 *Calculating Results* 🎲\n\nPreparing animation...",
        parse_mode='Markdown'
    )
    
    # Show each player's choice with animation
    for participant in participants:
        user = User.query.get(participant.user_id)
        username = user.username if user else "Unknown"
        
        if participant.choice == 'rock':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=ROCK_GIF,
                caption=f"{username} chose ROCK 🗿"
            )
        elif participant.choice == 'paper':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=PAPER_GIF,
                caption=f"{username} chose PAPER 📄"
            )
        elif participant.choice == 'scissors':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=SCISSORS_GIF,
                caption=f"{username} chose SCISSORS ✂️"
            )
    
    # Small delay for dramatic effect
    import asyncio
    await asyncio.sleep(1)
    
    # Show result animation
    result_text = "🏆 *Results* 🏆\n\n"
                            
                            if game.winner_id:
                                winner = User.query.get(game.winner_id)
        winner_username = winner.username if winner else "Unknown"
        
        # Find winner's choice
        winner_choice = None
        for p in participants:
            if p.user_id == game.winner_id:
                winner_choice = p.choice
        
        if winner_choice == 'rock':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=ROCK_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with ROCK! 🎉\n\nRock crushes scissors!"
            )
        elif winner_choice == 'paper':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=PAPER_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with PAPER! 🎉\n\nPaper covers rock!"
            )
        elif winner_choice == 'scissors':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=SCISSORS_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with SCISSORS! 🎉\n\nScissors cut paper!"
            )
                            else:
        # It's a draw
        await context.bot.send_animation(
            chat_id=chat_id,
            animation=DRAW_GIF,
            caption="It's a DRAW! No winner this time."
        )
    
    # Final result message
    pot_size = game.bet_amount * len(participants)
    if game.winner_id:
        winner = User.query.get(game.winner_id)
        platform_fee = pot_size * (PLATFORM_FEE_PERCENT / 100)
        winnings = pot_size - platform_fee
        
        result_text = f"Game #{game_id} Results:\n"
        result_text += f"Winner: {winner.username}\n"
        result_text += f"Pot: ${pot_size:.2f}\n"
        result_text += f"Platform Fee: ${platform_fee:.2f}\n"
        result_text += f"Winnings: ${winnings:.2f}"
    else:
        result_text = f"Game #{game_id} Results:\n"
        result_text += "Result: Draw - Bets have been refunded."
                            
                            await context.bot.send_message(
        chat_id=chat_id,
        text=result_text
    )

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    query.answer()

    try:
        if query.data.startswith('choice_'):
            choice = query.data.split('_')[1]
            game_id = context.user_data.get('current_game')
            
            if not game_id:
                await query.edit_message_text("No active game found!")
                return

            # Get game and participants
            game = Game.query.get(game_id)
            if not game:
                await query.edit_message_text("Game not found!")
                return

            # Update user's choice
            user = get_user_by_telegram_id(update.effective_user.id)
            user_participant = GameParticipant.query.filter_by(
                game_id=game.id,
                user_id=user.id
            ).first()
            
            if not user_participant:
                await query.edit_message_text("You are not part of this game!")
                return

            # Record the choice
            user_participant.choice = choice
            db.session.commit()

            # Check if all players have made their choices
            participants = GameParticipant.query.filter_by(game_id=game.id).all()
            all_chosen = all(p.choice for p in participants)

            if all_chosen:
                # Initialize animator
                animator = RPSGameAnimator()
                
                # Prepare player choices for animation
                choices = {
                    User.query.get(p.user_id).username: p.choice 
                    for p in participants
                }
                
                # Determine winner
                winner = None
                winner_id = None
                winner_choice = None
                
                if len(set(p.choice for p in participants)) == 3:
                    # All different choices - it's a draw
                    winner = None
        else:
                    # Count wins for each player
                    wins = {p.user_id: 0 for p in participants}
                    for p1 in participants:
                        for p2 in participants:
                            if p1.id != p2.id:
                                if animator.beats(p1.choice, p2.choice):
                                    wins[p1.user_id] += 1
                    
                    # Find player(s) with most wins
                    max_wins = max(wins.values())
                    winners = [uid for uid, win_count in wins.items() if win_count == max_wins]
                    
                    if len(winners) == 1:
                        winner_id = winners[0]
                        winner = User.query.get(winner_id).username
                        winner_choice = next(p.choice for p in participants if p.user_id == winner_id)

                # Calculate and distribute prize
                pot_size = game.bet_amount * len(participants)
                platform_fee = pot_size * (PLATFORM_FEE_PERCENT / 100)
                prize = pot_size - platform_fee

                # Send animations to all participants
                for p in participants:
                    try:
                        user_obj = User.query.get(p.user_id)
                        chat_id = user_obj.telegram_id
                        
                        # Show each player's choice
                        for participant in participants:
                            participant_user = User.query.get(participant.user_id)
                            choice_animation = animator.get_match_animation(participant.choice, participant.choice)
                            if choice_animation:
                                with open(choice_animation, 'rb') as anim:
                                    await context.bot.send_animation(
                                        chat_id=chat_id,
                                        animation=anim,
                                        caption=f"{participant_user.username} chose {participant.choice.upper()}"
                                    )
                        
                        # Show result animation
                        result_animation = animator.get_result_animation(winner_choice)
                        if result_animation:
                            with open(result_animation, 'rb') as anim:
                                if winner:
                                    caption = f"🎉 {winner} WINS with {winner_choice.upper()}! 🎉"
                                    if winner_choice == 'rock':
                                        caption += "\n\nRock crushes scissors!"
                                    elif winner_choice == 'paper':
                                        caption += "\n\nPaper covers rock!"
                                    else:  # scissors
                                        caption += "\n\nScissors cut paper!"
                                else:
                                    caption = "It's a DRAW! All bets refunded."
                                
                                await context.bot.send_animation(
                                    chat_id=chat_id,
                                    animation=anim,
                                    caption=caption
                                )
                        
                        # Send final results message
                        if winner_id:
                            winner_user = User.query.get(winner_id)
                            winner_user.balance += Decimal(str(prize))
                            result_text = (
                                f"🏆 Game #{game.id} Results:\n\n"
                                f"Winner: {winner_user.username}\n"
                                f"Prize Pool: ETB {pot_size:.2f}\n"
                                f"Platform Fee: ETB {platform_fee:.2f}\n"
                                f"Net Prize: ETB {prize:.2f}"
                            )
                        else:
                            # Draw - refund bets
                            refund = game.bet_amount
                            for participant in participants:
                                participant.user.balance += Decimal(str(refund))
                            result_text = (
                                f"🤝 Game #{game.id} Results:\n\n"
                                f"Result: Draw\n"
                                f"All players have been refunded ETB {refund:.2f}"
                            )
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=result_text
                        )
                        
                    except Exception as e:
                        LOGGER.error(f"Error sending animation to user {p.user_id}: {e}")

                # Mark game as completed
                game.status = 'completed'
                game.completed_at = datetime.utcnow()
                game.winner_id = winner_id
        db.session.commit()
        
            else:
                # Not all players have chosen yet
                choices_made = sum(1 for p in participants if p.choice)
        await query.edit_message_text(
                    f"Choice recorded! Waiting for other players...\n"
                    f"({choices_made}/{len(participants)} players ready)"
                )

    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}")
        await query.edit_message_text("❌ Error processing game result. Please try again.")
        if 'current_game' in context.user_data:
            del context.user_data['current_game']
        db.session.rollback()


async def whoami(update: Update, context: CallbackContext) -> None:
    """Debug command to show user information"""
    telegram_id = update.effective_user.id
    telegram_username = update.effective_user.username
    
    user = get_user_by_telegram_id(telegram_id)
    
    if user:
        await update.message.reply_text(
            escape_markdown("*User Information*\n\n") +
            f"Telegram ID: `{telegram_id}`\n"
            f"Telegram Username: @{telegram_username}\n"
            f"Database ID: {user.id}\n"
            f"Username: {user.username}\n"
            f"Balance: ${user.balance:.2f}\n"
            f"Admin: {'Yes' if user.is_admin else 'No'}\n"
            f"Account Created: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Last Active: {user.last_active.strftime('%Y-%m-%d %H:%M')}\n"
            f"Games Played: {user.games_played}\n"
            f"Games Won: {user.games_won}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"*User Not Registered*\n\n"
            f"Telegram ID: `{telegram_id}`\n"
            f"Telegram Username: @{telegram_username}\n\n"
            f"You need to create an account using /create_account [username]",
            parse_mode='Markdown'
        )


# Add this function to handle unknown commands
async def unknown_command(update: Update, context: CallbackContext) -> None:
    """Handle unknown commands by showing available commands."""
    LOGGER.info(f"User {update.effective_user.id} tried unknown command: {update.message.text}")
    
    await update.message.reply_text(
        "Sorry, I don't recognize that command. Here are the available commands:\n\n"
        "/start - Start the bot\n"
        "/create_account - Create a new account\n"
        "/help - Show all available commands\n\n"
        "Please make sure you type the commands exactly as shown, including the forward slash."
    )



async def debug_command(update: Update, context: CallbackContext) -> None:
    """Debug command to test bot functionality."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Simple message without parse_mode
    await update.message.reply_text(
        f"Debug command works!\n"
        f"Your Telegram ID: {user_id}\n"
        f"Your username: {username}"
    )
    
    # Check if user exists in database
    user = get_user_by_telegram_id(user_id)
    if user:
        # Send a second message with user info
        await update.message.reply_text(
            f"Database info:\n"
            f"DB ID: {user.id}\n"
            f"Username: {user.username}\n"
            f"Balance: {user.balance:.2f}\n"
            f"Exists in DB: Yes"
        )
            else:
        await update.message.reply_text(
            f"You don't exist in the database.\n"
            f"Use /create_account to create an account."
        )


async def handle_menu_button(update: Update, context: CallbackContext) -> None:
    """Handle menu button selections"""
    text = update.message.text
    
    if text == "💰 Account":
        await update.message.reply_text(
            "📋 *Account Commands*\n\n"
            "/create_account - Create your account\n"
            "/balance - Check your wallet balance\n"
            "/deposit - Add funds to your wallet\n"
            "/withdraw - Withdraw funds\n"
            "/delete_account - Delete your account\n"
            "/history - View your transaction history",
            parse_mode='Markdown'
        )
    elif text == "🎮 Game":
        await update.message.reply_text(
            "📋 *Game Commands*\n\n"
            "/join_game - Join a match with default bet ($10)\n"
            "/join_game [amount] - Join with custom bet amount\n"
            "/game_status - Check current game status\n"
            "/simulate - Watch RPS battle simulation\n"
            "/simulate [rock] [paper] [scissors] - Custom simulation\n\n"
            "Example:\n"
            "/simulate 30 30 30 - Start with 30 of each type",
            parse_mode='Markdown'
        )
    elif text == "📊 Stats":
        await update.message.reply_text(
            "📋 *Stats Commands*\n\n"
            "/leaderboard - View top players\n"
            "/profile - View your stats",
            parse_mode='Markdown'
        )
    elif text == "ℹ️ Help":
        await update.message.reply_text(
            "📋 *Help Commands*\n\n"
            "/help - Show all available commands\n"
            "/about - About the Rock Paper Scissors bot",
            parse_mode='Markdown'
        )


@cooldown()
def simulate(update: Update, context: CallbackContext) -> None:
    """Simulate a game with AI players"""
    try:
        # Check if user has an account
        user = get_user_by_telegram_id(update.effective_user.id)
        if not user:
            update.message.reply_text(
                "You need to create an account first! Use /create_account"
            )
            return

        # Parse bet amount if provided
        bet_amount = 10.0  # Default bet amount
        if context.args:
            try:
                bet_amount = float(context.args[0])
                if bet_amount <= 0:
                    update.message.reply_text("Bet amount must be greater than 0!")
                    return
            except ValueError:
                update.message.reply_text("Invalid bet amount! Please provide a valid number.")
                return

        # Check user balance
        if user.balance < Decimal(str(bet_amount)):
            update.message.reply_text(
                f"Insufficient balance! You need ETB {bet_amount:.2f} to play."
            )
            return

        # Create AI players
        ai_names = ["🤖 Bot-Alpha", "🤖 Bot-Beta"]
        ai_users = []
        
        for name in ai_names:
            ai_user = User(
                username=name,
                telegram_id=None,
                balance=Decimal('1000.00'),
                is_bot=True,
                created_at=datetime.utcnow()
            )
            db.session.add(ai_user)
            ai_users.append(ai_user)
        
        # Create game
        game = Game(
            bet_amount=bet_amount,
            status='active',
            created_at=datetime.utcnow()
        )
        db.session.add(game)
        
        # Add participants
        participants = [user] + ai_users
        choices = ['rock', 'paper', 'scissors']
        
        for p in participants:
            # Deduct bet amount
            p.balance -= Decimal(str(bet_amount))
            
            # Add to game
            participant = GameParticipant(
                game_id=game.id,
                user_id=p.id,
                choice=random.choice(choices) if p.is_bot else None,
                joined_at=datetime.utcnow()
            )
            db.session.add(participant)
        
        db.session.commit()

        # Store game ID in user data for callback handling
        context.user_data['current_game'] = game.id

        # Send initial message
        update.message.reply_text(
            f"🎮 Simulation started!\n\n"
            f"Game #{game.id}\n"
            f"Bet amount: ETB {bet_amount:.2f}\n\n"
            f"Players:\n"
            f"👤 You\n"
            f"🤖 {ai_names[0]}\n"
            f"🤖 {ai_names[1]}\n\n"
            f"Make your choice:",
            reply_markup=GAME_CHOICES
        )

    except Exception as e:
        LOGGER.error(f"Error in simulate command: {e}")
        update.message.reply_text("❌ Error starting simulation. Please try again.")
        if 'current_game' in context.user_data:
            del context.user_data['current_game']
        db.session.rollback()

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        LOGGER.error("No BOT_TOKEN provided. Please set the BOT_TOKEN environment variable.")
        return
    
    try:
        # Initialize the updater and dispatcher
        updater = Updater(BOT_TOKEN)
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
        dispatcher.add_handler(CommandHandler("simulate", simulate))
        
        # Stats commands
        dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
        dispatcher.add_handler(CommandHandler("profile", profile))
        
        # Add callback query handler for buttons
        dispatcher.add_handler(CallbackQueryHandler(button_callback))
        
        # Add message handler for menu buttons
        dispatcher.add_handler(MessageHandler(
            filters.Regex("^(💰 Account|🎮 Game|📊 Stats|ℹ️ Help)$"),
            handle_menu_button
        ))
        
        # Add handler for unknown commands
        dispatcher.add_handler(MessageHandler(filters.Command, unknown_command))
        
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
