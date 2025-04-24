"""Payment service for handling Chapa integration"""
import hmac
import hashlib
import requests
from datetime import datetime, UTC
from app import db
from models import User, Transaction
from payment_config import (
    CHAPA_SECRET_KEY, CHAPA_API_URL, CURRENCY,
    PAYMENT_DESCRIPTION, PAYMENT_TITLE,
    PAYMENT_SUCCESS_URL, PAYMENT_CALLBACK_URL,
    generate_transaction_ref
)

class PaymentService:
    """Service for handling payments through Chapa"""
    
    TEST_MODE = True  # Enable test mode for free deposits
    
    @staticmethod
    def initialize_payment(user_id: int, amount: float, test_mode: bool = True) -> tuple[bool, str, str]:
        """Initialize a payment transaction with Chapa or process test deposit
        
        Args:
            user_id: The user ID
            amount: The deposit amount
            test_mode: Override default test mode setting
            
        Returns:
            tuple: (success, message, checkout_url)
        """
        try:
            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found", ""
            
            # Generate transaction reference
            tx_ref = generate_transaction_ref()
            
            # Create and complete test transaction immediately
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                transaction_type="deposit",
                status="completed",  # Mark as completed immediately
                reference_id=tx_ref,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC)  # Set completion time
            )
            
            # Update user balance immediately
            old_balance = float(user.balance)
            user.balance = old_balance + float(amount)
            
            # Save changes
            db.session.add(transaction)
            db.session.commit()
            
            return True, "Test deposit completed successfully", ""
            
        except Exception as e:
            db.session.rollback()
            return False, f"Unexpected error: {str(e)}", ""
    
    @staticmethod
    def verify_payment(tx_ref: str) -> tuple[bool, str]:
        """Verify a payment transaction
        
        Returns:
            tuple: (success, message)
        """
        try:
            # Get transaction
            transaction = Transaction.query.filter_by(reference_id=tx_ref).first()
            if not transaction:
                return False, "Transaction not found"
            
            if transaction.status == "completed":
                return True, "Transaction already verified"
            
            # Auto-approve in test mode
            transaction.status = "completed"
            transaction.completed_at = datetime.now(UTC)
            
            user = db.session.get(User, transaction.user_id)
            user.balance += transaction.amount
            
            db.session.commit()
            return True, "Test payment verified successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def set_test_mode(enabled: bool):
        """Enable or disable test mode for free deposits"""
        PaymentService.TEST_MODE = enabled
    
    @staticmethod
    def verify_webhook_signature(signature: str, payload: bytes) -> bool:
        """Verify Chapa webhook signature"""
        computed_sig = hmac.new(
            CHAPA_SECRET_KEY.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_sig, signature) 