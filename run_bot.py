"""Telegram bot for Rock Paper Scissors game"""
import os
import logging
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from datetime import datetime
import pytz
from app import create_app, init_db
from extensions import db
from models import User, Room, RoomPlayer, Transaction
import re
import asyncio
import telegram

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

# Initialize UTC timezone
UTC = pytz.UTC

# Create Flask app and push context
app = create_app()
app.app_context().push()

# Initialize database
try:
    init_db()
    LOGGER.info("Database initialized successfully")
except Exception as e:
    LOGGER.error(f"Failed to initialize database: {e}")
    raise

# Game states
WAITING_FOR_MOVE = 1

def generate_room_code():
    """Generate a unique 5-character room code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not Room.query.filter_by(room_code=code).first():
            return code

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    try:
        user = update.effective_user
        
        # Check if user exists in database
        db_user = User.query.filter_by(telegram_id=user.id).first()
        
        if db_user:
            # User exists, show welcome back message
            keyboard = [
                [
                    InlineKeyboardButton("🎮 Create Room", callback_data='create_room'),
                    InlineKeyboardButton("🔍 Join Room", callback_data='join_room')
                ],
                [
                    InlineKeyboardButton("💰 Balance", callback_data='balance'),
                    InlineKeyboardButton("📊 Stats", callback_data='stats')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Welcome back {user.first_name}! 🎮\n\n"
                f"Your current balance: {db_user.balance:.2f} ETB\n\n"
                "What would you like to do?",
                reply_markup=reply_markup
            )
        else:
            # Create new user account
            try:
                new_user = User(
                    telegram_id=user.id,
                    username=user.username or f"player_{user.id}",
                    balance=0.0,
                    wins=0,
                    losses=0,
                    created_at=datetime.utcnow()
                )
                db.session.add(new_user)
                db.session.commit()
                
                # Show welcome message for new users
                keyboard = [
                    [
                        InlineKeyboardButton("💰 Add Funds", callback_data='deposit'),
                        InlineKeyboardButton("🎮 Create Room", callback_data='create_room')
                    ],
                    [
                        InlineKeyboardButton("📖 How to Play", callback_data='help'),
                        InlineKeyboardButton("📊 Rules", callback_data='rules')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    f"Welcome {user.first_name} to Rock Paper Scissors! 🎮\n\n"
                    "Your account has been created successfully! 🎉\n\n"
                    "🎲 *How to Play:*\n"
                    "1. Add funds to your wallet\n"
                    "2. Create or join a room\n"
                    "3. Choose rock, paper, or scissors\n"
                    "4. Win and collect your prize!\n\n"
                    "💰 *Betting Limits:*\n"
                    "• Minimum bet: 10 ETB\n"
                    "• Maximum bet: 1000 ETB\n"
                    "• Winner takes 95% of the pot!\n\n"
                    "Get started by adding funds to your wallet!",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )

            except Exception as db_error:
                LOGGER.error(f"Error creating user account: {db_error}")
                await update.message.reply_text(
                    "Sorry, there was an error creating your account. Please try again later or contact support."
                )

    except Exception as e:
        LOGGER.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later or contact support."
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's balance"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return
        
        await update.message.reply_text(
            f"💰 *Your Balance*\n"
            f"Current Balance: ETB {user.balance:.2f}\n\n"
            f"What would you like to do?\n"
            f"➕ /deposit   ➖ /withdraw",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Error in balance command: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

def get_room_status_text(room: Room) -> str:
    return (
        f"🧩 Room Code: {room.room_code}\n\n"
        f"Bet Amount: ETB {room.bet_amount:.2f}\n"
        f"Players: {room.players.count()}/3\n\n"
        f"Waiting for {3 - room.players.count()} more player(s) to start...\n\n"
        f"👇 What would you like to do?"
    )

async def update_room_message(context, room: Room):
    """Update the room status message for all players"""
    if room.message_id and room.chat_id:
        try:
            await context.bot.edit_message_text(
                chat_id=room.chat_id,
                message_id=room.message_id,
                text=get_room_status_text(room),
                reply_markup=game_waiting_buttons(room.room_code)
            )
        except Exception as e:
            LOGGER.warning(f"Could not update room message: {e}")

async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new game room with specified bet amount"""
    try:
        # 1. Parse and validate bet amount
        bet_amount = None
        if context.args and len(context.args) > 0:
            try:
                bet_amount = float(context.args[0])
            except ValueError:
                bet_amount = None
        else:
            # Try to parse from the command itself (e.g., /create_room100)
            match = re.match(r"/create_room(\d+)", update.message.text)
            if match:
                bet_amount = float(match.group(1))

        if bet_amount is None:
            await update.message.reply_text(
                "Please specify the bet amount:\n"
                "/create_room <amount> (e.g., /create_room 100)"
            )
            return

        # 2. Validate bet amount limits
        if bet_amount < 10:
            await update.message.reply_text("Minimum bet amount is 10 ETB")
            return
        if bet_amount > 1000:
            await update.message.reply_text("Maximum bet amount is 1000 ETB")
            return

        # 3. Get and validate user
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # 4. Check if user is already in a room
        active_room = RoomPlayer.query.join(Room).filter(
            RoomPlayer.user_id == user.id,
            Room.status.in_(['waiting', 'in_progress'])
        ).first()
        
        if active_room:
            await update.message.reply_text(
                f"⚠️ You are already in room `{active_room.room.room_code}`.\n"
                f"Use /leave_room to leave first.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # 5. Check user balance
        if user.balance < bet_amount:
            await update.message.reply_text(
                f"❌ Insufficient balance! You need ETB {bet_amount:.2f} to create a room.\n"
                f"Your balance: ETB {user.balance:.2f}"
            )
            return

        # 6. Generate unique room code
        max_attempts = 5
        room_code = None
        for _ in range(max_attempts):
            temp_code = generate_room_code()
            if not Room.query.filter_by(room_code=temp_code).first():
                room_code = temp_code
                break
        
        if not room_code:
            await update.message.reply_text(
                "Sorry, couldn't generate a unique room code. Please try again."
            )
            return

        # 7. Create room and add player in a transaction
        try:
            # Create new room
            room = Room(
                room_code=room_code,
                bet_amount=bet_amount,
                creator_id=user.id,
                status='waiting',
                created_at=datetime.utcnow()
            )
            db.session.add(room)
            db.session.flush()  # Get room.id without committing

            # Add creator as first player
            player = RoomPlayer(
                room_id=room.id,
                user_id=user.id,
                joined_at=datetime.utcnow()
            )
            db.session.add(player)

            # Create bet transaction
            transaction = Transaction(
                user_id=user.id,
                amount=-bet_amount,
                type='bet',
                status='completed',
                reference_id=f"BET-{room_code}-{user.id}"
            )
            db.session.add(transaction)

            # Deduct bet amount from user balance
            user.balance -= bet_amount

            # Commit all changes
            db.session.commit()

            # 8. Send room status message with retry logic
            max_retries = 3
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries):
                try:
                    message = await update.message.reply_text(
                        get_room_status_text(room),
                        reply_markup=game_waiting_buttons(room.room_code),
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=30,
                        pool_timeout=30
                    )
                    
                    # Save message info
                    room.message_id = message.message_id
                    room.chat_id = message.chat_id
                    db.session.commit()
                    break
                except telegram.error.TimedOut:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                except Exception as e:
                    LOGGER.error(f"Error sending room status message: {e}")
                    raise

            # 9. Send confirmation with share buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room_code}'),
                    InlineKeyboardButton("❌ Cancel Room", callback_data=f'cancel_room_{room_code}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await update.message.reply_text(
                    f"🎮 *Room Created Successfully!*\n\n"
                    f"Room Code: `{room_code}`\n"
                    f"Bet Amount: ETB {bet_amount:.2f}\n"
                    f"Players: 1/3\n\n"
                    f"Share this code with friends to join!\n"
                    f"Use /join_game {room_code} {bet_amount:.0f} to join.",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
            except telegram.error.TimedOut:
                # If confirmation message fails, at least the room was created
                LOGGER.warning("Timeout sending confirmation message, but room was created successfully")
                await update.message.reply_text(
                    f"Room created with code: {room_code}\n"
                    f"Bet amount: ETB {bet_amount:.2f}\n"
                    f"Players: 1/3",
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )

        except Exception as db_error:
            db.session.rollback()
            LOGGER.error(f"Database error creating room: {db_error}")
            await update.message.reply_text(
                "Sorry, there was an error creating the room. Please try again later.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )

    except Exception as e:
        LOGGER.error(f"Error in create_room command: {e}")
        try:
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
        except Exception as reply_error:
            LOGGER.error(f"Error sending error message: {reply_error}")

async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join an existing game room"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Check if user is already in a room
        active_room = RoomPlayer.query.join(Room).filter(
            RoomPlayer.user_id == user.id,
            Room.status.in_(['waiting', 'in_progress'])
        ).first()

        if active_room:
            await update.message.reply_text(
                f"You're already in Room {active_room.room.room_code}!\n"
                f"Use /leave_room to leave first."
            )
            return

        # Parse room code
        if not context.args:
            await update.message.reply_text(
                "Please specify the room code:\n"
                "/join_room <code>"
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

        # Check user balance
        if user.balance < room.bet_amount:
            await update.message.reply_text(
                f"Insufficient balance! You need ETB {room.bet_amount:.2f} to join.\n"
                f"Your balance: ETB {user.balance:.2f}"
            )
            return

        # Add player to room
        player = RoomPlayer(
            room_id=room.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(player)

        try:
            db.session.commit()

            # Check if room is full (3 players)
            if len(room.players) == 3:
                # Start the game
                await start_game(room.id, context)
            else:
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
                f"Bet Amount: ETB {room.bet_amount:.2f}\n"
                f"Players: {len(room.players)}/3\n\n"
                f"Waiting for more players...",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as db_error:
            db.session.rollback()
            LOGGER.error(f"Database error joining room: {db_error}")
            await update.message.reply_text(
                "Sorry, there was an error joining the room. Please try again later."
            )

    except Exception as e:
        LOGGER.error(f"Error in join_room command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def start_game(room_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a game when the room is full"""
    try:
        room = Room.query.get(room_id)
        if not room or room.status != 'waiting':
            return

        # Update room status
        room.status = 'in_progress'
        room.started_at = datetime.utcnow()
        
        # Delete the waiting room message if it exists
        if room.message_id and room.chat_id:
            try:
                await context.bot.delete_message(chat_id=room.chat_id, message_id=room.message_id)
            except Exception as e:
                LOGGER.warning(f"Could not delete waiting room message: {e}")
        
        # Deduct bet amount from all players
        for player in room.players:
            player.user.balance -= room.bet_amount
            # Create bet transaction
            transaction = Transaction(
                user_id=player.user.id,
                amount=-room.bet_amount,
                type='bet',
                status='completed',
                reference_id=f"BET-{room.room_code}-{player.user.id}"
            )
            db.session.add(transaction)
        
        db.session.commit()

        # Create move keyboard
        keyboard = [
            [
                InlineKeyboardButton("🪨 Rock", callback_data=f"move_rock_{room.room_code}"),
                InlineKeyboardButton("📄 Paper", callback_data=f"move_paper_{room.room_code}"),
                InlineKeyboardButton("✂️ Scissors", callback_data=f"move_scissors_{room.room_code}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Calculate prize pool
        total_pot = room.bet_amount * len(room.players)
        prize_pool = total_pot * 0.95  # 95% of pot goes to winner(s)

        # Notify all players
        for player in room.players:
            try:
                await context.bot.send_message(
                    chat_id=player.user.telegram_id,
                    text=(
                        f"🕹️ *Game Started in Room {room.room_code}*\n\n"
                        f"Bet Amount: ETB {room.bet_amount:.2f}\n"
                        f"Prize Pool: ETB {prize_pool:.2f}\n\n"
                        f"Please choose your move:"
                    ),
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Error notifying player {player.user_id}: {e}")

    except Exception as e:
        LOGGER.error(f"Error starting game: {e}")
        db.session.rollback()

def game_waiting_buttons(room_code: str) -> InlineKeyboardMarkup:
    """Create keyboard for game waiting state"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Share Room", switch_inline_query=room_code)],
        [InlineKeyboardButton("🚪 Leave Room", callback_data=f"leave_room:{room_code}")]
    ])

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join a game room with code and bet amount, with robust validation and share/leave buttons."""
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Usage: /join_game <room_code> <bet_amount>")
            return
        room_code = args[0].upper()
        try:
            bet_amount = float(args[1])
        except ValueError:
            await update.message.reply_text("Bet amount must be a number. Usage: /join_game <room_code> <bet_amount>")
            return

        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first using /start")
            return

        # Check if user is already in a room
        active_room = RoomPlayer.query.join(Room).filter(
            RoomPlayer.user_id == user.id,
            Room.status.in_(['waiting', 'in_progress'])
        ).first()
        if active_room:
            await update.message.reply_text(
                f"⚠️ You are already in room {active_room.room.room_code}.\nUse /leave_room to leave first."
            )
            return

        # Check if room exists
        room = Room.query.filter_by(room_code=room_code).first()
        if not room:
            await update.message.reply_text("Room not found. You can create one using /create_room <amount>")
            return
        if room.status != 'waiting':
            await update.message.reply_text("This room is no longer accepting players.")
            return
        
        # Get current player count
        player_count = RoomPlayer.query.filter_by(room_id=room.id).count()
        if player_count >= 3:
            await update.message.reply_text("This room is full!")
            return
        if bet_amount != room.bet_amount:
            await update.message.reply_text(
                f"This room requires a bet of ETB {room.bet_amount:.2f}. Please use: /join_game {room_code} {room.bet_amount:.0f}"
            )
            return
        if user.balance < bet_amount:
            await update.message.reply_text(
                f"Insufficient balance! You need ETB {bet_amount:.2f} to join.\nYour balance: ETB {user.balance:.2f}"
            )
            return

        # Add player to room
        player = RoomPlayer(
            room_id=room.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(player)
        try:
            db.session.commit()
            
            # Show confirmation with share/leave buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room_code}'),
                    InlineKeyboardButton("❌ Leave Room", callback_data=f'leave_room_{room_code}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Format message exactly as requested
            await update.message.reply_text(
                f"🧩 Joining a game...\n\n"
                f"✅ You've been added to room {room_code}\n"
                f"Bet Amount: ETB {bet_amount:.2f}\n"
                f"Players: {player_count + 1}/3\n\n"
                f"Waiting for {2 - player_count} more player(s) to start.",
                reply_markup=reply_markup
            )

            # Start game if room is full (3 players)
            if player_count + 1 == 3:
                # Create move keyboard
                move_keyboard = [
                    [
                        InlineKeyboardButton("🪨 Rock", callback_data=f"move_rock_{room_code}"),
                        InlineKeyboardButton("📄 Paper", callback_data=f"move_paper_{room_code}"),
                        InlineKeyboardButton("✂️ Scissors", callback_data=f"move_scissors_{room_code}")
                    ]
                ]
                move_reply_markup = InlineKeyboardMarkup(move_keyboard)

                # Notify all players that game is starting
                for room_player in RoomPlayer.query.filter_by(room_id=room.id).all():
                    try:
                        await context.bot.send_message(
                            chat_id=room_player.user.telegram_id,
                            text=f"🎮 Game starting in room {room_code}!\n\n"
                                 f"Bet Amount: ETB {bet_amount:.2f}\n"
                                 f"Prize Pool: ETB {bet_amount * 3 * 0.95:.2f}\n\n"
                                 f"Choose your move:",
                            reply_markup=move_reply_markup
                        )
                    except Exception as e:
                        LOGGER.error(f"Error notifying player {room_player.user_id}: {e}")
                
                # Start the game
                await start_game(room.id, context)

        except Exception as db_error:
            db.session.rollback()
            LOGGER.error(f"Database error joining room: {db_error}")
            if 'UNIQUE constraint failed' in str(db_error):
                await update.message.reply_text(
                    "You are already in this room! If you want to join another, leave this one first."
                )
            else:
                await update.message.reply_text(
                    "Sorry, there was a database error joining the room. Please try again later."
                )
    except Exception as e:
        LOGGER.error(f"Error in join_game command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()

    try:
        if query.data.startswith('leave_room:'):
            room_code = query.data.split(':')[1]
            user = User.query.filter_by(telegram_id=update.effective_user.id).first()
            if not user:
                await query.edit_message_text("User not found!")
                return

            # Find room and player
            room = Room.query.filter_by(room_code=room_code).first()
            if not room:
                await query.edit_message_text("Room not found!")
                return

            player = RoomPlayer.query.filter_by(room_id=room.id, user_id=user.id).first()
            if not player:
                await query.edit_message_text("You're not in this room!")
                return

            # Check if game has started
            if room.status == 'in_progress':
                await query.edit_message_text("Cannot leave a game in progress!")
                return

            # Remove player from room
            db.session.delete(player)
            
            # If room is empty, delete it
            if len(room.players) <= 1:
                db.session.delete(room)
                await query.edit_message_text(
                    "🚪 You have left the room!\n"
                    "The room has been closed since it's empty."
                )
            else:
                # Update remaining players
                remaining_players = room.players.all()
                for remaining_player in remaining_players:
                    try:
                        await context.bot.send_message(
                            chat_id=remaining_player.user.telegram_id,
                            text=f"🧩 Room Update\n\n"
                                 f"Room: {room_code}\n"
                                 f"Bet Amount: ETB {room.bet_amount:.2f}\n"
                                 f"Players: {len(remaining_players)}/3\n\n"
                                 f"Waiting for {3 - len(remaining_players)} more player(s) to start."
                        )
                    except Exception as e:
                        LOGGER.error(f"Error notifying player {remaining_player.user_id}: {e}")

                await query.edit_message_text(
                    "🚪 You have left the room!\n"
                    f"Room {room_code} is still open with {len(remaining_players)} players."
                )

            try:
                db.session.commit()
                
                # Show new game options
                keyboard = [
                    [
                        InlineKeyboardButton("🎮 Create Room", callback_data='create_room'),
                        InlineKeyboardButton("🔍 Join Room", callback_data='join_room')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    "What would you like to do next?",
                    reply_markup=reply_markup
                )

            except Exception as db_error:
                db.session.rollback()
                LOGGER.error(f"Database error leaving room: {db_error}")
                await query.edit_message_text(
                    "Sorry, there was an error leaving the room. Please try again later."
                )

        elif query.data == 'create_room':
            # Redirect to create_room command
            await create_room(update, context)

        elif query.data == 'join_room':
            # Redirect to join_room command
            await join_room(update, context)

        elif query.data.startswith('move_'):
            # Handle player move
            move, room_code = query.data.split('_')[1:]
            await handle_move(update, context, move, room_code)

    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}")
        await query.edit_message_text("An error occurred. Please try again.")

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE, move: str, room_code: str) -> None:
    """Handle a player's move"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.callback_query.edit_message_text("You need to create an account first! Use /start")
            return
        
        # Find player's room
        room = Room.query.filter_by(room_code=room_code).first()
        if not room or room.status != 'in_progress':
            await update.callback_query.edit_message_text("This game is no longer active!")
            return
        
        player = RoomPlayer.query.filter_by(room_id=room.id, user_id=user.id).first()
        if not player:
            await update.callback_query.edit_message_text("You're not in this game!")
            return

        if player.move:
            await update.callback_query.edit_message_text("You've already made your move!")
            return
        
        # Record the move
        player.move = move
        player.move_made_at = datetime.utcnow()
        db.session.commit()

        # Check if all players have moved
        all_moved = all(p.move for p in room.players)
        if all_moved:
            await process_game_result(room.id, context)
        else:
            await update.callback_query.edit_message_text(
                f"Move recorded! ✅\n"
                f"Waiting for other players...\n"
                f"({sum(1 for p in room.players if p.move)}/3 players ready)"
            )

    except Exception as e:
        LOGGER.error(f"Error handling move: {e}")
        await update.callback_query.edit_message_text("An error occurred. Please try again.")

async def process_game_result(room_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the game result and distribute prizes"""
    try:
        room = Room.query.get(room_id)
        if not room or room.status != 'in_progress':
            return

        # Get all moves
        moves = {p.user_id: p.move for p in room.players}
        
        # Calculate wins for each player
        wins = {p.user_id: 0 for p in room.players}
        for p1 in room.players:
            for p2 in room.players:
                if p1.user_id != p2.user_id:
                    if beats(p1.move, p2.move):
                        wins[p1.user_id] += 1

        # Determine winner(s)
        max_wins = max(wins.values())
        winners = [user_id for user_id, win_count in wins.items() if win_count == max_wins]

        # Calculate prize pool
        total_pot = room.bet_amount * len(room.players)
        prize_pool = total_pot * 0.95  # 95% of pot goes to winner(s)
        prize_per_winner = prize_pool / len(winners)
        
        # Update player stats and distribute prizes
        for player in room.players:
            if player.user_id in winners:
                player.user.wins += 1
                player.user.balance += prize_per_winner
                # Create win transaction
                transaction = Transaction(
                    user_id=player.user.id,
                    amount=prize_per_winner,
                    type='win',
                    status='completed',
                    reference_id=f"WIN-{room.room_code}-{player.user.id}"
                )
                db.session.add(transaction)
            else:
                player.user.losses += 1
        
        # Update room status
        room.status = 'completed'
        room.completed_at = datetime.utcnow()
        db.session.commit()

        # Format result message
        result_lines = [
            f"🎉 *Game Over - Room {room.room_code}*\n",
            "\n🧍 *Players:*"
        ]
        
        # Show all players' moves
        for player in room.players:
            result_lines.append(f"• {player.user.username} → {get_move_emoji(moves[player.user_id])}")
        
        result_lines.append("\n🏆 *Results:*")
        if len(winners) == 1:
            winner = room.players.filter_by(user_id=winners[0]).first()
            result_lines.append(f"• {winner.user.username} WON ETB {prize_per_winner:.2f}!")
        else:
            result_lines.append(f"• Draw! Prize split between {len(winners)} players")
            for winner_id in winners:
                winner = room.players.filter_by(user_id=winner_id).first()
                result_lines.append(f"• {winner.user.username} won ETB {prize_per_winner:.2f}")
        
        result_lines.append(f"\n💰 Total Pot: ETB {total_pot:.2f}")
        result_lines.append(f"💸 House Fee: ETB {total_pot * 0.05:.2f}")
        
        # Add "Play Again" button
        keyboard = [
            [InlineKeyboardButton("🎮 Play Again", callback_data='create_room')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send results to all players
        result_text = "\n".join(result_lines)
        for player in room.players:
            try:
                await context.bot.send_message(
                    chat_id=player.user.telegram_id,
                    text=result_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Error sending result to player {player.user_id}: {e}")

    except Exception as e:
        LOGGER.error(f"Error processing game result: {e}")
        db.session.rollback()

def get_move_emoji(move: str) -> str:
    """Get emoji for a move"""
    return {
        'rock': '🪨 Rock',
        'paper': '📄 Paper',
        'scissors': '✂️ Scissors'
    }.get(move, '❓ Unknown')

def beats(move1: str, move2: str) -> bool:
    """Determine if move1 beats move2"""
    return (
        (move1 == 'rock' and move2 == 'scissors') or
        (move1 == 'paper' and move2 == 'rock') or
        (move1 == 'scissors' and move2 == 'paper')
    )

async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new user account"""
    try:
        user = update.effective_user
        
        # Check if user already exists
        existing_user = User.query.filter_by(telegram_id=user.id).first()
        if existing_user:
            await update.message.reply_text(
                "You already have an account! Use /balance to check your balance."
            )
            return
        
        # Create new user
        try:
            new_user = User(
                telegram_id=user.id,
                username=user.username or f"player_{user.id}",
                balance=0.0,
                wins=0,
                losses=0,
                created_at=datetime.utcnow()
            )
            db.session.add(new_user)
            db.session.commit()
            
            # Show success message with deposit instructions
            keyboard = [
                [
                    InlineKeyboardButton("💰 Deposit", callback_data='deposit'),
                    InlineKeyboardButton("🎮 Create Room", callback_data='create_room')
                ],
                [
                    InlineKeyboardButton("📖 How to Play", callback_data='help'),
                    InlineKeyboardButton("📊 Rules", callback_data='rules')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Account created successfully! 🎉\n\n"
                "🎲 *How to Play:*\n"
                "1. Add funds to your wallet\n"
                "2. Create or join a room\n"
                "3. Choose rock, paper, or scissors\n"
                "4. Win and collect your prize!\n\n"
                "💰 *Betting Limits:*\n"
                "• Minimum bet: 10 ETB\n"
                "• Maximum bet: 1000 ETB\n"
                "• Winner takes 95% of the pot!\n\n"
                "Get started by adding funds to your wallet!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as db_error:
            LOGGER.error(f"Error creating user account: {db_error}")
            await update.message.reply_text(
                "Sorry, there was an error creating your account. Please try again later or contact support."
            )
            
    except Exception as e:
        LOGGER.error(f"Error in create_account command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later or contact support."
        )

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle deposit command with simulated payment"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # For simulation, we'll add a fixed amount of 100 ETB
        deposit_amount = 100.0
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            amount=deposit_amount,
            type='deposit',
            status='completed',
            reference_id=f"DEP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user.id}"
        )
        
        # Update user balance
        user.balance += deposit_amount
        
        try:
            db.session.add(transaction)
            db.session.commit()
            
            await update.message.reply_text(
                f"✅ *Deposit Successful!*\n\n"
                f"Amount: ETB {deposit_amount:.2f}\n"
                f"New Balance: ETB {user.balance:.2f}\n\n"
                f"Transaction ID: `{transaction.reference_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as db_error:
            db.session.rollback()
            LOGGER.error(f"Database error during deposit: {db_error}")
            await update.message.reply_text(
                "Sorry, there was an error processing your deposit. Please try again later."
            )
            
    except Exception as e:
        LOGGER.error(f"Error in deposit command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle withdraw command with balance validation"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # For simulation, we'll withdraw a fixed amount of 50 ETB
        withdraw_amount = 50.0
        
        # Validate user has enough balance
        if user.balance < withdraw_amount:
            await update.message.reply_text(
                f"Insufficient balance! You need ETB {withdraw_amount:.2f} to withdraw.\n"
                f"Your balance: ETB {user.balance:.2f}"
            )
            return
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            amount=-withdraw_amount,  # Negative amount for withdrawal
            type='withdraw',
            status='completed',
            reference_id=f"WD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user.id}"
        )
        
        # Update user balance
        user.balance -= withdraw_amount
        
        try:
            db.session.add(transaction)
            db.session.commit()
            
            await update.message.reply_text(
                f"✅ *Withdrawal Successful!*\n\n"
                f"Amount: ETB {withdraw_amount:.2f}\n"
                f"New Balance: ETB {user.balance:.2f}\n\n"
                f"Transaction ID: `{transaction.reference_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as db_error:
            db.session.rollback()
            LOGGER.error(f"Database error during withdrawal: {db_error}")
            await update.message.reply_text(
                "Sorry, there was an error processing your withdrawal. Please try again later."
            )
            
    except Exception as e:
        LOGGER.error(f"Error in withdraw command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle delete account command with confirmation"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, delete my account", callback_data='confirm_delete'),
                InlineKeyboardButton("❌ No, keep my account", callback_data='cancel_delete')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ *Delete Account Confirmation*\n\n"
            "Are you sure you want to delete your account?\n"
            "This will:\n"
            "• Delete your account\n"
            "• Remove your game history\n"
            "• Clear your wallet balance\n\n"
            "This action cannot be undone!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in delete_account command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the confirmation of account deletion"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == 'confirm_delete':
            user = User.query.filter_by(telegram_id=update.effective_user.id).first()
            if not user:
                await query.edit_message_text("Account not found.")
                return
            
            try:
                # Delete all related records
                RoomPlayer.query.filter_by(user_id=user.id).delete()
                Transaction.query.filter_by(user_id=user.id).delete()
                Room.query.filter_by(creator_id=user.id).delete()
                
                # Delete the user
                db.session.delete(user)
                db.session.commit()
                
                await query.edit_message_text(
                    "✅ *Account Deleted Successfully*\n\n"
                    "Your account and all associated data have been permanently deleted.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            except Exception as db_error:
                db.session.rollback()
                LOGGER.error(f"Database error during account deletion: {db_error}")
                await query.edit_message_text(
                    "Sorry, there was an error deleting your account. Please try again later."
                )
                
        elif query.data == 'cancel_delete':
            await query.edit_message_text(
                "Account deletion cancelled. Your account remains active."
            )
            
    except Exception as e:
        LOGGER.error(f"Error handling delete confirmation: {e}")
        await query.edit_message_text(
            "Sorry, something went wrong. Please try again later."
        )

async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current game status"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Find user's active room
        active_room = RoomPlayer.query.join(Room).filter(
            RoomPlayer.user_id == user.id,
            Room.status.in_(['waiting', 'in_progress'])
        ).first()
        
        if not active_room:
            await update.message.reply_text(
                "You are not in any active game room.\n"
                "Use /create_room to create a new room or /join_room to join one."
            )
            return

        room = active_room.room
        
        # Count submitted moves
        moves_submitted = sum(1 for player in room.players if player.move is not None)
        
        # Calculate time left if game is in progress
        time_left = ""
        if room.status == 'in_progress' and room.started_at:
            time_elapsed = datetime.utcnow() - room.started_at
            time_left_seconds = max(0, 300 - time_elapsed.total_seconds())  # 5 minutes timeout
            minutes = int(time_left_seconds // 60)
            seconds = int(time_left_seconds % 60)
            time_left = f"\n⏱️ Time Left: {minutes:02d}:{seconds:02d}"
        
        # Create status message
        status_message = (
            f"🎮 *Game Status*\n\n"
            f"Room Code: `{room.room_code}`\n"
            f"Players Joined: {len(room.players)}/3\n"
            f"Moves Submitted: {moves_submitted}/3"
        )
        
        if time_left:
            status_message += time_left
            
        # Add room status
        status_message += f"\n\nStatus: {room.status.replace('_', ' ').title()}"
        
        # Add action buttons based on room status
        keyboard = []
        if room.status == 'waiting':
            keyboard.append([
                InlineKeyboardButton("🔗 Share Room", callback_data=f'share_room_{room.room_code}'),
                InlineKeyboardButton("❌ Leave Room", callback_data=f'leave_room_{room.room_code}')
            ])
        elif room.status == 'in_progress' and not active_room.move:
            keyboard.append([
                InlineKeyboardButton("🪨 Rock", callback_data=f"move_rock_{room.room_code}"),
                InlineKeyboardButton("📄 Paper", callback_data=f"move_paper_{room.room_code}"),
                InlineKeyboardButton("✂️ Scissors", callback_data=f"move_scissors_{room.room_code}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            status_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in game_status command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's recent game history"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Get last 5 completed games where user participated
        recent_games = Room.query.join(RoomPlayer).filter(
            RoomPlayer.user_id == user.id,
            Room.status == 'completed'
        ).order_by(Room.completed_at.desc()).limit(5).all()
        
        if not recent_games:
            await update.message.reply_text(
                "You haven't played any games yet!\n"
                "Use /create_room to start playing."
            )
            return
        
        # Format game history
        history_lines = []
        for game in recent_games:
            # Get player's result
            player = RoomPlayer.query.filter_by(room_id=game.id, user_id=user.id).first()
            
            # Calculate result and amount
            if player.move:
                # Get all moves
                moves = {p.user_id: p.move for p in game.players}
                
                # Calculate wins for each player
                wins = {p.user_id: 0 for p in game.players}
                for p1 in game.players:
                    for p2 in game.players:
                        if p1.user_id != p2.user_id:
                            if beats(p1.move, p2.move):
                                wins[p1.user_id] += 1
                
                # Determine result
                max_wins = max(wins.values())
                winners = [user_id for user_id, win_count in wins.items() if win_count == max_wins]
                
                if user.id in winners:
                    if len(winners) == 1:
                        # Win
                        prize = game.bet_amount * len(game.players) / len(winners)
                        result = f"You Won! 💰 +ETB {prize:.2f}"
                    else:
                        # Draw
                        refund = game.bet_amount
                        result = f"Draw — ETB Refunded"
                else:
                    # Loss
                    result = f"Lost — ETB {game.bet_amount:.2f}"
            else:
                # No move made
                result = "No Move — ETB Forfeited"
            
            # Format date
            date_str = game.completed_at.strftime("%b %d")
            
            # Add to history
            history_lines.append(
                f"📅 {date_str} — Room {game.room_code} — {result}"
            )
        
        # Create history message
        history_message = "📊 *Your Recent Games*\n\n" + "\n".join(history_lines)
        
        # Add stats summary
        history_message += f"\n\n*Overall Stats:*\n"
        history_message += f"Wins: {user.wins}\n"
        history_message += f"Losses: {user.losses}\n"
        history_message += f"Current Balance: ETB {user.balance:.2f}"
        
        await update.message.reply_text(
            history_message,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in history command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top players by wins and balance"""
    try:
        # Get top 5 players by wins
        top_winners = User.query.order_by(User.wins.desc()).limit(5).all()
        
        # Get top 5 players by balance
        top_balance = User.query.order_by(User.balance.desc()).limit(5).all()
        
        # Format winners leaderboard
        winners_lines = ["🏆 *Top Players by Wins*\n"]
        for i, user in enumerate(top_winners, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            username = f"@{user.username}" if user.username else f"Player_{user.telegram_id}"
            winners_lines.append(
                f"{medal} {username} — {user.wins} Wins — ETB {user.balance:,.2f}"
            )
        
        # Format balance leaderboard
        balance_lines = ["\n💰 *Top Players by Balance*\n"]
        for i, user in enumerate(top_balance, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            username = f"@{user.username}" if user.username else f"Player_{user.telegram_id}"
            balance_lines.append(
                f"{medal} {username} — {user.wins} Wins — ETB {user.balance:,.2f}"
            )
        
        # Create keyboard for switching views
        keyboard = [
            [
                InlineKeyboardButton("🏆 By Wins", callback_data='leaderboard_wins'),
                InlineKeyboardButton("💰 By Balance", callback_data='leaderboard_balance')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Combine messages
        leaderboard_message = "\n".join(winners_lines + balance_lines)
        
        await update.message.reply_text(
            leaderboard_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in leaderboard command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def handle_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle leaderboard view switching"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == 'leaderboard_wins':
            # Get top 5 players by wins
            top_players = User.query.order_by(User.wins.desc()).limit(5).all()
            title = "🏆 *Top Players by Wins*\n"
        else:  # leaderboard_balance
            # Get top 5 players by balance
            top_players = User.query.order_by(User.balance.desc()).limit(5).all()
            title = "💰 *Top Players by Balance*\n"
        
        # Format leaderboard
        lines = [title]
        for i, user in enumerate(top_players, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            username = f"@{user.username}" if user.username else f"Player_{user.telegram_id}"
            lines.append(
                f"{medal} {username} — {user.wins} Wins — ETB {user.balance:,.2f}"
            )
        
        # Create keyboard for switching views
        keyboard = [
            [
                InlineKeyboardButton("🏆 By Wins", callback_data='leaderboard_wins'),
                InlineKeyboardButton("💰 By Balance", callback_data='leaderboard_balance')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error handling leaderboard callback: {e}")
        await query.edit_message_text(
            "Sorry, something went wrong. Please try again later."
        )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile and statistics"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("You need to create an account first! Use /start")
            return

        # Calculate total games and win rate
        total_games = user.wins + user.losses
        win_rate = (user.wins / total_games * 100) if total_games > 0 else 0
        
        # Format profile message
        profile_message = (
            f"👤 *Player Profile*\n\n"
            f"Username: @{user.username}\n"
            f"Balance: ETB {user.balance:,.2f}\n\n"
            f"🎮 *Game Statistics*\n"
            f"Total Games: {total_games}\n"
            f"Wins: {user.wins}\n"
            f"Losses: {user.losses}\n"
            f"Win Rate: {win_rate:.1f}%\n\n"
            f"📅 Member since: {user.created_at.strftime('%B %d, %Y')}"
        )
        
        # Create keyboard for quick actions
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data='deposit'),
                InlineKeyboardButton("🎮 Play Now", callback_data='create_room')
            ],
            [
                InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard_wins'),
                InlineKeyboardButton("📜 History", callback_data='history')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            profile_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in profile command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show information about the bot"""
    try:
        about_message = (
            "🤖 *Rock Paper Scissors Game Bot*\n\n"
            "A multiplayer game bot for 3 players where you can:\n"
            "• Create and join game rooms\n"
            "• Bet with other players\n"
            "• Win prizes and climb the leaderboard\n\n"
            "Built with ❤️ using:\n"
            "• Python\n"
            "• SQLite\n"
            "• Telegram API\n\n"
            "Powered by: Chapa (Payment simulation)\n\n"
            "Use /start to begin playing!"
        )
        
        # Create keyboard for quick actions
        keyboard = [
            [
                InlineKeyboardButton("🎮 Play Now", callback_data='create_room'),
                InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard_wins')
            ],
            [
                InlineKeyboardButton("📖 How to Play", callback_data='help'),
                InlineKeyboardButton("📜 Rules", callback_data='rules')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            about_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in about command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of available commands"""
    try:
        help_message = (
            "🎮 *Available Commands*\n\n"
            "*/start* - Start the bot and create account\n"
            "*/create_account* - Start your game journey\n"
            "*/deposit* - Add virtual money\n"
            "*/withdraw* - Withdraw your winnings\n"
            "*/balance* - View your wallet\n\n"
            "*/create_room <amount>* - Start a new game room\n"
            "*/join_room <code>* - Join a room\n"
            "*/game_status* - Check current game status\n\n"
            "*/profile* - View your stats and info\n"
            "*/history* - See your recent games\n"
            "*/leaderboard* - Top players ranking\n"
            "*/about* - Bot information\n"
            "*/help* - Show this help message\n\n"
            "💰 *Betting Limits:*\n"
            "• Minimum bet: 10 ETB\n"
            "• Maximum bet: 1000 ETB\n"
            "• Winner takes 95% of the pot!"
        )
        
        # Create keyboard for quick actions
        keyboard = [
            [
                InlineKeyboardButton("🎮 Play Now", callback_data='create_room'),
                InlineKeyboardButton("💰 Deposit", callback_data='deposit')
            ],
            [
                InlineKeyboardButton("📊 Leaderboard", callback_data='leaderboard_wins'),
                InlineKeyboardButton("📜 Rules", callback_data='rules')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
            
    except Exception as e:
        LOGGER.error(f"Error in help command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

def main() -> None:
    """Start the bot"""
    try:
        # Get bot token from environment variable
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            LOGGER.error("TELEGRAM_BOT_TOKEN environment variable not set")
            return
        
        # Create application and add handlers
        application = Application.builder().token(token).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("create_account", create_account))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("deposit", deposit))
        application.add_handler(CommandHandler("withdraw", withdraw))
        application.add_handler(CommandHandler("delete_account", delete_account))
        application.add_handler(CommandHandler("create_room", create_room))
        application.add_handler(CommandHandler("join_room", join_room))
        application.add_handler(CommandHandler("join_game", join_game))
        application.add_handler(CommandHandler("game_status", game_status))
        application.add_handler(CommandHandler("history", history))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("profile", profile))
        application.add_handler(CommandHandler("about", about))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(CallbackQueryHandler(handle_delete_confirmation, pattern='^(confirm|cancel)_delete$'))
        application.add_handler(CallbackQueryHandler(handle_leaderboard_callback, pattern='^leaderboard_(wins|balance)$'))

        # Start the bot
        LOGGER.info("Starting bot...")
        application.run_polling()

    except Exception as e:
        LOGGER.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()
