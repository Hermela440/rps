"""Deposit command handler for the bot"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import User, Transaction
from extensions import db
from payment_service import PaymentService
from config import MIN_DEPOSIT_AMOUNT, MAX_DEPOSIT_AMOUNT
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment service
payment_service = PaymentService()

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
            f"💰 Please enter the amount you want to deposit (ETB):\n\n"
            f"Minimum: {MIN_DEPOSIT_AMOUNT} ETB\n"
            f"Maximum: {MAX_DEPOSIT_AMOUNT} ETB"
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
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Create deposit transaction
        success, result = payment_service.create_deposit(db_user.id, amount)
        
        if not success:
            await update.message.reply_text(f"❌ {result}")
            return ConversationHandler.END

        # Extract payment details
        checkout_url = result.get("checkout_url")
        tx_ref = result.get("reference")

        # Create keyboard with payment link
        keyboard = [
            [InlineKeyboardButton("💳 Pay Now", url=checkout_url)],
            [InlineKeyboardButton("🔄 Check Status", callback_data=f"check_deposit_{tx_ref}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send payment instructions
        await update.message.reply_text(
            f"💳 Payment Details:\n\n"
            f"Amount: {amount} ETB\n"
            f"Reference: {tx_ref}\n\n"
            "Click the button below to complete your payment:",
            reply_markup=reply_markup
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error processing deposit: {str(e)}")
        await update.message.reply_text(
            "An error occurred while processing your deposit. Please try again later."
        )
        return ConversationHandler.END

async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit amount input"""
    try:
        # Get amount from message
        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text(
                "Invalid amount format. Please enter a valid number."
            )
            return WAITING_AMOUNT

        return await process_deposit(update, context, amount)

    except Exception as e:
        logger.error(f"Error handling deposit amount: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit status check callback"""
    try:
        query = update.callback_query
        await query.answer()

        # Extract transaction reference
        tx_ref = query.data.split("_")[-1]
        
        # Verify deposit status
        success, message = payment_service.verify_deposit(tx_ref)
        
        if success:
            # Get transaction details
            transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
            if transaction:
                await query.edit_message_text(
                    f"✅ Payment successful!\n\n"
                    f"Amount: {transaction.amount} ETB\n"
                    f"Reference: {tx_ref}\n\n"
                    f"Your balance has been updated."
                )
            else:
                await query.edit_message_text(
                    "✅ Payment successful!\n\n"
                    "Your balance has been updated."
                )
        else:
            await query.edit_message_text(
                f"⏳ Payment status: {message}\n\n"
                "Please wait while we verify your payment."
            )

    except Exception as e:
        logger.error(f"Error in deposit callback: {str(e)}")
        await query.edit_message_text(
            "An error occurred while checking payment status. Please try again later."
        )

def get_deposit_handler():
    """Get deposit conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("deposit", handle_deposit)],
        states={
            WAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_amount)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ) 