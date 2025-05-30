"""Handle Rock Paper Scissors game"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import User, Transaction
from extensions import db
from services.transaction import TransactionService
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
transaction_service = TransactionService()

# Game states
WAITING_BET = 1
WAITING_CHOICE = 2

# Game choices
ROCK = "🪨"
PAPER = "📄"
SCISSORS = "✂️"

# Game rules
WINNING_COMBOS = {
    ROCK: SCISSORS,
    PAPER: ROCK,
    SCISSORS: PAPER
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

        # Check if bet amount is provided
        if context.args:
            try:
                bet = float(context.args[0])
                context.user_data['bet_amount'] = bet
                return await request_choice(update, context)
            except ValueError:
                await update.message.reply_text(
                    "Invalid bet amount. Please enter a valid number."
                )
                return ConversationHandler.END

        # Ask for bet amount
        await update.message.reply_text(
            "💰 How much do you want to bet? (ETB):"
        )
        return WAITING_BET

    except Exception as e:
        logger.error(f"Error in play handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bet amount input"""
    try:
        # Get bet amount
        try:
            bet = float(update.message.text)
        except ValueError:
            await update.message.reply_text(
                "Invalid bet amount. Please enter a valid number."
            )
            return WAITING_BET

        # Store bet in context
        context.user_data['bet_amount'] = bet
        return await request_choice(update, context)

    except Exception as e:
        logger.error(f"Error handling bet: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def request_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request player's choice"""
    try:
        bet = context.user_data.get('bet_amount')
        if not bet:
            await update.message.reply_text(
                "Please start over with /play command."
            )
            return ConversationHandler.END

        # Get user
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Check user balance
        if db_user.balance < bet:
            await update.message.reply_text(
                f"❌ Insufficient balance!\n\n"
                f"Bet amount: {bet} ETB\n"
                f"Your balance: {db_user.balance} ETB"
            )
            return ConversationHandler.END

        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton(ROCK, callback_data=f"choice_{ROCK}"),
                InlineKeyboardButton(PAPER, callback_data=f"choice_{PAPER}"),
                InlineKeyboardButton(SCISSORS, callback_data=f"choice_{SCISSORS}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎮 Choose your move (Bet: {bet} ETB):",
            reply_markup=reply_markup
        )
        return WAITING_CHOICE

    except Exception as e:
        logger.error(f"Error requesting choice: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player's choice"""
    try:
        query = update.callback_query
        await query.answer()

        # Get player's choice
        choice = query.data.split('_')[1]
        bet = context.user_data.get('bet_amount')

        if not bet:
            await query.edit_message_text(
                "Please start over with /play command."
            )
            return ConversationHandler.END

        # Get user
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Generate bot's choice
        bot_choice = random.choice([ROCK, PAPER, SCISSORS])

        # Determine winner
        result = determine_winner(choice, bot_choice)
        
        # Update balance
        if result == "win":
            winnings = bet * 2  # 2x bet for winning
            db_user.balance += winnings
            result_text = f"🎉 You won {winnings} ETB!"
        elif result == "lose":
            db_user.balance -= bet
            result_text = f"😢 You lost {bet} ETB!"
        else:
            result_text = "🤝 It's a tie! Your bet is returned."

        # Create transaction record
        transaction = Transaction(
            user_id=db_user.id,
            tx_ref=f"GAME-{uuid.uuid4().hex[:8].upper()}",
            type='game',
            amount=bet,
            status='completed'
        )
        db.session.add(transaction)
        db.session.commit()

        # Send result
        await query.edit_message_text(
            f"🎮 Game Result:\n\n"
            f"Your choice: {choice}\n"
            f"Bot's choice: {bot_choice}\n\n"
            f"{result_text}\n\n"
            f"New balance: {db_user.balance} ETB"
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error handling choice: {str(e)}")
        await query.edit_message_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

def determine_winner(player_choice: str, bot_choice: str) -> str:
    """Determine the winner of the game"""
    if player_choice == bot_choice:
        return "tie"
    if WINNING_COMBOS[player_choice] == bot_choice:
        return "win"
    return "lose"

def get_game_handler():
    """Get game conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("play", handle_play)],
        states={
            WAITING_BET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet)
            ],
            WAITING_CHOICE: [
                CallbackQueryHandler(handle_choice, pattern="^choice_")
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ) 