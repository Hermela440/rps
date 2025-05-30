"""Payment service for handling transactions"""
from datetime import datetime
import logging
from typing import Tuple, Dict, Union, Optional
from extensions import db
from models import User, Transaction
from chapa_integration import ChapaPayment
from capa_wallet import CapaWallet
from config import (
    MIN_DEPOSIT_AMOUNT,
    MAX_DEPOSIT_AMOUNT,
    MIN_WITHDRAW_AMOUNT,
    MAX_WITHDRAW_AMOUNT,
    TEST_MODE
)

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling deposits and withdrawals"""
    
    TEST_MODE = TEST_MODE
    
    def __init__(self):
        self.chapa = ChapaPayment()
        self.capa = CapaWallet()
        logger.info(f"Initialized PaymentService with {'test' if TEST_MODE else 'live'} mode")
    
    @staticmethod
    def validate_amount(amount: float, transaction_type: str) -> Tuple[bool, str]:
        """Validate transaction amount against limits"""
        try:
            if transaction_type == 'deposit':
                if amount < MIN_DEPOSIT_AMOUNT:
                    return False, f"Minimum deposit amount is {MIN_DEPOSIT_AMOUNT}"
                if amount > MAX_DEPOSIT_AMOUNT:
                    return False, f"Maximum deposit amount is {MAX_DEPOSIT_AMOUNT}"
            elif transaction_type == 'withdrawal':
                if amount < MIN_WITHDRAW_AMOUNT:
                    return False, f"Minimum withdrawal amount is {MIN_WITHDRAW_AMOUNT}"
                if amount > MAX_WITHDRAW_AMOUNT:
                    return False, f"Maximum withdrawal amount is {MAX_WITHDRAW_AMOUNT}"
            return True, ""
        except Exception as e:
            logger.error(f"Error validating amount: {str(e)}")
            return False, f"Error validating amount: {str(e)}"

    def create_wallet(self, user_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """Create a Capa wallet for a user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found", None

            success, message, wallet_data = self.capa.create_wallet(
                user_id=str(user_id),
                email=user.email or f"{user.username}@rpsbot.com"
            )

            if success and wallet_data:
                # Update user with wallet ID
                user.wallet_id = wallet_data.get("wallet_id")
                db.session.commit()
                return True, "Wallet created successfully", wallet_data

            return False, message, None

        except Exception as e:
            db.session.rollback()
            return False, f"Error creating wallet: {str(e)}", None

    def create_deposit(self, user_id: int, amount: float) -> Tuple[bool, Union[Dict, str]]:
        """Create a deposit transaction"""
        try:
            # Validate amount
            valid, message = self.validate_amount(amount, 'deposit')
            if not valid:
                logger.warning(f"Invalid deposit amount: {message}")
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                logger.error(f"User not found: {user_id}")
                return False, "User not found"

            # Create transaction record
            tx_ref = f"DEP_{user_id}_{int(datetime.utcnow().timestamp())}"
            transaction = Transaction(
                user_id=user_id,
                tx_ref=tx_ref,
                type='deposit',
                amount=amount,
                status='pending'
            )
            db.session.add(transaction)
            db.session.commit()
            logger.info(f"Created pending deposit transaction: {tx_ref}")

            # In test mode, auto-complete deposit
            if self.TEST_MODE:
                logger.info(f"Test mode: Auto-completing deposit {tx_ref}")
                self.process_transaction(tx_ref, "completed")
                return True, {
                    "message": f"Test deposit of {amount} completed",
                    "reference": tx_ref
                }

            # Initialize Capa wallet deposit
            if user.wallet_id:
                logger.info(f"Initializing Capa wallet deposit for user {user_id}")
                success, message, checkout_url = self.capa.initialize_deposit(
                    wallet_id=user.wallet_id,
                    amount=amount,
                    tx_ref=tx_ref
                )
            else:
                # Fallback to Chapa if no wallet
                logger.info(f"Initializing Chapa deposit for user {user_id}")
                success, message, checkout_url = self.chapa.initialize_payment(
                    amount=amount,
                    email=user.email or f"{user.username}@rpsbot.com",
                    tx_ref=tx_ref,
                    first_name=user.full_name.split()[0] if user.full_name else user.username,
                    last_name=user.full_name.split()[-1] if user.full_name else "Player"
                )

            if not success:
                logger.error(f"Failed to initialize deposit: {message}")
                transaction.status = 'failed'
                db.session.commit()
                return False, message

            logger.info(f"Deposit initialized successfully: {tx_ref}")
            return True, {
                "message": f"Deposit of {amount} initiated",
                "reference": tx_ref,
                "checkout_url": checkout_url
            }

        except Exception as e:
            logger.error(f"Error processing deposit: {str(e)}")
            db.session.rollback()
            return False, f"Error processing deposit: {str(e)}"

    @classmethod
    def create_withdrawal(
        cls,
        user_id: int,
        amount: float,
        bank_details: Dict[str, str]
    ) -> Tuple[bool, Union[Dict, str]]:
        """Create a withdrawal transaction"""
        try:
            # Validate amount
            valid, message = cls.validate_amount(amount, 'withdrawal')
            if not valid:
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Check balance
            if user.balance < amount:
                return False, "Insufficient balance"

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

            # Update user balance
            user.balance -= amount
            db.session.commit()

            # Process withdrawal through Capa wallet
            if user.wallet_id:
                capa = CapaWallet()
                success, message, reference = capa.process_withdrawal(
                    wallet_id=user.wallet_id,
                    amount=amount,
                    bank_details=bank_details
                )
                if not success:
                    # Refund user balance if withdrawal fails
                    user.balance += amount
                    transaction.status = 'failed'
                    db.session.commit()
                    return False, message

            return True, {
                "message": "Withdrawal request created successfully",
                "reference": tx_ref
            }

        except Exception as e:
            db.session.rollback()
            return False, f"Error processing withdrawal: {str(e)}"

    def process_transaction(self, tx_ref: str, status: str) -> bool:
        """Process a transaction (complete or reject)"""
        try:
            transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
            if not transaction:
                return False

            user = User.query.get(transaction.user_id)
            if not user:
                return False

            if status == "completed":
                if transaction.type == "deposit":
                    user.balance += transaction.amount
                transaction.status = "completed"
            elif status == "rejected":
                if transaction.type == "withdrawal":
                    user.balance += transaction.amount  # Refund
                transaction.status = "rejected"
            else:
                transaction.status = "failed"

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            return False

    def verify_deposit(self, tx_ref: str) -> Tuple[bool, str]:
        """Verify a deposit transaction"""
        try:
            # In test mode, auto-verify
            if self.TEST_MODE:
                self.process_transaction(tx_ref, "completed")
                return True, "Test payment verified successfully"

            transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
            if not transaction:
                return False, "Transaction not found"

            user = User.query.get(transaction.user_id)
            if not user:
                return False, "User not found"

            # Try Capa wallet verification first
            if user.wallet_id:
                success, message, data = self.capa.verify_transaction(tx_ref)
                if success:
                    self.process_transaction(tx_ref, "completed")
                    return True, "Payment verified successfully"

            # Fallback to Chapa verification
            success, message, data = self.chapa.verify_payment(tx_ref)
            if success:
                self.process_transaction(tx_ref, "completed")
                return True, "Payment verified successfully"
            return False, message

        except Exception as e:
            return False, f"Error verifying payment: {str(e)}"

    @staticmethod
    def get_transactions(user_id: int, limit: int = 10) -> list:
        """Get user's recent transactions"""
        return Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.created_at.desc()
        ).limit(limit).all()

    def get_wallet_balance(self, user_id: int) -> Tuple[bool, str, Optional[float]]:
        """Get user's Capa wallet balance"""
        try:
            user = User.query.get(user_id)
            if not user or not user.wallet_id:
                return False, "User or wallet not found", None

            success, message, balance = self.capa.get_wallet_balance(user.wallet_id)
            return success, message, balance

        except Exception as e:
            return False, f"Error getting wallet balance: {str(e)}", None 