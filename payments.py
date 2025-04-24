import uuid
from datetime import datetime
import requests
from typing import Dict, Tuple, Optional, Union
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
    CHAPA_API_URL,
    DAILY_DEPOSIT_LIMIT,
    DAILY_WITHDRAW_LIMIT
)

from logging import getLogger

LOGGER = getLogger(__name__)

class ChapaWallet:
    @staticmethod
    def create_payment_link(amount, email, callback_url, reference):
        """Create a Chapa payment link"""
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "email": email,
            "first_name": "User",
            "last_name": "Player",
            "tx_ref": reference,
            "callback_url": callback_url,
            "return_url": callback_url,
            "customization[title]": "RPS Game Deposit",
            "customization[description]": "Deposit funds to play Rock Paper Scissors"
        }
        
        try:
            response = requests.post(
                f"{CHAPA_API_URL}/transaction/initialize",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, {
                        "payment_url": data["data"]["checkout_url"],
                        "reference": reference
                    }
            
            return False, "Payment initialization failed"
            
        except Exception as e:
            LOGGER.error(f"Chapa API error: {e}")
            return False, "Payment service temporarily unavailable"

    @staticmethod
    def verify_payment(reference):
        """Verify a Chapa payment"""
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
        }
        
        try:
            response = requests.get(
                f"{CHAPA_API_URL}/transaction/verify/{reference}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, data["data"]
            
            return False, "Payment verification failed"
            
        except Exception as e:
            LOGGER.error(f"Chapa verification error: {e}")
            return False, "Verification service unavailable"

class PaymentSystem:
    """Handle all payment-related operations using Chapa"""
    
    @staticmethod
    def generate_transaction_id() -> str:
        """Generate a unique transaction ID"""
        return str(uuid.uuid4())

    @staticmethod
    def validate_amount(amount: float, transaction_type: str) -> Tuple[bool, str]:
        """Validate transaction amount against limits"""
        if transaction_type == 'deposit':
            if amount < MIN_DEPOSIT_AMOUNT:
                return False, f"Minimum deposit amount is ETB {MIN_DEPOSIT_AMOUNT}"
            if amount > MAX_DEPOSIT_AMOUNT:
                return False, f"Maximum deposit amount is ETB {MAX_DEPOSIT_AMOUNT}"
        elif transaction_type == 'withdraw':
            if amount < MIN_WITHDRAW_AMOUNT:
                return False, f"Minimum withdrawal amount is ETB {MIN_WITHDRAW_AMOUNT}"
            if amount > MAX_WITHDRAW_AMOUNT:
                return False, f"Maximum withdrawal amount is ETB {MAX_WITHDRAW_AMOUNT}"
        return True, ""

    @staticmethod
    def check_daily_limit(user_id: int, amount: float, transaction_type: str) -> Tuple[bool, str]:
        """Check if transaction would exceed daily limits"""
        # Skip daily limits in test mode
        return True, ""

    @classmethod
    def create_deposit(cls, user_id: int, amount: float) -> Tuple[bool, Union[Dict, str]]:
        """Create a deposit request"""
        try:
            # Validate amount
            valid, message = cls.validate_amount(amount, 'deposit')
            if not valid:
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                transaction_type='deposit',
                status='completed',  # Auto-complete in test mode
                reference_id=f"DEP_{user_id}_{int(datetime.utcnow().timestamp())}"
            )
            db.session.add(transaction)

            # Update user balance immediately in test mode
            user.balance += amount
            
            db.session.commit()
            return True, {
                "message": f"Test deposit of ETB {amount:.2f} completed successfully",
                "reference": transaction.reference_id
            }

        except Exception as e:
            LOGGER.error(f"Error creating deposit: {e}")
            db.session.rollback()
            return False, "Error processing deposit request"

            # Create Chapa payment request
            headers = {
                "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "amount": str(amount),
                "currency": "ETB",
                "email": f"{user.username}@rpsbot.com",
                "first_name": user.username,
                "last_name": "Player",
                "tx_ref": transaction.reference_id,
                "callback_url": f"{CHAPA_API_URL}/webhook/deposit",
                "return_url": f"{CHAPA_API_URL}/deposit/success",
                "customization": {
                    "title": "RPS Game Deposit",
                    "description": f"Deposit ETB {amount} to your RPS game wallet"
                }
            }

            response = requests.post(
                f"{CHAPA_API_URL}/transaction/initialize",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, {
                    "payment_url": data["data"]["checkout_url"],
                    "reference": transaction.reference_id
                }
            else:
                LOGGER.error(f"Chapa API error: {response.text}")
                return False, "Payment service temporarily unavailable"

        except Exception as e:
            LOGGER.error(f"Error creating deposit: {e}")
            db.session.rollback()
            return False, "Error processing deposit request"

    @classmethod
    def process_deposit_callback(cls, reference: str, status: str) -> bool:
        """Process deposit callback from Chapa"""
        try:
            transaction = Transaction.query.filter_by(reference_id=reference).first()
            if not transaction:
                LOGGER.error(f"Transaction not found for reference: {reference}")
                return False

            if status == "success":
                # Update transaction
                transaction.status = "completed"
                transaction.completed_at = datetime.utcnow()

                # Update user balance
                user = User.query.get(transaction.user_id)
                user.balance += transaction.amount

                db.session.commit()
                return True
            else:
                transaction.status = "failed"
                db.session.commit()
                return False

        except Exception as e:
            LOGGER.error(f"Error processing deposit callback: {e}")
            db.session.rollback()
            return False

    @classmethod
    def create_withdrawal(cls, user_id: int, amount: float, wallet_address: str) -> Tuple[bool, Union[Dict, str]]:
        """Create a withdrawal request"""
        try:
            # Validate amount
            valid, message = cls.validate_amount(amount, 'withdraw')
            if not valid:
                return False, message

            # Check daily limit
            valid, message = cls.check_daily_limit(user_id, amount, 'withdraw')
            if not valid:
                return False, message

            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=-amount,  # Negative for withdrawals
                transaction_type='withdraw',
                status='pending',
                reference_id=f"WD_{user_id}_{int(datetime.utcnow().timestamp())}"
            )
            db.session.add(transaction)

            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                user_id=user_id,
                amount=amount,
                wallet_address=wallet_address,
                transaction_id=transaction.id
            )
            db.session.add(withdrawal)

            # Update user balance
            user.balance -= amount

            db.session.commit()
            return True, {
                "message": "Withdrawal request created successfully",
                "reference": transaction.reference_id
            }

        except Exception as e:
            LOGGER.error(f"Error creating withdrawal: {e}")
            db.session.rollback()
            return False, "Error processing withdrawal request"

    @classmethod
    def process_withdrawal(cls, request_id: int, status: str, admin_id: int) -> bool:
        """Process a withdrawal request (admin only)"""
        try:
            withdrawal = WithdrawalRequest.query.get(request_id)
            if not withdrawal:
                return False

            transaction = Transaction.query.get(withdrawal.transaction_id)
            if not transaction:
                return False

            if status == "approved":
                # Call Chapa transfer API
                headers = {
                    "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "amount": str(withdrawal.amount),
                    "currency": "ETB",
                    "wallet_address": withdrawal.wallet_address,
                    "reference": transaction.reference_id
                }

                response = requests.post(
                    f"{CHAPA_API_URL}/transfer",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    withdrawal.status = "completed"
                    withdrawal.processed_at = datetime.utcnow()
                    transaction.status = "completed"
                    transaction.completed_at = datetime.utcnow()
                    db.session.commit()
                    return True
                else:
                    LOGGER.error(f"Chapa transfer error: {response.text}")
                    return False

            elif status == "rejected":
                # Refund the amount to user
                user = User.query.get(withdrawal.user_id)
                user.balance += withdrawal.amount
                
                withdrawal.status = "rejected"
                withdrawal.processed_at = datetime.utcnow()
                transaction.status = "failed"
                
                db.session.commit()
                return True

        except Exception as e:
            LOGGER.error(f"Error processing withdrawal: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def get_transactions(user_id, limit=10):
        """Get user's recent transactions"""
        return Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def verify_deposit(reference):
        """Verify and complete a deposit"""
        try:
            transaction = Transaction.query.filter_by(reference_id=reference).first()
            if not transaction:
                return False, "Transaction not found"
            
            if transaction.status != 'pending':
                return True, "Transaction already processed"
            
            # Verify with Chapa
            success, result = ChapaWallet.verify_payment(reference)
            if success:
                # Update user balance
                user = User.query.get(transaction.user_id)
                user.balance += Decimal(str(abs(transaction.amount)))
                
                # Update transaction
                transaction.status = 'completed'
                transaction.completed_at = datetime.utcnow()
                db.session.commit()
                
                return True, {
                    "message": f"Deposit of ETB {abs(transaction.amount):.2f} completed successfully"
                }
            
            return False, result
            
        except Exception as e:
            LOGGER.error(f"Deposit verification error: {e}")
            db.session.rollback()
            return False, "Error verifying deposit"

    @staticmethod
    def get_pending_withdrawals():
        """Get all pending withdrawal requests"""
        return WithdrawalRequest.query.filter_by(
            status='pending'
        ).order_by(
            WithdrawalRequest.created_at.asc()
        ).all()
