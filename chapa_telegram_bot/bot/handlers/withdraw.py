"""Handle /withdraw command"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import User, Transaction, WithdrawalRequest
from extensions import db
from services.transaction import TransactionService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
transaction_service = TransactionService()

# Conversation states
WAITING_AMOUNT = 1
WAITING_WALLET = 2

async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command"""
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
                context.user_data['withdraw_amount'] = amount
                return await request_wallet(update, context)
            except ValueError:
                await update.message.reply_text(
                    "Invalid amount format. Please enter a valid number."
                )
                return ConversationHandler.END

        # Ask for withdrawal amount
        await update.message.reply_text(
            "💰 Please enter the amount you want to withdraw (ETB):"
        )
        return WAITING_AMOUNT

    except Exception as e:
        logger.error(f"Error in withdraw handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal amount input"""
    try:
        # Get amount from message
        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text(
                "Invalid amount format. Please enter a valid number."
            )
            return WAITING_AMOUNT

        # Store amount in context
        context.user_data['withdraw_amount'] = amount
        return await request_wallet(update, context)

    except Exception as e:
        logger.error(f"Error handling withdraw amount: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def request_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request wallet address"""
    try:
        amount = context.user_data.get('withdraw_amount')
        if not amount:
            await update.message.reply_text(
                "Please start over with /withdraw command."
            )
            return ConversationHandler.END

        # Get user
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Check user balance
        if db_user.balance < amount:
            await update.message.reply_text(
                f"❌ Insufficient balance!\n\n"
                f"Withdrawal amount: {amount} ETB\n"
                f"Your balance: {db_user.balance} ETB"
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "💳 Please enter your wallet address or phone number:"
        )
        return WAITING_WALLET

    except Exception as e:
        logger.error(f"Error requesting wallet: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

async def handle_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet address input"""
    try:
        wallet = update.message.text.strip()
        amount = context.user_data.get('withdraw_amount')
        
        if not wallet or not amount:
            await update.message.reply_text(
                "Please start over with /withdraw command."
            )
            return ConversationHandler.END

        # Get user
        user = update.effective_user
        db_user = User.query.filter_by(telegram_id=user.id).first()

        # Create withdrawal request
        success, result = transaction_service.create_withdrawal(
            db_user.id,
            amount,
            wallet
        )

        if not success:
            await update.message.reply_text(f"❌ {result}")
            return ConversationHandler.END

        # Notify user
        await update.message.reply_text(
            f"✅ Withdrawal request submitted!\n\n"
            f"Amount: {amount} ETB\n"
            f"Wallet: {wallet}\n"
            f"Reference: {result['reference']}\n\n"
            "Your request is pending admin approval."
        )

        # Notify admins
        admins = User.query.filter_by(is_admin=True).all()
        for admin in admins:
            if admin.telegram_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=(
                            f"🔔 New Withdrawal Request\n\n"
                            f"User: {db_user.username}\n"
                            f"Amount: {amount} ETB\n"
                            f"Wallet: {wallet}\n"
                            f"Reference: {result['reference']}\n\n"
                            f"To approve: /approve {result['reference']}\n"
                            f"To reject: /reject {result['reference']}"
                        )
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin {admin.id}: {str(e)}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error handling wallet: {str(e)}")
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )
        return ConversationHandler.END

def get_withdraw_handler():
    """Get withdrawal conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("withdraw", handle_withdraw)],
        states={
            WAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)
            ],
            WAITING_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet)
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ) 