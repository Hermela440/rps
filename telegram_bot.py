import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from rps_simulation import create_rps_simulation
# Import Update from telegram
from telegram import Update
from datetime import datetime

from app import db
from models import User, Game, GameParticipant, Transaction
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
from config import BOT_TOKEN, ADMIN_USERS, LOGGER, BET_AMOUNT_DEFAULT
@cooldown()
async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... existing code ...
    
    # Fix: Remove parse_mode=Markdown or escape $ symbols
    await update.message.reply_text(
        f"Account created successfully! Welcome, {username}.\n"
        f"You've received a welcome bonus of $100.00 in your wallet.\n"
        f"Your current balance: ${user.balance:.2f}\n\n"
        f"Use /join_game to start playing!"
    )  # Remove parse_mode='Markdown'

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
        "/game_status": "Check status of current game"
    ,
        "/replay": "Replay a game animation with GIFs"
    ,
        "/simulate": "Run Rock-Paper-Scissors simulation"
    },
    "📊 Stats Commands": {
        "/leaderboard": "View top players",
        "/profile": "View your profile stats"
    },
    "ℹ️ Help Commands": {
        "/help": "Show this help message",
        "/about": "About the RPS Arena bot"
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    # Create a keyboard with command categories
    keyboard = [
        [KeyboardButton("💰 Account"), KeyboardButton("🎮 Game")],
        [KeyboardButton("📊 Stats"), KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome to RPS Arena Bot! Choose a command category or use / to see all commands:",
        reply_markup=reply_markup
    )
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_text = "📚 *RPS Arena Bot Commands* 📚\n\n"
    
    for category, commands in COMMANDS.items():
        help_text += f"*{category}*\n"
        for cmd, desc in commands.items():
            help_text += f"{cmd} - {desc}\n"
        help_text += "\n"
    
    # Add admin commands if user is admin
    user = get_user_by_telegram_id(update.effective_user.id)
    if user and user.is_admin:
        help_text += "*🔑 Admin Commands*\n"
        for cmd, desc in ADMIN_COMMANDS.items():
            help_text += f"{cmd} - {desc}\n"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send information about the bot."""
    await update.message.reply_text(
        "📱 *RPS Arena Bot* 📱\n\n"
        "A Telegram bot for playing Rock-Paper-Scissors with virtual betting.\n\n"
        "Features:\n"
        "• Play RPS with 3 players\n"
        "• Virtual wallet system\n"
        "• Betting on matches\n"
        "• Leaderboard and statistics\n\n"
        "Created as a sample project for demonstration purposes.",
        parse_mode='Markdown'
    )


@cooldown()
async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new user account."""
    try:
        telegram_id = update.effective_user.id
        telegram_username = update.effective_user.username
        
        # Log the request
        LOGGER.info(f"Account creation request from Telegram ID: {telegram_id}, Username: {telegram_username}")
        
        # Check if user already exists
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            await update.message.reply_text("You already have an account.")
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
                await update.message.reply_text(
                    "Please provide a username: /create_account [username]"
                )
                return
        
        # Simple username validation (3-32 chars, alphanumeric, underscores, hyphens)
        if len(username) < 3 or len(username) > 32:
            await update.message.reply_text(
                f"Username '{username}' must be between 3 and 32 characters."
            )
            return
            
        # Simplified validation to avoid regex issues
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not all(c in valid_chars for c in username):
            await update.message.reply_text(
                f"Username '{username}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed."
            )
            return
        
        # Check if username is already taken (with error handling)
        try:
            existing_name = User.query.filter_by(username=username).first()
            if existing_name:
                await update.message.reply_text(f"Username '{username}' is already taken. Please try another one.")
                return
        except Exception as e:
            LOGGER.error(f"Database error checking username: {e}")
            await update.message.reply_text("Error checking username availability. Please try again later.")
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
            await update.message.reply_text(
               f"Account created successfully! Welcome, {username}."
                f"You've received a welcome bonus of $100.00 in your wallet.\n"
                f"Your current balance: ${user.balance:.2f}\n\n"
                f"Use /join_game to start playing!"
            )
            
        except Exception as e:
            LOGGER.error(f"Error creating account: {e}")
            db.session.rollback()
            await update.message.reply_text("Error creating account. Please try again later.")
            
    except Exception as e:
        LOGGER.error(f"Unexpected error in create_account: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again.")
async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a user account."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    
    # Create confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton("Yes, delete my account", callback_data="confirm_delete_account"),
            InlineKeyboardButton("No, keep my account", callback_data="cancel_delete_account")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚠️ Are you sure you want to delete your account?\n\n"
        f"Username: {user.username}\n"
        f"Balance: ${user.balance:.2f}\n"
        f"Games played: {user.games_played}\n\n"
        f"This action cannot be undone!",
        reply_markup=reply_markup
    )


@cooldown()
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check user balance."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    await update.message.reply_text(
        f"💰 Your Wallet Balance\n\n"
        f"Username: {user.username}\n"
        f"Current balance: ${user.balance:.2f}\n\n"
        f"Use /deposit to add funds or /withdraw to cash out."
    )


@cooldown()
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            "💳 *Deposit Funds*\n\n"
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
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join a game match."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check if custom bet amount provided
    bet_amount = BET_AMOUNT_DEFAULT
    if context.args and len(context.args) > 0:
        try:
            bet_amount = float(context.args[0])
            if bet_amount <= 0:
                await update.message.reply_text("Bet amount must be greater than zero.")
                return
        except ValueError:
            await update.message.reply_text("Invalid bet amount. Please enter a valid number.")
            return
    
    # Check user balance
    if user.balance < bet_amount:
        await update.message.reply_text(
            f"Insufficient balance. You need ${bet_amount:.2f} to join this game.\n"
            f"Your current balance: ${user.balance:.2f}\n"
            f"Use /deposit to add more funds."
        )
        return
    else:
        # If game is now full (3 players), send choice options to all players
        if participants >= 3:
            # Refresh game object to get updated status
            game = Game.query.get(game.id)
            
            if game.status == 'active':
                # Notify all participants
                for participant in game.participants:
                    user_obj = User.query.get(participant.user_id)
                    if user_obj.telegram_id:
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
                            LOGGER.error(f"Error sending message to user {user_obj.telegram_id}: {e}")
    else:
        await update.message.reply_text(message)


@cooldown()
async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the leaderboard."""
    leaderboard_data = get_leaderboard(10)
    
    text = "🏆 *RPS Arena Leaderboard* 🏆\n\n"
    
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
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user profile."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Calculate stats
    win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
    
    # Get user ranking based on win rate (simplified version)
    users = User.query.filter(User.games_played > 0).all()
    
    # Calculate win rate for each user
    user_stats = []
    for u in users:
        u_win_rate = (u.games_won / u.games_played * 100) if u.games_played > 0 else 0
        user_stats.append({
            'id': u.id,
            'win_rate': u_win_rate
        })
    
    # Sort by win rate (descending)
    sorted_stats = sorted(user_stats, key=lambda x: x['win_rate'], reverse=True)
    
    # Find user's rank
    rank = next((i + 1 for i, u in enumerate(sorted_stats) if u['id'] == user.id), len(sorted_stats))
    
    text = (
        f"👤 *Player Profile: {user.username}*\n\n"
        f"Rank: #{rank}\n"
        f"Balance: ${user.balance:.2f}\n\n"
        f"Games Played: {user.games_played}\n"
        f"Games Won: {user.games_won}\n"
        f"Win Rate: {win_rate:.1f}%\n\n"
        f"Account Created: {user.created_at.strftime('%Y-%m-%d')}\n"
    )
    
    # Admin status
    if user.is_admin:
        text += "\n🔑 *Admin User*\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')


# Admin commands
@admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def admin_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()  # Answer the callback query to clear the loading state
    
    data = query.data
    user = get_user_by_telegram_id(update.effective_user.id)
    
    if not user:
        await query.edit_message_text("You don't have an account. Use /create_account to get started.")
        return
    
    # Game choice callbacks
    if data.startswith("choice_"):
        choice = data.split("_")[1]
        
        # Find the active game for this user
        participant = GameParticipant.query.join(
            Game, GameParticipant.game_id == Game.id
        ).filter(
            GameParticipant.user_id == user.id,
            Game.status == 'active',
            GameParticipant.choice == None
        ).first()
        
        if not participant:
            await query.edit_message_text(
                "You are not in an active game or you've already made your choice."
            )
            return
        
        game_id = participant.game_id
        success, message = RPSGame.make_choice(game_id, user.id, choice)
        
        if success:
            await query.edit_message_text(
                escape_markdown(f"You chose {choice.capitalize()}! Waiting for other players...")
            )
            
            # Check if game is now completed
            game = Game.query.get(game_id)
            if game.status == 'completed':
                # Get game details
                game_details = RPSGame.get_game_details(game_id)
                
                # Send results to all participants
                for p in game_details['participants']:
                    user_obj = User.query.get(p['user_id'])
                    if user_obj.telegram_id:
                        try:
                            result_text = (
                                f"🎮 *Game #{game_id} Results*\n\n"
                                f"Bet Amount: ${game.bet_amount:.2f}\n\n"
                                f"*Players:*\n"
                            )
                            
                            for player in game_details['participants']:
                                user_name = player['username']
                                player_choice = player['choice'].capitalize() if player['choice'] else "No choice"
                                winner_text = " 🏆" if player['is_winner'] else ""
                                result_text += f"- {user_name}: {player_choice}{winner_text}\n"
                            
                            if game.winner_id:
                                winner = User.query.get(game.winner_id)
                                result_text += f"\n🏆 Winner: {winner.username}"
                                
                                # Calculate winnings
                                total_pot = game.bet_amount * len(game_details['participants'])
                                platform_fee = total_pot * (PLATFORM_FEE_PERCENT / 100)
                                winnings = total_pot - platform_fee
                                
                                result_text += f"\nWinnings: ${winnings:.2f}"
                            else:
                                result_text += "\nResult: Draw - Bets have been refunded."
                                
                            # Add link to web animation
                            base_url = "https://your-name-rps.example.com"  # Your personal website URL
                            animation_url = f"{base_url}/game/{game_id}/result"
                            result_text += f"\n\n🎬 [Watch the battle animation]({animation_url})"
                            
                            await context.bot.send_message(
                                chat_id=user_obj.telegram_id,
                                text=result_text,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            LOGGER.error(f"Error sending game results to user {user_obj.telegram_id}: {e}")
        else:
            await query.edit_message_text(message)
    
    # Deposit callbacks
    elif data.startswith("deposit_"):
        amount = float(data.split("_")[1])
        success, message = PaymentSystem.deposit(user.id, amount)
        await query.edit_message_text(message)
    
    # Withdraw callbacks
    elif data.startswith("withdraw_"):
        amount = float(data.split("_")[1])
        success, message = PaymentSystem.request_withdrawal(user.id, amount)
        await query.edit_message_text(message)
    
    # Account deletion callbacks
    elif data == "confirm_delete_account":
        # Delete user data (cascade should handle related records)
        db.session.delete(user)
        db.session.commit()
        
        await query.edit_message_text(
            "Your account has been deleted. All associated data has been removed from our system.\n\n"
            "If you wish to play again in the future, you can create a new account with /create_account."
        )
    
    elif data == "cancel_delete_account":
        await query.edit_message_text(
            "Account deletion cancelled. Your account remains active."
        )
    
    # Admin callbacks
    elif data.startswith("admin_") and user.is_admin:
        parts = data.split("_")
        action = parts[1]
        
        # Admin - View user details
        if action == "view" and parts[2] == "user":
            target_user_id = int(parts[3])
            user_details = AdminService.get_user_details(target_user_id)
            
            if not user_details:
                await query.edit_message_text("User not found.")
                return
            
            target_user = user_details['user']
            win_rate = user_details['win_rate']
            
            text = (
                f"👤 *User Details: {target_user.username}*\n\n"
                f"ID: {target_user.id}\n"
                f"Telegram ID: {target_user.telegram_id}\n"
                f"Balance: ${target_user.balance:.2f}\n"
                f"Games Played: {target_user.games_played}\n"
                f"Win Rate: {win_rate:.1f}%\n"
                f"Created: {target_user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Last Active: {target_user.last_active.strftime('%Y-%m-%d %H:%M')}\n"
                f"Admin: {'Yes' if target_user.is_admin else 'No'}\n\n"
                f"*Recent Transactions:*\n"
            )
            
            # Add recent transactions
            if not user_details['transactions']:
                text += "No transactions found.\n"
            else:
                for tx in user_details['transactions'][:3]:
                    tx_type = tx.transaction_type.capitalize()
                    amount_str = f"+${tx.amount:.2f}" if tx.amount >= 0 else f"-${abs(tx.amount):.2f}"
                    date_str = tx.created_at.strftime("%Y-%m-%d %H:%M")
                    
                    text += f"{date_str}: {tx_type} {amount_str} ({tx.status})\n"
            
            await query.edit_message_text(text, parse_mode='Markdown')
        
        # Admin - Make user an admin
        elif action == "make" and parts[2] == "admin":
            target_user_id = int(parts[3])
            success, message = AdminService.make_admin(target_user_id)
            await query.edit_message_text(message)
        
        # Admin - Remove admin status
        elif action == "remove" and parts[2] == "admin":
            target_user_id = int(parts[3])
            success, message = AdminService.remove_admin(target_user_id)
            await query.edit_message_text(message)
        
        # Admin - Approve withdrawal
        elif action == "approve" and parts[2] == "withdrawal":
            withdrawal_id = int(parts[3])
            success, message = AdminService.approve_withdrawal(withdrawal_id, user.id)
            await query.edit_message_text(message)
            
            # Notify user about approved withdrawal
            withdrawal = WithdrawalRequest.query.get(withdrawal_id)
            if success and withdrawal:
                target_user = User.query.get(withdrawal.user_id)
                if target_user.telegram_id:
                    try:
                        await context.bot.send_message(
                            chat_id=target_user.telegram_id,
                            text=(
                                f"💸 *Withdrawal Approved*\n\n"
                                f"Your withdrawal request for ${withdrawal.amount:.2f} has been approved.\n"
                                f"Transaction ID: {withdrawal.transaction_id}"
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        LOGGER.error(f"Error sending approval notification to user {target_user.telegram_id}: {e}")
        
        # Admin - Reject withdrawal
        elif action == "reject" and parts[2] == "withdrawal":
            withdrawal_id = int(parts[3])
            success, message = AdminService.reject_withdrawal(withdrawal_id, user.id)
            await query.edit_message_text(message)
            
            # Notify user about rejected withdrawal
            withdrawal = WithdrawalRequest.query.get(withdrawal_id)
            if success and withdrawal:
                target_user = User.query.get(withdrawal.user_id)
                if target_user.telegram_id:
                    try:
                        await context.bot.send_message(
                            chat_id=target_user.telegram_id,
                            text=(
                                f"❌ *Withdrawal Rejected*\n\n"
                                f"Your withdrawal request for ${withdrawal.amount:.2f} has been rejected.\n"
                                f"The amount has been refunded to your wallet."
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        LOGGER.error(f"Error sending rejection notification to user {target_user.telegram_id}: {e}")


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to show user information"""
    telegram_id = update.effective_user.id
    telegram_username = update.effective_user.username
    
    user = get_user_by_telegram_id(telegram_id)
    
    if user:
        await update.message.reply_text(
            escape_markdown(f"*User Information*\n\n")
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
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands by showing available commands."""
    LOGGER.info(f"User {update.effective_user.id} tried unknown command: {update.message.text}")
    
    await update.message.reply_text(
        "Sorry, I don't recognize that command. Here are the available commands:\n\n"
        "/start - Start the bot\n"
        "/create_account - Create a new account\n"
        "/help - Show all available commands\n\n"
        "Please make sure you type the commands exactly as shown, including the forward slash."
    )



async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            "/game_status - Check current game status",
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
            "/about - About the RPS Arena bot",
            parse_mode='Markdown'
        )


@cooldown()
async def replay_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replay a game animation."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check if game ID is provided
    if not context.args or len(context.args) == 0:
        # Show recent games instead
        recent_games = db.session.query(Game).join(
            GameParticipant, Game.id == GameParticipant.game_id
        ).filter(
            GameParticipant.user_id == user.id,
            Game.status == 'completed'
        ).order_by(Game.completed_at.desc()).limit(5).all()
        
        if not recent_games:
            await update.message.reply_text("You haven't played any games yet. Use /join_game to start playing!")
            return
        
        # Create keyboard with recent games
        keyboard = []
        for game in recent_games:
            keyboard.append([InlineKeyboardButton(
                f"Game #{game.id} - {game.completed_at.strftime('%Y-%m-%d %H:%M')}",
                callback_data=f"replay_{game.id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Select a game to replay:",
            reply_markup=reply_markup
        )
        return
    
    # Get game ID from arguments
    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid game ID. Please provide a number.")
        return
    
    # Check if game exists and user participated
    game = Game.query.get(game_id)
    if not game or game.status != 'completed':
        await update.message.reply_text(f"Game #{game_id} not found or not completed.")
        return
    
    participant = GameParticipant.query.filter_by(
        game_id=game_id, user_id=user.id
    ).first()
    
    if not participant:
        await update.message.reply_text(f"You didn't participate in Game #{game_id}.")
        return
    
    # Send the animation
    await send_game_animation(update.message.chat_id, game_id, context)



@cooldown()
async def simulate_rps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a Rock-Paper-Scissors simulation and send as animation."""
    try:
        await update.message.reply_text("🎮 Creating RPS simulation... This may take a moment.")
        
        # Get custom counts if provided
        rock_count = 33
        paper_count = 35
        scissors_count = 31
        
        if context.args and len(context.args) >= 3:
            try:
                rock_count = max(1, min(50, int(context.args[0])))
                paper_count = max(1, min(50, int(context.args[1])))
                scissors_count = max(1, min(50, int(context.args[2])))
            except ValueError:
                await update.message.reply_text("Invalid arguments! Using default values instead.")
        
        # Send typing action while processing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")
        
        # Run the simulation
        gif_path, winner, stats = create_rps_simulation(rock_count, paper_count, scissors_count)
        
        # Create caption
        caption = (f"🎮 *Rock-Paper-Scissors Simulation*\n\n"
                 f"Starting: Rock: {rock_count}, Paper: {paper_count}, Scissors: {scissors_count}\n"
                 f"Final: Rock: {stats[0]}, Paper: {stats[1]}, Scissors: {stats[2]}\n\n")
        
        if winner == "rock":
            caption += "🪨 *Rock wins!* Rock crushes scissors!"
        elif winner == "paper":
            caption += "📄 *Paper wins!* Paper covers rock!"
        elif winner == "scissors":
            caption += "✂️ *Scissors win!* Scissors cut paper!"
        else:
            caption += "🤝 *It's a draw!* No clear winner."
        
        # Send the animation
        with open(gif_path, 'rb') as animation:
            await context.bot.send_animation(
                chat_id=update.effective_chat.id,
                animation=animation,
                caption=caption,
                parse_mode='Markdown'
            )
        
        # Clean up
        if os.path.exists(gif_path):
            os.remove(gif_path)
            
    except Exception as e:
        LOGGER.error(f"Error in RPS simulation: {e}")
        await update.message.reply_text("Sorry, there was an error creating the simulation. Please try again later.")

async def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        LOGGER.error("No BOT_TOKEN provided. Please set the BOT_TOKEN environment variable.")
        return
    
    try:
        # Initialize the application with explicit error handling
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Register ALL command handlers correctly
        LOGGER.info("Registering command handlers...")
        
        # Basic commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about))
        
        # Account commands
        application.add_handler(CommandHandler("create_account", create_account))
    # Also support misspelled version
    application.add_handler(CommandHandler("creat_account", create_account))
        application.add_handler(CommandHandler("delete_account", delete_account))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("deposit", deposit))
        application.add_handler(CommandHandler("withdraw", withdraw))
        application.add_handler(CommandHandler("history", history))
        
        # Game commands
        application.add_handler(CommandHandler("join_game", join_game))
        application.add_handler(CommandHandler("game_status", game_status))
        
        # Stats commands
        application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("simulate", simulate_rps))
        application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("replay", replay_game))
        
        # Admin commands
        application.add_handler(CommandHandler("admin_stats", admin_stats))
        application.add_handler(CommandHandler("admin_users", admin_users))
        application.add_handler(CommandHandler("admin_games", admin_games))
        application.add_handler(CommandHandler("admin_withdrawals", admin_withdrawals))
        
        # Debug commands
        application.add_handler(CommandHandler("whoami", whoami))
        
        # Add callback query handler for buttons
        application.add_handler(CallbackQueryHandler(button_callback))
    # Add debug command
    application.add_handler(CommandHandler("debug", debug_command))
        
        # Add a message handler to provide help for unknown commands
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Add menu button handler
    application.add_handler(MessageHandler(filters.Regex("^(💰 Account|🎮 Game|📊 Stats|ℹ️ Help)$"), handle_menu_button))
        
        LOGGER.info("All command handlers registered successfully")
        
        # Start the bot with proper polling
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        LOGGER.error(f"Error in bot startup: {e}")
        LOGGER.exception("Full traceback:")


if __name__ == "__main__":
    asyncio.run(main())
