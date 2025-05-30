"""Webhook handler for Chapa payment callbacks"""
from flask import Blueprint, request, jsonify
from models import User, Transaction
from extensions import db
from payment_service import PaymentService
from services.user import UserService
import hmac
import hashlib
import json
import logging
from config import CHAPA_SECRET_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
callback_bp = Blueprint('callback', __name__)

# Initialize services
payment_service = PaymentService()
user_service = UserService()

def verify_chapa_signature(payload: str, signature: str) -> bool:
    """Verify Chapa webhook signature"""
    try:
        # Create HMAC SHA-256 hash
        expected_signature = hmac.new(
            CHAPA_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False

@callback_bp.route('/callback', methods=['POST'])
def handle_callback():
    """Handle Chapa payment callback"""
    try:
        # Get request data
        payload = request.get_data(as_text=True)
        signature = request.headers.get('Chapa-Signature')
        
        # Verify signature
        if not verify_chapa_signature(payload, signature):
            logger.warning("Invalid signature in callback")
            return jsonify({"status": "error", "message": "Invalid signature"}), 401
        
        # Parse payload
        data = json.loads(payload)
        tx_ref = data.get('tx_ref')
        status = data.get('status')
        
        if not tx_ref or not status:
            logger.warning("Missing required fields in callback")
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            logger.warning(f"Transaction not found: {tx_ref}")
            return jsonify({"status": "error", "message": "Transaction not found"}), 404
        
        # Get user
        user = User.query.get(transaction.user_id)
        if not user:
            logger.warning(f"User not found for transaction: {tx_ref}")
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        # Process transaction based on status
        if status == 'success':
            try:
                # Update transaction status
                transaction.status = 'completed'
                
                # Update user balance
                success = user_service.update_balance(
                    user.id,
                    transaction.amount,
                    'deposit'
                )
                
                if not success:
                    logger.error(f"Failed to update balance for user {user.id}")
                    return jsonify({
                        "status": "error",
                        "message": "Failed to update balance"
                    }), 500
                
                # Commit changes
                db.session.commit()
                
                logger.info(f"Successfully processed payment for tx_ref: {tx_ref}")
                return jsonify({
                    "status": "success",
                    "message": "Payment processed successfully"
                })
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error processing payment: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": "Error processing payment"
                }), 500
                
        elif status == 'failed':
            # Update transaction status
            transaction.status = 'failed'
            db.session.commit()
            
            logger.info(f"Payment failed for tx_ref: {tx_ref}")
            return jsonify({
                "status": "success",
                "message": "Payment marked as failed"
            })
            
        else:
            logger.warning(f"Unknown status in callback: {status}")
            return jsonify({
                "status": "error",
                "message": "Unknown status"
            }), 400
            
    except Exception as e:
        logger.error(f"Error in callback handler: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500 