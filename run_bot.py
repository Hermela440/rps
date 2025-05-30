"""Telegram bot for Rock Paper Scissors game"""
import os
import logging
import random
import string
from datetime import datetime, timedelta
import pytz
import asyncio
import json
from typing import Optional, Dict, Any
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

from app import create_app, init_db
from extensions import db
from models import User, Room, RoomPlayer, Transaction

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
LOGGER = logging.getLogger(__name__)

# Initialize UTC timezone
UTC = pytz.UTC

# Create Flask app and push context
app = create_app()
app.app_context().push()

# Initialize database
try:
    init_db(app)
    LOGGER.info("Database initialized successfully")
except Exception as e:
    LOGGER.error(f"Failed to initialize database: {e}")
    raise

# Game states
WAITING_FOR_MOVE = 1

# Define conversation states
REGISTER_NAME, REGISTER_EMAIL, REGISTER_USERNAME, REGISTER_CONFIRM = range(4)

# Configuration
class Config:
    BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///rps_game.db')
    ADMIN_IDS = json.loads(os.environ.get('ADMIN_IDS', '[]'))
    MAINTENANCE_MODE = os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'
    
    # Payment Configuration
    MIN_DEPOSIT = 10  # Minimum deposit amount in ETB
    MAX_DEPOSIT = 1000  # Maximum deposit amount in ETB
    
    # Bank Account Details
    BANK_NAME = os.environ.get('BANK_NAME', "Commercial Bank of Ethiopia")
    ACCOUNT_NUMBER = os.environ.get('ACCOUNT_NUMBER', "1000123456789")
    ACCOUNT_NAME = os.environ.get('ACCOUNT_NAME', "RPS Game")
    BRANCH = os.environ.get('BRANCH', "Addis Ababa")

    @classmethod
    def validate(cls):
        """Validate configuration"""
        if cls.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            LOGGER.warning("Using default BOT_TOKEN. Please set BOT_TOKEN environment variable.")
        if not cls.ADMIN_IDS:
            LOGGER.warning("No ADMIN_IDS configured. Admin features will be disabled.")

def generate_room_code():
    """Generate a unique 5-character room code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not Room.query.filter_by(room_code=code).first():
            return code

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the registration process"""
    if Config.MAINTENANCE_MODE:
        await update.message.reply_text(
            "🛠️ Oops! Our game servers are taking a quick nap! 😴\n"
            "We'll be back before you can say 'Rock Paper Scissors'! 🎮"
        )
        return ConversationHandler.END

    user = update.effective_user

    # Check if user exists
    db_user = User.query.filter_by(telegram_id=user.id).first()
    if db_user:
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data='deposit'),
                InlineKeyboardButton("🎮 Create Room", callback_data='create_room')
            ],
            [
                InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard'),
                InlineKeyboardButton("❓ Help", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎮 Hey {user.first_name}! Ready to rock (paper scissors) again? 🚀\n\n"
            f"💰 Your current balance: ETB {db_user.balance:.2f}\n\n"
            "What's your next move? 🎯",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # New user registration
    await update.message.reply_text(
        f"🎮 Welcome to the coolest Rock Paper Scissors game in town, {user.first_name}! 🎲\n\n"
        f"🌟 *What's in it for you?*\n"
        f"• Create or join game rooms with friends 🎯\n"
        f"• Place bets and compete in Rock-Paper-Scissors 🎮\n"
        f"• Win real money and become a legend! 👑\n"
        f"• Climb the leaderboard and show off your skills! 📊\n\n"
        f"Let's set up your account and get you started on your winning streak! 💫\n\n"
        f"First things first - what's your full name? 👤",
        parse_mode=ParseMode.MARKDOWN
    )
    return REGISTER_NAME

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle name input"""
    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        "✨ Great name! Now, let's get your email address so we can keep you updated on your winnings! 📧"
    )
    return REGISTER_EMAIL

async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email input"""
    email = update.message.text.lower()
    
    # Validate email format
    if not '@' in email or not '.' in email:
        await update.message.reply_text(
            "❌ Oops! That email looks a bit wonky! 🤔\n"
            "Please enter a valid email address (like: player@example.com):"
        )
        return REGISTER_EMAIL

    # Check if email exists
    if User.query.filter_by(email=email).first():
        await update.message.reply_text(
            "❌ Looks like someone's already using this email! 🕵️‍♂️\n"
            "Please use a different email address:"
        )
        return REGISTER_EMAIL
    
    context.user_data['email'] = email
    await update.message.reply_text(
        "🎮 Now, choose your gaming username!\n"
        "You can use letters, numbers, and underscores.\n"
        "Make it cool - this is how other players will know you! 🦸‍♂️"
    )
    return REGISTER_USERNAME

async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle username input"""
    username = update.message.text
    
    # Validate username format
    if not username.replace('_', '').isalnum():
        await update.message.reply_text(
            "❌ Oops! That username has some special characters we don't allow! 🚫\n"
            "Please use only letters, numbers, and underscores:"
        )
        return REGISTER_USERNAME
    
    # Check if username exists
    if User.query.filter_by(username=username).first():
        await update.message.reply_text(
            "❌ That username is already taken! 🎯\n"
            "Time to get creative - try another one:"
        )
        return REGISTER_USERNAME
    
    context.user_data['username'] = username
    
    # Show confirmation with improved button layout
    keyboard = [
        [
            InlineKeyboardButton("✅ Let's Play!", callback_data='confirm_registration'),
            InlineKeyboardButton("🔄 Start Over", callback_data='restart_registration')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎮 *Your Gaming Profile* 🎮\n\n"
        f"👤 Name: {context.user_data['name']}\n"
        f"📧 Email: {context.user_data['email']}\n"
        f"👾 Username: {context.user_data['username']}\n\n"
        f"Everything look good? Ready to start your winning streak? 🚀\n\n"
        f"Click '✅ Let's Play!' to create your account!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return REGISTER_CONFIRM

async def register_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle registration confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'confirm_registration':
        try:
            # Create new user
            user = User(
                telegram_id=update.effective_user.id,
                username=context.user_data['username'],
                email=context.user_data['email'],
                full_name=context.user_data['name'],
                balance=0.0,
                created_at=datetime.utcnow()
            )
            db.session.add(user)
            db.session.commit()
            LOGGER.info(f"Created new user with ID: {user.id}")

            # Clear user data after successful registration
            context.user_data.clear()

            # Show welcome message with menu
            keyboard = [
                [
                    InlineKeyboardButton("💰 Deposit", callback_data='deposit'),
                    InlineKeyboardButton("🎮 Create Room", callback_data='create_room')
                ],
                [
                    InlineKeyboardButton("📖 How to Play", callback_data='help'),
                    InlineKeyboardButton("📋 Menu", callback_data='menu')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🎮 *Welcome to Rock Paper Scissors!* 🎮\n\n"
                "✅ *Account Created Successfully!*\n\n"
                "*What's Next?*\n"
                "1️⃣ Add funds to your wallet\n"
                "2️⃣ Create or join a room\n"
                "3️⃣ Choose your moves\n"
                "4️⃣ Win and collect! 🏆\n\n"
                "Use the buttons below to get started! 🚀",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
            
        except Exception as e:
            LOGGER.error(f"Error creating user: {str(e)}", exc_info=True)
            db.session.rollback()
            await query.edit_message_text(
                "❌ Oops! Something went wrong while creating your account.\n"
                "Please try again later or contact support."
            )
            return ConversationHandler.END
    else:
        # Handle restart registration
        context.user_data.clear()  # Clear user data when restarting
        await query.edit_message_text(
            "🔄 Let's start over! Please enter your full name:"
        )
        return REGISTER_NAME

async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new game room"""
    try:
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Generate room code
        room_code = generate_room_code()
        
        # Create room
        room = Room(
            room_code=room_code,
            creator_id=user.id,
            status='waiting',
            created_at=datetime.utcnow()
        )
        db.session.add(room)
        
        # Add creator as first player
        player = RoomPlayer(
            room_id=room.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(player)
        db.session.commit()

        # Show room status
        keyboard = [
            [
                InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room_code}'),
                InlineKeyboardButton("❌ Cancel Room", callback_data=f'cancel_room_{room_code}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎮 *Room Created Successfully!*\n\n"
            f"Room Code: `{room_code}`\n"
            f"Players: 1/3\n\n"
            f"📢 Share this code with friends to join!\n"
            f"They can join using: `/join_game {room_code}`\n\n"
            f"⏳ Waiting for 2 more players to start...",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        LOGGER.error(f"Error creating room: {e}")
        await update.message.reply_text(
            "Sorry, there was an error creating the room. Please try again later."
        )

async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join an existing game room"""
    try:
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Get room code
        if not context.args:
            await update.message.reply_text(
                "Please specify the room code:\n"
                "/join_game <code>"
            )
            return

        room_code = context.args[0].upper()
        room = Room.query.filter_by(room_code=room_code).first()
        
        if not room:
            await update.message.reply_text("Room not found! Please check the code and try again.")
            return
        
        if room.status != 'waiting':
            await update.message.reply_text("This room is no longer accepting players.")
            return
        
        if len(room.players) >= 3:
            await update.message.reply_text("This room is full!")
            return

        # Add player to room
        player = RoomPlayer(
            room_id=room.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(player)
        db.session.commit()

        # Show join confirmation
        keyboard = [
            [
                InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room_code}'),
                InlineKeyboardButton("❌ Leave Room", callback_data=f'leave_room_{room_code}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎮 *Joined Room {room.room_code}!*\n\n"
            f"Players: {len(room.players)}/3\n\n"
            f"Waiting for more players...",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        LOGGER.error(f"Error joining room: {e}")
        await update.message.reply_text(
            "Sorry, there was an error joining the room. Please try again later."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message"""
    help_text = (
        "🎮 *Rock Paper Scissors Game Guide* 🎮\n\n"
        "*Basic Commands:*\n"
        "• /start - Begin your gaming adventure\n"
        "• /help - Show this awesome guide\n"
        "• /balance - Check your winning stash\n"
        "• /deposit - Add funds to your account\n\n"
        "*Game Commands:*\n"
        "• Create Room - Start a new game room\n"
        "• Join Room - Enter a friend's room\n"
        "• Make Move - Choose Rock, Paper, or Scissors\n\n"
        "*Pro Tips:* 💡\n"
        "• Start with small bets to learn the ropes\n"
        "• Watch out for patterns in your opponent's moves\n"
        "• Don't forget to withdraw your winnings!\n\n"
        "Need more help? Just ask! We're here to make you a champion! 🏆"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Use /start to begin again."
    )
    return ConversationHandler.END

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check user balance"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return
            
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data='deposit'),
                InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 *Your Balance*\n\n"
            f"Current Balance: ETB {user.balance:.2f}\n\n"
            "What would you like to do?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        LOGGER.error(f"Error checking balance: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred while checking your balance.\n"
            "Please try again later or contact support."
        )

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the deposit command"""
    try:
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return

        # Show simple deposit options
        keyboard = [
            [
                InlineKeyboardButton("💰 100 ETB", callback_data='quick_deposit_100'),
                InlineKeyboardButton("💰 500 ETB", callback_data='quick_deposit_500')
            ],
            [
                InlineKeyboardButton("💰 1000 ETB", callback_data='quick_deposit_1000'),
                InlineKeyboardButton("💰 2000 ETB", callback_data='quick_deposit_2000')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💰 *Quick Deposit*\n\n"
            "Select amount to deposit:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    except Exception as e:
        LOGGER.error(f"Error in deposit command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred. Please try again later or contact support."
        )

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment verification"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract transaction reference from callback data
        tx_ref = query.data.split('_')[1]
        
        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            await query.edit_message_text("❌ Transaction not found. Please contact support.")
            return
            
        # Update transaction status
        transaction.status = "completed"
        transaction.completed_at = datetime.utcnow()
        
        # Update user balance
        user = User.query.get(transaction.user_id)
        user.balance += transaction.amount
        
        db.session.commit()
        
        # Show success message
        keyboard = [
            [
                InlineKeyboardButton("🎮 Play Game", callback_data='create_room'),
                InlineKeyboardButton("💰 Deposit More", callback_data='deposit')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *Payment Successful!*\n\n"
            f"Amount: ETB {transaction.amount:.2f}\n"
            f"Balance: ETB {user.balance:.2f}\n\n"
            "What would you like to do?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
            
    except Exception as e:
        LOGGER.error(f"Error verifying payment: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ Error verifying payment. Please contact support."
        )

async def handle_quick_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quick deposit button callbacks"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract amount from callback data
        amount = float(query.data.split('_')[2])
        
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await query.edit_message_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return

        # Generate transaction reference
        tx_ref = f"DEP_{user.id}_{int(datetime.utcnow().timestamp())}"
        
        # Create pending transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type='deposit',
            status='pending',
            tx_ref=tx_ref,
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()

        # Show simple payment instructions
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Payment", callback_data=f"verify_{tx_ref}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{tx_ref}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💰 *Deposit ETB {amount:.2f}*\n\n"
            f"🏦 Bank: {Config.BANK_NAME}\n"
            f"📝 Account: {Config.ACCOUNT_NAME}\n"
            f"🔢 Number: `{Config.ACCOUNT_NUMBER}`\n"
            f"🏢 Branch: {Config.BRANCH}\n\n"
            f"Reference: `{tx_ref}`\n\n"
            f"Click 'Confirm Payment' after transfer",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    except Exception as e:
        LOGGER.error(f"Error in quick deposit: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle deposit cancellation"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract transaction reference from callback data
        tx_ref = query.data.split('_')[1]
        
        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if transaction and transaction.status == 'pending':
            transaction.status = 'cancelled'
            db.session.commit()
            
        # Show simple menu
        keyboard = [
            [
                InlineKeyboardButton("💰 Try Again", callback_data='deposit'),
                InlineKeyboardButton("🎮 Play Game", callback_data='create_room')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ Deposit cancelled.\n\n"
            "What would you like to do?",
            reply_markup=reply_markup
        )
            
    except Exception as e:
        LOGGER.error(f"Error cancelling deposit: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ Error cancelling deposit. Please contact support."
        )

async def show_game_animation(update: Update, context: ContextTypes.DEFAULT_TYPE, room: Room) -> None:
    """Show animated game results"""
    try:
        # Get all players and their moves
        players = RoomPlayer.query.filter_by(room_id=room.id).all()
        moves = {}
        for player in players:
            moves[player.user_id] = player.move

        # Create animation frames
        frames = [
            "🎮 Game in progress...",
            "🎮 Game in progress... 🎲",
            "🎮 Game in progress... 🎲 🎯",
            "🎮 Game in progress... 🎲 🎯 🎪",
            "🎮 Game in progress... 🎲 🎯 🎪 🎨",
            "🎮 Game in progress... 🎲 🎯 🎪 🎨 🎭"
        ]

        # Send initial message
        message = await update.callback_query.edit_message_text(
            "🎮 *Game Results*\n\n"
            "Calculating results...",
            parse_mode='Markdown'
        )

        # Show animation
        for frame in frames:
            await message.edit_text(
                f"🎮 *Game Results*\n\n{frame}",
                parse_mode='Markdown'
            )
            await asyncio.sleep(0.5)

        # Calculate results
        results = calculate_game_results(moves)
        
        # Show results with animation
        result_text = "🎮 *Game Results*\n\n"
        for player_id, move in moves.items():
            user = User.query.get(player_id)
            result_text += f"👤 {user.username}: {get_move_emoji(move)}\n"
        
        result_text += "\n"
        for player_id, result in results.items():
            user = User.query.get(player_id)
            if result == "win":
                result_text += f"🏆 {user.username} wins!\n"
            elif result == "lose":
                result_text += f"😢 {user.username} loses\n"
            else:
                result_text += f"🤝 {user.username} draws\n"

        # Show results with celebration animation
        celebrations = ["🎉", "🎊", "🎈", "🎆", "🎇", "✨"]
        for emoji in celebrations:
            await message.edit_text(
                f"{result_text}\n{emoji}",
                parse_mode='Markdown'
            )
            await asyncio.sleep(0.3)

        # Final result message
        await message.edit_text(
            f"{result_text}\n\n"
            "Game completed! 🎮\n"
            "Use /create_room to start a new game!",
            parse_mode='Markdown'
        )

    except Exception as e:
        LOGGER.error(f"Error showing game animation: {str(e)}", exc_info=True)
        await update.callback_query.edit_message_text(
            "❌ Error showing game results. Please try again."
        )

def get_move_emoji(move: str) -> str:
    """Get emoji for player's move"""
    moves = {
        "rock": "🪨",
        "paper": "📄",
        "scissors": "✂️"
    }
    return moves.get(move.lower(), "❓")

def calculate_game_results(moves: Dict[int, str]) -> Dict[int, str]:
    """Calculate game results for all players"""
    results = {}
    move_list = list(moves.values())
    
    # If all moves are the same, it's a draw
    if len(set(move_list)) == 1:
        return {player_id: "draw" for player_id in moves.keys()}
    
    # Check each player's result
    for player_id, move in moves.items():
        wins = 0
        for other_move in move_list:
            if move != other_move:
                if (move == "rock" and other_move == "scissors") or \
                   (move == "paper" and other_move == "rock") or \
                   (move == "scissors" and other_move == "paper"):
                    wins += 1
        
        # Player wins if they beat at least one other player
        results[player_id] = "win" if wins > 0 else "lose"
    
    return results

async def make_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle player's move"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract room code and move from callback data
        data = query.data.split('_')
        room_code = data[1]
        move = data[2]
        
        # Get room and player
        room = Room.query.filter_by(room_code=room_code).first()
        if not room:
            await query.edit_message_text("❌ Room not found!")
            return
            
        player = RoomPlayer.query.filter_by(
            room_id=room.id,
            user_id=update.effective_user.id
        ).first()
        
        if not player:
            await query.edit_message_text("❌ You are not in this room!")
            return
            
        # Record player's move
        player.move = move
        db.session.commit()
        
        # Check if all players have made their moves
        all_moved = all(p.move for p in room.players)
        
        if all_moved:
            # Show game animation and results
            await show_game_animation(update, context, room)
            
            # Reset room for next game
            for p in room.players:
                p.move = None
            db.session.commit()
        else:
            # Show waiting message
            await query.edit_message_text(
                f"✅ You selected {get_move_emoji(move)}\n\n"
                "Waiting for other players...",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        LOGGER.error(f"Error processing move: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ Error processing your move. Please try again."
        )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu with all commands and their steps"""
    menu_text = (
        "🎮 *RPS Game Menu* 🎮\n\n"
        "*🎯 Account Commands:*\n"
        "• /start - Begin your adventure\n"
        "• /help - Show this awesome guide\n"
        "• /balance - Check your wallet\n"
        "• /deposit - Add funds\n\n"
        "*🎲 Game Commands:*\n"
        "• Create Room - Start a new game\n"
        "• Join Room - Play with friends\n"
        "• Make Move - Play your turn\n\n"
        "*📱 Other Commands:*\n"
        "• /help - Show game guide\n"
        "• /menu - Show this menu\n"
        "• /cancel - Cancel current action\n\n"
        "*💡 Quick Tips:*\n"
        "• Start with small bets\n"
        "• Watch for patterns\n"
        "• Have fun! 🎉\n\n"
        "Need help? Just ask! 😊"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🎮 Create Room", callback_data='create_room'),
            InlineKeyboardButton("💰 Deposit", callback_data='deposit')
        ],
        [
            InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard'),
            InlineKeyboardButton("❓ Help", callback_data='help')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        menu_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle deposit button callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await query.edit_message_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return

        # Show simple deposit options
        keyboard = [
            [
                InlineKeyboardButton("💰 100 ETB", callback_data='quick_deposit_100'),
                InlineKeyboardButton("💰 500 ETB", callback_data='quick_deposit_500')
            ],
            [
                InlineKeyboardButton("💰 1000 ETB", callback_data='quick_deposit_1000'),
                InlineKeyboardButton("💰 2000 ETB", callback_data='quick_deposit_2000')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💰 *Quick Deposit*\n\n"
            "Select amount to deposit:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        LOGGER.error(f"Error in deposit callback: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

async def handle_create_room_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle create room button callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await query.edit_message_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return

        # Create new room
        room_code = generate_room_code()
        room = Room(
            room_code=room_code,
            creator_id=user.id,
            status='waiting',
            created_at=datetime.utcnow()
        )
        db.session.add(room)
        
        # Add creator as first player
        player = RoomPlayer(
            room_id=room.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(player)
        db.session.commit()

        keyboard = [
            [
                InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room_code}'),
                InlineKeyboardButton("❌ Cancel Room", callback_data=f'cancel_room_{room_code}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎮 *Room Created Successfully!*\n\n"
            f"Room Code: `{room_code}`\n"
            f"Players: 1/3\n\n"
            f"📢 Share this code with friends to join!\n"
            f"They can join using: `/join_game {room_code}`\n\n"
            f"⏳ Waiting for 2 more players to start...",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Error in create room callback: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle help button callback"""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "🎮 *Rock Paper Scissors Game Guide* 🎮\n\n"
        "*Basic Commands:*\n"
        "• /start - Begin your gaming adventure\n"
        "• /help - Show this awesome guide\n"
        "• /balance - Check your winning stash\n"
        "• /deposit - Add funds to your account\n\n"
        "*Game Commands:*\n"
        "• Create Room - Start a new game room\n"
        "• Join Room - Enter a friend's room\n"
        "• Make Move - Choose Rock, Paper, or Scissors\n\n"
        "*Pro Tips:* 💡\n"
        "• Start with small bets to learn the ropes\n"
        "• Watch out for patterns in your opponent's moves\n"
        "• Don't forget to withdraw your winnings!\n\n"
        "Need more help? Just ask! We're here to make you a champion! 🏆"
    )
    await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu button callback"""
    query = update.callback_query
    await query.answer()
    
    menu_text = (
        "🎮 *RPS Game Menu* 🎮\n\n"
        "*🎯 Account Commands:*\n"
        "• /start - Begin your adventure\n"
        "• /balance - Check your wallet\n"
        "• /deposit - Add funds\n\n"
        "*🎲 Game Commands:*\n"
        "• Create Room - Start a new game\n"
        "• Join Room - Play with friends\n"
        "• Make Move - Play your turn\n\n"
        "*📱 Other Commands:*\n"
        "• /help - Show game guide\n"
        "• /menu - Show this menu\n"
        "• /cancel - Cancel current action\n\n"
        "*💡 Quick Tips:*\n"
        "• Start with small bets\n"
        "• Watch for patterns\n"
        "• Have fun! 🎉\n\n"
        "Need help? Just ask! 😊"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🎮 Create Room", callback_data='create_room'),
            InlineKeyboardButton("💰 Deposit", callback_data='deposit')
        ],
        [
            InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard'),
            InlineKeyboardButton("❓ Help", callback_data='help')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        menu_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_share_room_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle share room button callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        room_code = query.data.split('_')[2]
        await query.edit_message_text(
            f"🎮 *Share Room Code*\n\n"
            f"Room Code: `{room_code}`\n\n"
            f"Share this code with friends to join your game!\n"
            f"They can join using: `/join_game {room_code}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Error in share room callback: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

async def handle_cancel_room_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel room button callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        room_code = query.data.split('_')[2]
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        
        if not user:
            await query.edit_message_text(
                "❌ You need to create an account first!\n"
                "Use /start to begin registration."
            )
            return
            
        room = Room.query.filter_by(room_code=room_code).first()
        if room and room.creator_id == user.id:
            db.session.delete(room)
            db.session.commit()
            await query.edit_message_text("✅ Room cancelled successfully!")
        else:
            await query.edit_message_text("❌ You can't cancel this room!")
    except Exception as e:
        LOGGER.error(f"Error in cancel room callback: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

async def handle_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle leaderboard button callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        top_players = User.query.order_by(User.balance.desc()).limit(10).all()
        leaderboard_text = "🏆 *Top Players* 🏆\n\n"
        for i, player in enumerate(top_players, 1):
            leaderboard_text += f"{i}. {player.username}: ETB {player.balance:.2f}\n"
        await query.edit_message_text(leaderboard_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.error(f"Error in leaderboard callback: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred. Please try again later."
        )

def main():
    """Start the bot"""
    # Validate configuration
    Config.validate()
    
    # Create the Application
    application = Application.builder().token(Config.BOT_TOKEN).build()

    # Add conversation handler for registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
            REGISTER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_username)],
            REGISTER_CONFIRM: [CallbackQueryHandler(register_confirm, pattern='^confirm_|restart_')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(conv_handler)

    # Add command handlers
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('balance', balance))
    application.add_handler(CommandHandler('deposit', deposit))
    application.add_handler(CommandHandler('menu', menu))

    # Add callback query handlers
    application.add_handler(CallbackQueryHandler(handle_deposit_callback, pattern='^deposit$'))
    application.add_handler(CallbackQueryHandler(handle_create_room_callback, pattern='^create_room$'))
    application.add_handler(CallbackQueryHandler(handle_help_callback, pattern='^help$'))
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern='^menu$'))
    application.add_handler(CallbackQueryHandler(handle_share_room_callback, pattern='^share_room_'))
    application.add_handler(CallbackQueryHandler(handle_cancel_room_callback, pattern='^cancel_room_'))
    application.add_handler(CallbackQueryHandler(handle_leaderboard_callback, pattern='^leaderboard$'))
    application.add_handler(CallbackQueryHandler(handle_quick_deposit, pattern='^quick_deposit_'))
    application.add_handler(CallbackQueryHandler(verify_payment, pattern='^verify_'))
    application.add_handler(CallbackQueryHandler(cancel_deposit, pattern='^cancel_'))

    # Start the Bot
    LOGGER.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
