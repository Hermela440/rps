"""Command handlers for the bot"""
from telegram import Update
from telegram.ext import ContextTypes
from payment_service import PaymentService
from models import User, Transaction, WithdrawalRequest
from extensions import db
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment service
payment_service = PaymentService()

async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit command"""
    try:
        # Get user ID
        user_id = update.effective_user.id
        
        # Check if amount is provided
        if not context.args:
            await update.message.reply_text("Please provide an amount to deposit.")
            return
            
        # Parse amount
        try:
            amount = float(context.args[0])
        except ValueError:
            await update.message.reply_text("Please provide a valid amount.")
            return
            
        # Create deposit
        success, response = payment_service.create_deposit(user_id, amount)
        
        if success:
            checkout_url = response["checkout_url"]
            await update.message.reply_text(
                f"Please complete your payment of {amount} ETB:\n{checkout_url}"
            )
        else:
            await update.message.reply_text(f"Error: {response}")
            
    except Exception as e:
        logger.error(f"Error in deposit handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def handle_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal command"""
    try:
        # Get user ID
        user_id = update.effective_user.id
        
        # Check if amount and wallet are provided
        if len(context.args) < 2:
            await update.message.reply_text(
                "Please provide both amount and wallet address.\n"
                "Example: /withdraw 100 0x123..."
            )
            return
            
        # Parse amount
        try:
            amount = float(context.args[0])
        except ValueError:
            await update.message.reply_text("Please provide a valid amount.")
            return
            
        # Get wallet address
        wallet_address = context.args[1]
        
        # Get user
        user = User.query.get(user_id)
        if not user:
            await update.message.reply_text("User not found.")
            return
            
        # Check balance
        if user.balance < amount:
            await update.message.reply_text("Insufficient balance.")
            return
            
        # Create withdrawal request
        try:
            # Create transaction record
            tx_ref = f"WD_{user_id}_{int(datetime.utcnow().timestamp())}"
            transaction = Transaction(
                user_id=user_id,
                tx_ref=tx_ref,
                type='withdrawal',
                amount=amount,
                status='pending'
            )
            db.session.add(transaction)
            
            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                user_id=user_id,
                amount=amount,
                wallet_address=wallet_address,
                status='pending'
            )
            db.session.add(withdrawal)
            
            # Update user balance
            user.balance -= amount
            
            db.session.commit()
            
            # Notify user
            await update.message.reply_text(
                f"Withdrawal request of {amount} ETB created successfully.\n"
                f"Reference: {tx_ref}\n"
                "Your withdrawal is pending admin approval."
            )
            
            # Notify admins (you can implement this based on your admin notification system)
            # notify_admins(f"New withdrawal request: {amount} ETB from user {user.username}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating withdrawal: {str(e)}")
            await update.message.reply_text("Failed to create withdrawal request.")
            
    except Exception as e:
        logger.error(f"Error in withdrawal handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle balance command"""
    try:
        user_id = update.effective_user.id
        transactions = payment_service.get_transactions(user_id, limit=5)
        
        # Get user's current balance
        user = User.query.get(user_id)
        if not user:
            await update.message.reply_text("User not found.")
            return
            
        # Format message
        message = f"Current Balance: {user.balance} ETB\n\n"
        message += "Recent Transactions:\n"
        
        for tx in transactions:
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'rejected': '❌'
            }.get(tx.status, '❓')
            
            message += (
                f"{status_emoji} {tx.type.title()}: {tx.amount} ETB "
                f"({tx.status})\n"
            )
            
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"Error in balance handler: {str(e)}")
        await update.message.reply_text(f"An error occurred: {str(e)}") 