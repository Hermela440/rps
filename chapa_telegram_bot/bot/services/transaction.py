"""Transaction service for handling deposits and withdrawals"""
from models import User, Transaction, WithdrawalRequest
from extensions import db
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransactionService:
    """Service for handling transactions"""
    
    def __init__(self):
        """Initialize transaction service"""
        self.min_amount = 10  # Minimum transaction amount in ETB
        self.max_amount = 10000  # Maximum transaction amount in ETB
        self.daily_limit = 50000  # Daily withdrawal limit in ETB

    def _generate_tx_ref(self) -> str:
        """Generate unique transaction reference"""
        return f"TX-{uuid.uuid4().hex[:8].upper()}"

    def _validate_amount(self, amount: float) -> tuple[bool, str]:
        """Validate transaction amount"""
        try:
            amount = float(amount)
            if amount < self.min_amount:
                return False, f"Minimum amount is {self.min_amount} ETB"
            if amount > self.max_amount:
                return False, f"Maximum amount is {self.max_amount} ETB"
            return True, str(amount)
        except ValueError:
            return False, "Invalid amount format"

    def _check_daily_limit(self, user_id: int, amount: float) -> tuple[bool, str]:
        """Check if user has exceeded daily withdrawal limit"""
        today = datetime.utcnow().date()
        daily_total = db.session.query(db.func.sum(Transaction.amount))\
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == 'withdrawal',
                db.func.date(Transaction.created_at) == today
            ).scalar() or 0

        if daily_total + amount > self.daily_limit:
            return False, f"Daily withdrawal limit exceeded. Remaining: {self.daily_limit - daily_total} ETB"
        return True, ""

    def create_deposit(self, user_id: int, amount: float) -> tuple[bool, dict]:
        """Create a new deposit transaction"""
        try:
            # Validate amount
            valid, message = self._validate_amount(amount)
            if not valid:
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Create transaction
            tx_ref = self._generate_tx_ref()
            transaction = Transaction(
                user_id=user_id,
                tx_ref=tx_ref,
                type='deposit',
                amount=float(amount),
                status='pending'
            )
            db.session.add(transaction)
            db.session.commit()

            return True, {
                'reference': tx_ref,
                'amount': amount,
                'status': 'pending'
            }

        except Exception as e:
            logger.error(f"Error creating deposit: {str(e)}")
            db.session.rollback()
            return False, "Failed to create deposit"

    def create_withdrawal(self, user_id: int, amount: float, wallet: str) -> tuple[bool, dict]:
        """Create a new withdrawal request"""
        try:
            # Validate amount
            valid, message = self._validate_amount(amount)
            if not valid:
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Check balance
            if user.balance < amount:
                return False, "Insufficient balance"

            # Check daily limit
            valid, message = self._check_daily_limit(user_id, amount)
            if not valid:
                return False, message

            # Create transaction
            tx_ref = self._generate_tx_ref()
            transaction = Transaction(
                user_id=user_id,
                tx_ref=tx_ref,
                type='withdrawal',
                amount=float(amount),
                status='pending'
            )
            db.session.add(transaction)

            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                user_id=user_id,
                amount=float(amount),
                wallet_address=wallet,
                status='pending'
            )
            db.session.add(withdrawal)

            # Deduct balance
            user.balance -= float(amount)

            db.session.commit()

            return True, {
                'reference': tx_ref,
                'amount': amount,
                'status': 'pending'
            }

        except Exception as e:
            logger.error(f"Error creating withdrawal: {str(e)}")
            db.session.rollback()
            return False, "Failed to create withdrawal"

    def process_withdrawal(self, tx_ref: str) -> tuple[bool, str]:
        """Process a withdrawal request"""
        try:
            # Get transaction
            transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
            if not transaction:
                return False, "Transaction not found"

            if transaction.status != 'pending':
                return False, f"Transaction is already {transaction.status}"

            # Get withdrawal request
            withdrawal = WithdrawalRequest.query.filter_by(
                user_id=transaction.user_id,
                amount=transaction.amount
            ).order_by(WithdrawalRequest.created_at.desc()).first()

            if not withdrawal:
                return False, "Withdrawal request not found"

            # Update transaction status
            transaction.status = 'completed'
            withdrawal.status = 'completed'

            db.session.commit()

            return True, "Withdrawal processed successfully"

        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}")
            db.session.rollback()
            return False, "Failed to process withdrawal"

    def reject_withdrawal(self, tx_ref: str) -> tuple[bool, str]:
        """Reject a withdrawal request"""
        try:
            # Get transaction
            transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
            if not transaction:
                return False, "Transaction not found"

            if transaction.status != 'pending':
                return False, f"Transaction is already {transaction.status}"

            # Get withdrawal request
            withdrawal = WithdrawalRequest.query.filter_by(
                user_id=transaction.user_id,
                amount=transaction.amount
            ).order_by(WithdrawalRequest.created_at.desc()).first()

            if not withdrawal:
                return False, "Withdrawal request not found"

            # Get user
            user = User.query.get(transaction.user_id)
            if not user:
                return False, "User not found"

            # Update transaction status
            transaction.status = 'rejected'
            withdrawal.status = 'rejected'

            # Refund balance
            user.balance += transaction.amount

            db.session.commit()

            return True, "Withdrawal rejected and refunded"

        except Exception as e:
            logger.error(f"Error rejecting withdrawal: {str(e)}")
            db.session.rollback()
            return False, "Failed to reject withdrawal" 