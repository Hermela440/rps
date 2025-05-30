"""Admin command handlers for the bot"""
from telegram import Update
from telegram.ext import ContextTypes
from models import User, Transaction, WithdrawalRequest
from extensions import db
from payment_service import PaymentService
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment service
payment_service = PaymentService()

def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    user = User.query.get(user_id)
    return user and user.is_admin

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Decorator to check admin status"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to administrators.")
        return False
    return True

async def handle_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal approval command"""
    try:
        # Check admin status
        if not await require_admin(update, context):
            return

        # Check if transaction ID is provided
        if not context.args:
            await update.message.reply_text("Please provide a transaction ID.")
            return

        tx_ref = context.args[0]
        
        # Get transaction and withdrawal request
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            await update.message.reply_text("Transaction not found.")
            return

        withdrawal = WithdrawalRequest.query.filter_by(
            user_id=transaction.user_id,
            amount=transaction.amount,
            status='pending'
        ).first()
        
        if not withdrawal:
            await update.message.reply_text("Withdrawal request not found.")
            return

        # Process withdrawal
        try:
            # In test mode, auto-approve
            if payment_service.TEST_MODE:
                success = True
            else:
                # TODO: Implement actual fund transfer via Chapa or other payment provider
                success = True  # Placeholder for actual transfer

            if success:
                # Update transaction status
                transaction.status = 'completed'
                withdrawal.status = 'completed'
                withdrawal.processed_at = datetime.utcnow()
                
                # Get user for notification
                user = User.query.get(transaction.user_id)
                
                db.session.commit()
                
                # Notify user
                if user and user.telegram_id:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"Your withdrawal of {transaction.amount} ETB has been approved and processed."
                    )
                
                await update.message.reply_text(
                    f"Withdrawal approved and processed successfully.\n"
                    f"Amount: {transaction.amount} ETB\n"
                    f"User: {user.username if user else 'Unknown'}"
                )
            else:
                # If transfer fails, refund the user
                user = User.query.get(transaction.user_id)
                if user:
                    user.balance += transaction.amount
                
                transaction.status = 'failed'
                withdrawal.status = 'failed'
                
                db.session.commit()
                
                # Notify user
                if user and user.telegram_id:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"Your withdrawal of {transaction.amount} ETB has failed. "
                             f"The amount has been refunded to your balance."
                    )
                
                await update.message.reply_text("Withdrawal processing failed. User has been refunded.")
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing withdrawal: {str(e)}")
            await update.message.reply_text("Failed to process withdrawal.")

    except Exception as e:
        logger.error(f"Error in approve withdrawal handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def handle_reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal rejection command"""
    try:
        # Check admin status
        if not await require_admin(update, context):
            return

        # Check if transaction ID is provided
        if not context.args:
            await update.message.reply_text("Please provide a transaction ID.")
            return

        tx_ref = context.args[0]
        
        # Get transaction and withdrawal request
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            await update.message.reply_text("Transaction not found.")
            return

        withdrawal = WithdrawalRequest.query.filter_by(
            user_id=transaction.user_id,
            amount=transaction.amount,
            status='pending'
        ).first()
        
        if not withdrawal:
            await update.message.reply_text("Withdrawal request not found.")
            return

        try:
            # Refund the user
            user = User.query.get(transaction.user_id)
            if user:
                user.balance += transaction.amount
            
            # Update statuses
            transaction.status = 'rejected'
            withdrawal.status = 'rejected'
            
            db.session.commit()
            
            # Notify user
            if user and user.telegram_id:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"Your withdrawal request of {transaction.amount} ETB has been rejected. "
                         f"The amount has been refunded to your balance."
                )
            
            await update.message.reply_text(
                f"Withdrawal rejected and refunded.\n"
                f"Amount: {transaction.amount} ETB\n"
                f"User: {user.username if user else 'Unknown'}"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error rejecting withdrawal: {str(e)}")
            await update.message.reply_text("Failed to reject withdrawal.")

    except Exception as e:
        logger.error(f"Error in reject withdrawal handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def handle_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle command to list pending withdrawals"""
    try:
        # Check admin status
        if not await require_admin(update, context):
            return

        # Get pending withdrawals
        pending = WithdrawalRequest.query.filter_by(status='pending').all()
        
        if not pending:
            await update.message.reply_text("No pending withdrawals.")
            return

        # Format message
        message = "📋 Pending Withdrawals:\n\n"
        for w in pending:
            user = User.query.get(w.user_id)
            message += (
                f"ID: {w.id}\n"
                f"User: {user.username if user else 'Unknown'}\n"
                f"Amount: {w.amount} ETB\n"
                f"Wallet: {w.wallet_address}\n"
                f"Date: {w.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"To approve: /approve {w.id}\n"
                f"To reject: /reject {w.id}\n\n"
            )

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in pending withdrawals handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}") 