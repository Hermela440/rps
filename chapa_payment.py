"""Chapa payment integration using the latest API"""
import chapa
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from decimal import Decimal
import json
import logging

from app import db
from models import User, Transaction
from config import (
    CHAPA_SECRET_KEY,
    CHAPA_API_URL,
    MIN_DEPOSIT_AMOUNT,
    MAX_DEPOSIT_AMOUNT
)

# Initialize Chapa client
chapa.api_key = CHAPA_SECRET_KEY
logger = logging.getLogger(__name__)

class ChapaPayment:
    """Handle Chapa payment operations"""
    
    @staticmethod
    def initialize_payment(
        user_id: int,
        amount: float,
        email: str,
        first_name: str,
        last_name: str,
        callback_url: str,
        return_url: str,
        customization: Optional[Dict] = None,
        preferred_payment: Optional[str] = None,
        split_payments: Optional[List[Dict]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Initialize a payment transaction with Chapa
        
        Args:
            user_id: The user ID
            amount: The deposit amount
            email: User's email
            first_name: User's first name
            last_name: User's last name
            callback_url: URL for payment callback
            return_url: URL to redirect after payment
            customization: Optional payment page customization
            preferred_payment: Preferred payment method (e.g., 'telebirr', 'cbe_birr')
            split_payments: List of split payment details
            
        Returns:
            tuple: (success, message, checkout_url)
        """
        try:
            # Validate amount
            if amount < MIN_DEPOSIT_AMOUNT:
                return False, f"Minimum deposit amount is ETB {MIN_DEPOSIT_AMOUNT}", None
            if amount > MAX_DEPOSIT_AMOUNT:
                return False, f"Maximum deposit amount is ETB {MAX_DEPOSIT_AMOUNT}", None
            
            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal(str(amount)),
                type="deposit",
                status="pending",
                created_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            # Prepare payment data
            payment_data = {
                "amount": str(amount),
                "currency": "ETB",
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "tx_ref": transaction.reference,
                "callback_url": callback_url,
                "return_url": return_url,
                "customization": customization or {
                    "title": "RPS Game Deposit",
                    "description": f"Deposit ETB {amount} to your RPS game wallet"
                }
            }
            
            # Add preferred payment method if specified
            if preferred_payment:
                payment_data["preferred_payment"] = preferred_payment
            
            # Add split payments if specified
            if split_payments:
                payment_data["split_payments"] = split_payments
            
            # Initialize payment with Chapa
            response = chapa.initialize(**payment_data)
            
            if response.get("status") == "success":
                # Store additional payment data
                transaction.payment_data = json.dumps({
                    "checkout_url": response["data"]["checkout_url"],
                    "preferred_payment": preferred_payment,
                    "split_payments": split_payments
                })
                db.session.commit()
                
                return True, "Payment initialized successfully", response["data"]["checkout_url"]
            else:
                # Update transaction status
                transaction.status = "failed"
                transaction.payment_data = json.dumps({"error": response.get("message", "Unknown error")})
                db.session.commit()
                return False, "Failed to initialize payment", None
                
        except Exception as e:
            logger.error(f"Error initializing payment: {str(e)}")
            db.session.rollback()
            return False, f"Error initializing payment: {str(e)}", None
    
    @staticmethod
    def verify_payment(reference: str) -> Tuple[bool, str, Optional[Dict]]:
        """Verify a payment transaction
        
        Args:
            reference: Transaction reference ID
            
        Returns:
            tuple: (success, message, payment_data)
                - success: Whether the verification was successful
                - message: Human-readable message about the status
                - payment_data: Additional payment details if successful
        """
        try:
            # Get transaction
            transaction = Transaction.query.filter_by(reference=reference).first()
            if not transaction:
                return False, "Transaction not found", None
            
            if transaction.status == "completed":
                return True, "Payment already verified", {
                    "amount": float(transaction.amount),
                    "currency": "ETB",
                    "status": "completed",
                    "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None
                }
            
            # Verify with Chapa
            response = chapa.verify(reference)
            
            if response.get("status") == "success":
                payment_data = response.get("data", {})
                payment_status = payment_data.get("status", "").lower()
                
                if payment_status == "success":
                    # Update transaction
                    transaction.status = "completed"
                    transaction.completed_at = datetime.utcnow()
                    transaction.payment_data = json.dumps(payment_data)
                    
                    # Update user balance
                    user = User.query.get(transaction.user_id)
                    user.balance += transaction.amount
                    
                    db.session.commit()
                    
                    return True, "Payment verified successfully", {
                        "amount": float(transaction.amount),
                        "currency": "ETB",
                        "status": "completed",
                        "completed_at": transaction.completed_at.isoformat(),
                        "payment_method": payment_data.get("payment_type"),
                        "payment_details": payment_data
                    }
                elif payment_status == "pending":
                    transaction.payment_data = json.dumps(payment_data)
                    db.session.commit()
                    return False, "Payment is still pending", {
                        "status": "pending",
                        "payment_details": payment_data
                    }
                else:
                    transaction.status = "failed"
                    transaction.payment_data = json.dumps({"error": payment_status})
                    db.session.commit()
                    return False, f"Payment failed: {payment_status}", {
                        "status": "failed",
                        "payment_details": payment_data
                    }
            else:
                transaction.status = "failed"
                transaction.payment_data = json.dumps({"error": response.get("message", "Unknown error")})
                db.session.commit()
                return False, "Payment verification failed", {
                    "status": "failed",
                    "error": response.get("message", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            db.session.rollback()
            return False, f"Error verifying payment: {str(e)}", None
    
    @staticmethod
    def get_supported_payment_methods() -> List[Dict]:
        """Get list of supported payment methods
        
        Returns:
            list: List of supported payment methods with their details
        """
        try:
            response = chapa.get_payment_methods()
            if response.get("status") == "success":
                return response.get("data", [])
            return []
        except Exception as e:
            logger.error(f"Error getting payment methods: {str(e)}")
            return []
    
    @staticmethod
    def get_transaction_logs(reference: str) -> List[Dict]:
        """Get transaction logs
        
        Args:
            reference: Transaction reference ID
            
        Returns:
            list: List of transaction logs
        """
        try:
            response = chapa.get_transaction_logs(reference)
            if response.get("status") == "success":
                return response.get("data", [])
            return []
        except Exception as e:
            logger.error(f"Error getting transaction logs: {str(e)}")
            return [] 