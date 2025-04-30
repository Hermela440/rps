"""Payment service for handling Chapa integration"""
import hmac
import hashlib
import requests
from datetime import datetime, timezone
from typing import Tuple
from extensions import db
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
    def initialize_payment(user_id: int, amount: float, test_mode: bool = True) -> Tuple[bool, str, str]:
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
            user = db.session.get(User, user_id)
            if not user:
                return False, "User not found", ""
            
            # Generate transaction reference
            tx_ref = generate_transaction_ref()
            
            # Use class test mode if not overridden
            is_test = test_mode if test_mode is not None else PaymentService.TEST_MODE
            
            if is_test:
                # Create and complete test transaction immediately
                transaction = Transaction(
                    user_id=user_id,
                    amount=amount,
                    transaction_type="deposit",
                    status="completed",  # Mark as completed immediately
                    reference_id=tx_ref,
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc)  # Set completion time
                )
                
                # Update user balance immediately
                old_balance = float(user.balance)
                user.balance = old_balance + float(amount)
                
                # Save changes
                db.session.add(transaction)
                db.session.commit()
                
                return True, "Test deposit completed successfully", ""
            else:
                # Create pending transaction
                transaction = Transaction(
                    user_id=user_id,
                    amount=amount,
                    transaction_type="deposit",
                    status="pending",
                    reference_id=tx_ref,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(transaction)
                db.session.commit()
                
                # Initialize real payment with Chapa
                payload = {
                    "amount": str(amount),
                    "currency": CURRENCY,
                    "email": "user@example.com",  # Replace with actual user email
                    "first_name": user.username,
                    "last_name": "",
                    "tx_ref": tx_ref,
                    "callback_url": PAYMENT_CALLBACK_URL,
                    "return_url": PAYMENT_SUCCESS_URL,
                    "customization[title]": PAYMENT_TITLE,
                    "customization[description]": PAYMENT_DESCRIPTION
                }
                
                headers = {
                    "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    f"{CHAPA_API_URL}/transaction/initialize",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return True, "Payment initialized", data["data"]["checkout_url"]
                
                return False, "Failed to initialize payment", ""
            
        except Exception as e:
            db.session.rollback()
            return False, f"Unexpected error: {str(e)}", ""
    
    @staticmethod
    def verify_payment(tx_ref: str) -> Tuple[bool, str]:
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
            
            if PaymentService.TEST_MODE:
                # Auto-approve in test mode
                transaction.status = "completed"
                transaction.completed_at = datetime.now(timezone.utc)
                
                user = db.session.get(User, transaction.user_id)
                user.balance += transaction.amount
                
                db.session.commit()
                return True, "Test payment verified successfully"
            else:
                # Verify with Chapa
                headers = {
                    "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
                }
                
                response = requests.get(
                    f"{CHAPA_API_URL}/transaction/verify/{tx_ref}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        transaction.status = "completed"
                        transaction.completed_at = datetime.now(timezone.utc)
                        
                        user = db.session.get(User, transaction.user_id)
                        user.balance += transaction.amount
                        
                        db.session.commit()
                        return True, "Payment verified successfully"
                
                return False, "Payment verification failed"
            
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