"""Play command handler for Rock Paper Scissors game"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from models import User, Game, GameParticipant
from extensions import db
from services.user import UserService
from datetime import datetime
import random
import logging
from config import GAME_ENTRY_FEE, MIN_PLAYERS, MAX_PLAYERS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize user service
user_service = UserService()

# Game states
WAITING_PLAYERS = 1
WAITING_MOVE = 2

# Game options
MOVES = ['rock', 'paper', 'scissors']
WINNING_COMBINATIONS = {
    'rock': 'scissors',
    'paper': 'rock',
    'scissors': 'paper'
}

async def handle_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /play command"""
    try:
        # Get user info
        user = update.effective_user
        if not user:
            await update.message.reply_text("Error: Could not get user information.")
            return ConversationHandler.END

        # Check if user exists in database
        db_user = User.query.filter_by(telegram_id=user.id).first()
        if not db_user:
            await update.message.reply_text(
                "Please start the bot first with /start command."
            )
            return ConversationHandler.END

        # Check user balance
        if db_user.balance < GAME_ENTRY_FEE:
            await update.message.reply_text(
                f"❌ Insufficient balance!\n\n"
                f"Entry fee: {GAME_ENTRY_FEE} ETB\n"
                f"Your balance: {db_user.balance} ETB\n\n"
                "Please deposit more funds using /deposit command."
            )
            return ConversationHandler.END

        # Create game
        game = Game(
            bet_amount=GAME_ENTRY_FEE,
            status='waiting',
            created_at=datetime.utcnow()
        )
        db.session.add(game)
        
        # Add first player
        participant = GameParticipant(
            game_id=game.id,
            user_id=db_user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(participant)
        db.session.commit()

        # Create join keyboard
        keyboard = [[
            InlineKeyboardButton("🎮 Join Game", callback_data=f"join_{game.id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send game invitation
        await update.message.reply_text(
            f"🎮 Rock Paper Scissors Game\n\n"
            f"Entry fee: {GAME_ENTRY_FEE} ETB\n"
            f"Players: 1/{MAX_PLAYERS}\n\n"
            f"Game ID: {game.id}\n"
            "Share this message to invite players!",
            reply_markup=reply_markup
        )

        return WAITING_PLAYERS

    except Exception as e:
        logger.error(f"Error in play handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player joining the game"""
    try:
        query = update.callback_query
        await query.answer()

        # Get user info
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Get game ID
        game_id = int(query.data.split('_')[1])
        game = Game.query.get(game_id)

        if not game or game.status != 'waiting':
            await query.edit_message_text("Game is no longer available.")
            return ConversationHandler.END

        # Check if user already joined
        existing = GameParticipant.query.filter_by(
            game_id=game_id,
            user_id=db_user.id
        ).first()
        if existing:
            await query.answer("You have already joined this game!")
            return WAITING_PLAYERS

        # Check user balance
        if db_user.balance < GAME_ENTRY_FEE:
            await query.answer("Insufficient balance!")
            return WAITING_PLAYERS

        # Add player
        participant = GameParticipant(
            game_id=game_id,
            user_id=db_user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(participant)
        db.session.commit()

        # Get updated player count
        player_count = GameParticipant.query.filter_by(game_id=game_id).count()

        # Update message
        keyboard = [[
            InlineKeyboardButton("🎮 Join Game", callback_data=f"join_{game_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎮 Rock Paper Scissors Game\n\n"
            f"Entry fee: {GAME_ENTRY_FEE} ETB\n"
            f"Players: {player_count}/{MAX_PLAYERS}\n\n"
            f"Game ID: {game_id}\n"
            "Share this message to invite players!",
            reply_markup=reply_markup
        )

        # Start game if enough players
        if player_count >= MIN_PLAYERS:
            return await start_game(update, context, game_id)

        return WAITING_PLAYERS

    except Exception as e:
        logger.error(f"Error handling join: {str(e)}")
        await query.edit_message_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: int):
    """Start the game and request moves"""
    try:
        game = Game.query.get(game_id)
        if not game:
            return ConversationHandler.END

        # Update game status
        game.status = 'in_progress'
        db.session.commit()

        # Get all participants
        participants = GameParticipant.query.filter_by(game_id=game_id).all()

        # Create move keyboard
        keyboard = [
            [
                InlineKeyboardButton("🪨 Rock", callback_data=f"move_{game_id}_rock"),
                InlineKeyboardButton("📄 Paper", callback_data=f"move_{game_id}_paper")
            ],
            [
                InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{game_id}_scissors")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Notify all players
        for participant in participants:
            user = User.query.get(participant.user_id)
            if user.telegram_id:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🎮 Game #{game_id} Started!\n\n"
                            f"Players: {len(participants)}\n"
                            f"Entry fee: {GAME_ENTRY_FEE} ETB\n"
                            f"Pot: {GAME_ENTRY_FEE * len(participants)} ETB\n\n"
                            "Make your move!"
                        ),
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error notifying player {user.id}: {str(e)}")

        return WAITING_MOVE

    except Exception as e:
        logger.error(f"Error starting game: {str(e)}")
        return ConversationHandler.END

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player's move"""
    try:
        query = update.callback_query
        await query.answer()

        # Get user info
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Get game and move info
        _, game_id, move = query.data.split('_')
        game_id = int(game_id)

        # Get game and participant
        game = Game.query.get(game_id)
        participant = GameParticipant.query.filter_by(
            game_id=game_id,
            user_id=db_user.id
        ).first()

        if not game or not participant:
            await query.edit_message_text("Game not found.")
            return ConversationHandler.END

        if game.status != 'in_progress':
            await query.edit_message_text("Game is not in progress.")
            return ConversationHandler.END

        if participant.choice:
            await query.answer("You have already made your move!")
            return WAITING_MOVE

        # Record move
        participant.choice = move
        db.session.commit()

        # Check if all players have moved
        all_moved = all(p.choice for p in GameParticipant.query.filter_by(game_id=game_id).all())
        if all_moved:
            return await end_game(update, context, game_id)

        # Update message
        await query.edit_message_text(
            f"✅ Move recorded: {move.upper()}\n\n"
            "Waiting for other players..."
        )

        return WAITING_MOVE

    except Exception as e:
        logger.error(f"Error handling move: {str(e)}")
        await query.edit_message_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: int):
    """End the game and determine winner"""
    try:
        game = Game.query.get(game_id)
        participants = GameParticipant.query.filter_by(game_id=game_id).all()

        # Get all moves
        moves = {p.user_id: p.choice for p in participants}
        
        # Determine winner
        winner_id = determine_winner(moves)
        
        # Calculate rewards
        pot = GAME_ENTRY_FEE * len(participants)
        if winner_id:
            # Single winner gets all
            reward = pot
            user_service.update_balance(winner_id, reward, 'game_win')
        else:
            # Draw - refund all players
            reward = GAME_ENTRY_FEE
            for p in participants:
                user_service.update_balance(p.user_id, reward, 'game_draw')

        # Update game status
        game.status = 'completed'
        game.winner_id = winner_id
        game.completed_at = datetime.utcnow()
        db.session.commit()

        # Create result message
        result_message = create_result_message(game, participants, moves, winner_id, reward)

        # Notify all players
        for participant in participants:
            user = User.query.get(participant.user_id)
            if user.telegram_id:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=result_message
                    )
                except Exception as e:
                    logger.error(f"Error notifying player {user.id}: {str(e)}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error ending game: {str(e)}")
        return ConversationHandler.END

def determine_winner(moves: dict) -> int:
    """Determine game winner from moves"""
    # Get unique moves
    unique_moves = set(moves.values())
    
    # If all moves are the same, it's a draw
    if len(unique_moves) == 1:
        return None
        
    # Check for winner
    for move, player_id in moves.items():
        # Count how many other moves this move beats
        wins = sum(1 for other_move in moves.values()
                  if other_move != move and WINNING_COMBINATIONS[move] == other_move)
        
        # If this move beats all others, it's the winner
        if wins == len(moves) - 1:
            return player_id
            
    return None

def create_result_message(game, participants, moves, winner_id, reward):
    """Create game result message"""
    # Get player names and moves
    player_info = []
    for p in participants:
        user = User.query.get(p.user_id)
        player_info.append(f"@{user.username}: {moves[p.user_id].upper()}")
    
    # Create message
    message = "🎮 Game Results!\n\n"
    message += "\n".join(player_info)
    message += "\n\n"
    
    if winner_id:
        winner = User.query.get(winner_id)
        message += f"🎉 @{winner.username} WINS!\n"
        message += f"💰 Reward: {reward} ETB"
    else:
        message += "🤝 It's a DRAW!\n"
        message += f"💰 Each player gets {reward} ETB"
        
    return message

def get_play_handler():
    """Get play conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("play", handle_play)],
        states={
            WAITING_PLAYERS: [
                CallbackQueryHandler(handle_join, pattern="^join_")
            ],
            WAITING_MOVE: [
                CallbackQueryHandler(handle_move, pattern="^move_")
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ) 