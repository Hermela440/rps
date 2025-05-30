"""Admin command handlers"""
from telegram import Update
from telegram.ext import ContextTypes
from models import User, Transaction, WithdrawalRequest
from extensions import db
from services.transaction import TransactionService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
transaction_service = TransactionService()

async def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    user = User.query.filter_by(telegram_id=user_id).first()
    return user and user.is_admin

async def require_admin(func):
    """Decorator to require admin privileges"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            await update.message.reply_text("Error: Could not get user information.")
            return
        
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ This command is only available to administrators.")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

@require_admin
async def handle_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /approve command"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Please provide a transaction reference.\n"
                "Usage: /approve <tx_ref>"
            )
            return

        tx_ref = context.args[0]
        
        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            await update.message.reply_text("❌ Transaction not found.")
            return

        if transaction.status != 'pending':
            await update.message.reply_text(
                f"❌ Transaction is already {transaction.status}."
            )
            return

        # Process withdrawal
        success, result = transaction_service.process_withdrawal(tx_ref)
        if not success:
            await update.message.reply_text(f"❌ {result}")
            return

        # Get user
        user = User.query.get(transaction.user_id)
        if not user or not user.telegram_id:
            await update.message.reply_text(
                "✅ Withdrawal approved but could not notify user."
            )
            return

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"✅ Your withdrawal has been approved!\n\n"
                    f"Amount: {transaction.amount} ETB\n"
                    f"Reference: {tx_ref}\n"
                    f"Status: Completed"
                )
            )
        except Exception as e:
            logger.error(f"Error notifying user {user.id}: {str(e)}")

        await update.message.reply_text(
            f"✅ Withdrawal approved and user notified."
        )

    except Exception as e:
        logger.error(f"Error in approve handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred while processing the approval."
        )

@require_admin
async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reject command"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Please provide a transaction reference.\n"
                "Usage: /reject <tx_ref>"
            )
            return

        tx_ref = context.args[0]
        
        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            await update.message.reply_text("❌ Transaction not found.")
            return

        if transaction.status != 'pending':
            await update.message.reply_text(
                f"❌ Transaction is already {transaction.status}."
            )
            return

        # Reject withdrawal
        success, result = transaction_service.reject_withdrawal(tx_ref)
        if not success:
            await update.message.reply_text(f"❌ {result}")
            return

        # Get user
        user = User.query.get(transaction.user_id)
        if not user or not user.telegram_id:
            await update.message.reply_text(
                "✅ Withdrawal rejected but could not notify user."
            )
            return

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"❌ Your withdrawal has been rejected.\n\n"
                    f"Amount: {transaction.amount} ETB\n"
                    f"Reference: {tx_ref}\n"
                    f"Status: Rejected\n\n"
                    f"Your balance has been refunded."
                )
            )
        except Exception as e:
            logger.error(f"Error notifying user {user.id}: {str(e)}")

        await update.message.reply_text(
            f"✅ Withdrawal rejected and user notified."
        )

    except Exception as e:
        logger.error(f"Error in reject handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred while processing the rejection."
        )

@require_admin
async def handle_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pending command"""
    try:
        # Get pending withdrawals
        pending = Transaction.query.filter_by(
            type='withdrawal',
            status='pending'
        ).order_by(Transaction.created_at.desc()).all()

        if not pending:
            await update.message.reply_text("No pending withdrawals.")
            return

        # Format message
        message = "📋 Pending Withdrawals:\n\n"
        for tx in pending:
            user = User.query.get(tx.user_id)
            message += (
                f"User: {user.username if user else 'Unknown'}\n"
                f"Amount: {tx.amount} ETB\n"
                f"Reference: {tx.tx_ref}\n"
                f"Created: {tx.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"To approve: /approve {tx.tx_ref}\n"
                f"To reject: /reject {tx.tx_ref}\n\n"
            )

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in pending handler: {str(e)}")
        await update.message.reply_text(
            "An error occurred while fetching pending withdrawals."
        ) 