import uuid
from datetime import datetime
import requests
from typing import Dict, Tuple
from decimal import Decimal

from app import db
from models import User, Transaction, WithdrawalRequest
from config import (
    MIN_DEPOSIT_AMOUNT,
    MAX_DEPOSIT_AMOUNT,
    MIN_WITHDRAW_AMOUNT,
    MAX_WITHDRAW_AMOUNT,
    PLATFORM_FEE_PERCENT,
    CHAPA_SECRET_KEY,
    CHAPA_API_URL
)

from logging import getLogger

LOGGER = getLogger(__name__)

class PaymentSystem:
    """Handle all payment-related operations using Chapa"""
    
    @staticmethod
    def generate_transaction_id() -> str:
        """Generate a unique transaction ID"""
        return str(uuid.uuid4())

    @classmethod
    def deposit(cls, user_id: int, amount: float) -> Tuple[bool, Dict]:
        """Process a deposit request using Chapa"""
        try:
            # Validate amount
            if amount < MIN_DEPOSIT_AMOUNT:
                return False, {"error": f"Minimum deposit amount is ETB {MIN_DEPOSIT_AMOUNT}"}
            if amount > MAX_DEPOSIT_AMOUNT:
                return False, {"error": f"Maximum deposit amount is ETB {MAX_DEPOSIT_AMOUNT}"}

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, {"error": "User not found"}

            # Generate transaction ID
            tx_ref = cls.generate_transaction_id()

            # Create Chapa payment request
            headers = {
                "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "amount": str(amount),
                "currency": "ETB",
                "email": f"{user.telegram_id}@telegram.user",
                "first_name": user.username,
                "last_name": "User",
                "tx_ref": tx_ref,
                "callback_url": "https://your-domain.com/chapa/callback",  # Replace with your callback URL
                "return_url": "https://t.me/your_bot_username",  # Replace with your bot's username
                "customization": {
                    "title": "Rock Paper Scissors Deposit",
                    "description": f"Deposit ETB {amount:.2f} to your Rock Paper Scissors wallet"
                }
            }

            response = requests.post(
                f"{CHAPA_API_URL}/transaction/initialize",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                
                # Create pending transaction
                transaction = Transaction(
                    id=tx_ref,
                    user_id=user_id,
                    amount=amount,
                    transaction_type='deposit',
                    status='pending',
                    payment_provider='chapa',
                    payment_id=data['data']['reference'],
                    created_at=datetime.utcnow()
                )
                db.session.add(transaction)
                db.session.commit()

                return True, {
                    "payment_url": data['data']['checkout_url'],
                    "transaction_id": tx_ref,
                    "message": f"Please complete your payment of ETB {amount:.2f}"
                }
            else:
                LOGGER.error(f"Chapa API error: {response.text}")
                return False, {"error": "Payment service error"}

        except Exception as e:
            LOGGER.error(f"Deposit error: {e}")
            db.session.rollback()
            return False, {"error": "Internal server error"}

    @classmethod
    def verify_payment(cls, tx_ref: str) -> Tuple[bool, str]:
        """Verify payment status with Chapa"""
        try:
            headers = {
                "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
            }

            response = requests.get(
                f"{CHAPA_API_URL}/transaction/verify/{tx_ref}",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return cls.confirm_deposit(tx_ref, 'succeeded')
                else:
                    return cls.confirm_deposit(tx_ref, 'failed')
            else:
                LOGGER.error(f"Chapa verification error: {response.text}")
                return False, "Payment verification failed"

        except Exception as e:
            LOGGER.error(f"Payment verification error: {e}")
            return False, "Internal server error"

    @classmethod
    def confirm_deposit(cls, transaction_id: str, payment_status: str) -> Tuple[bool, str]:
        """Confirm a deposit after payment is completed"""
        try:
            transaction = Transaction.query.get(transaction_id)
            if not transaction or transaction.status != 'pending':
                return False, "Invalid transaction"

            if payment_status == 'succeeded':
                # Update transaction
                transaction.status = 'completed'
                transaction.completed_at = datetime.utcnow()

                # Update user balance
                user = User.query.get(transaction.user_id)
                user.balance += Decimal(str(transaction.amount))

                db.session.commit()
                return True, "Payment confirmed successfully"
            else:
                transaction.status = 'failed'
                db.session.commit()
                return False, "Payment failed"

        except Exception as e:
            LOGGER.error(f"Confirm deposit error: {e}")
            db.session.rollback()
            return False, "Internal server error"

    @classmethod
    def request_withdrawal(cls, user_id: int, amount: float, wallet_address: str) -> Tuple[bool, Dict]:
        """Process a withdrawal request"""
        try:
            # Validate amount
            if amount < MIN_WITHDRAW_AMOUNT:
                return False, {"error": f"Minimum withdrawal amount is ETB {MIN_WITHDRAW_AMOUNT}"}
            if amount > MAX_WITHDRAW_AMOUNT:
                return False, {"error": f"Maximum withdrawal amount is ETB {MAX_WITHDRAW_AMOUNT}"}

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, {"error": "User not found"}

            # Check balance
            if user.balance < Decimal(str(amount)):
                return False, {"error": "Insufficient balance"}

            # Generate withdrawal ID
            withdrawal_id = cls.generate_transaction_id()

            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                id=withdrawal_id,
                user_id=user_id,
                amount=amount,
                wallet_address=wallet_address,
                status='pending',
                created_at=datetime.utcnow()
            )

            # Create pending transaction
            transaction = Transaction(
                id=cls.generate_transaction_id(),
                user_id=user_id,
                amount=-amount,
                transaction_type='withdrawal',
                status='pending',
                created_at=datetime.utcnow()
            )

            # Deduct from user balance
            user.balance -= Decimal(str(amount))

            db.session.add(withdrawal)
            db.session.add(transaction)
            db.session.commit()

            return True, {
                "message": f"Withdrawal request for ETB {amount:.2f} has been submitted",
                "withdrawal_id": withdrawal_id
            }

        except Exception as e:
            LOGGER.error(f"Withdrawal request error: {e}")
            db.session.rollback()
            return False, {"error": "Internal server error"}

    @classmethod
    def process_withdrawal(cls, withdrawal_id: str, admin_id: int) -> Tuple[bool, str]:
        """Process a pending withdrawal request using Chapa"""
        try:
            withdrawal = WithdrawalRequest.query.get(withdrawal_id)
            if not withdrawal or withdrawal.status != 'pending':
                return False, "Invalid withdrawal request"

            # Get associated transaction
            transaction = Transaction.query.filter_by(
                user_id=withdrawal.user_id,
                amount=-withdrawal.amount,
                transaction_type='withdrawal',
                status='pending'
            ).first()

            if not transaction:
                return False, "Transaction not found"

            # Here you would integrate with Chapa's payout API
            # For now, we'll mark it as completed
            withdrawal.status = 'completed'
            withdrawal.processed_by = admin_id
            withdrawal.processed_at = datetime.utcnow()

            transaction.status = 'completed'
            transaction.completed_at = datetime.utcnow()

            db.session.commit()
            return True, "Withdrawal processed successfully"

        except Exception as e:
            LOGGER.error(f"Process withdrawal error: {e}")
            db.session.rollback()
            return False, "Internal server error"

    @staticmethod
    def get_transactions(user_id, limit=10):
        """Get recent transactions for a user"""
        return Transaction.query.filter_by(
            user_id=user_id
        ).order_by(
            Transaction.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_pending_withdrawals():
        """Get all pending withdrawal requests"""
        return WithdrawalRequest.query.filter_by(
            status='pending'
        ).order_by(
            WithdrawalRequest.created_at.asc()
        ).all()
