"""Handle /deposit command (Chapa init)"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import User, Transaction
from extensions import db
from services.chapa_service import ChapaService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
chapa_service = ChapaService()

# Conversation states
WAITING_AMOUNT = 1

async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deposit command"""
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

        # Check if amount is provided in command
        if context.args:
            try:
                amount = float(context.args[0])
                return await process_deposit(update, context, amount)
            except ValueError:
                await update.message.reply_text(
                    "Invalid amount format. Please enter a valid number."
                )
                return ConversationHandler.END

        # Ask for deposit amount
        await update.message.reply_text(
            "💰 Please enter the amount you want to deposit (ETB):"
        )
        return WAITING_AMOUNT

    except Exception as e:
        logger.error(f"Error in deposit handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def process_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float):
    """Process deposit request"""
    try:
        # Get user
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Create deposit
        success, result = chapa_service.create_deposit(
            db_user.id,
            amount
        )

        if not success:
            await update.message.reply_text(f"❌ {result}")
            return ConversationHandler.END

        # Create payment link keyboard
        keyboard = [[
            InlineKeyboardButton("💳 Pay Now", url=result['payment_url'])
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send payment link
        await update.message.reply_text(
            f"✅ Deposit request created!\n\n"
            f"Amount: {amount} ETB\n"
            f"Reference: {result['reference']}\n\n"
            "Click the button below to pay:",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error processing deposit: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

def get_deposit_handler():
    """Get deposit conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("deposit", handle_deposit)],
        states={
            WAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                             lambda u, c: process_deposit(u, c, float(u.message.text)))
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ) 