"""Webhook handlers for payment callbacks"""
from flask import Blueprint, request, jsonify
from payment_service import PaymentService
from chapa_integration import ChapaPayment
from extensions import db
from models import Transaction, User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
webhooks = Blueprint('webhooks', __name__)

# Initialize services
payment_service = PaymentService()
chapa = ChapaPayment()

@webhooks.route('/callback', methods=['POST'])
def chapa_callback():
    """Handle Chapa payment callback"""
    try:
        # Get transaction reference
        tx_ref = request.args.get('tx_ref')
        if not tx_ref:
            logger.error("No transaction reference provided")
            return jsonify({"status": "error", "message": "No transaction reference"}), 400

        # Verify payment with Chapa
        success, message, data = chapa.verify_payment(tx_ref)
        
        if success:
            # Process successful payment
            if payment_service.process_transaction(tx_ref, "completed"):
                logger.info(f"Payment completed successfully for tx_ref: {tx_ref}")
                return jsonify({"status": "success", "message": "Payment processed"}), 200
            else:
                logger.error(f"Failed to process payment for tx_ref: {tx_ref}")
                return jsonify({"status": "error", "message": "Failed to process payment"}), 500
        else:
            # Mark payment as failed
            if payment_service.process_transaction(tx_ref, "failed"):
                logger.info(f"Payment marked as failed for tx_ref: {tx_ref}")
                return jsonify({"status": "error", "message": message}), 200
            else:
                logger.error(f"Failed to mark payment as failed for tx_ref: {tx_ref}")
                return jsonify({"status": "error", "message": "Failed to update transaction"}), 500

    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@webhooks.route('/success', methods=['GET'])
def payment_success():
    """Handle successful payment redirect"""
    try:
        tx_ref = request.args.get('tx_ref')
        if not tx_ref:
            return "Invalid transaction reference", 400

        # Get transaction
        transaction = Transaction.query.filter_by(tx_ref=tx_ref).first()
        if not transaction:
            return "Transaction not found", 404

        # Get user
        user = User.query.get(transaction.user_id)
        if not user:
            return "User not found", 404

        return f"""
        <html>
            <head>
                <title>Payment Successful</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .success {{ color: green; font-size: 24px; }}
                    .details {{ margin: 20px; }}
                </style>
            </head>
            <body>
                <div class="success">✅ Payment Successful!</div>
                <div class="details">
                    <p>Amount: {transaction.amount} ETB</p>
                    <p>Reference: {tx_ref}</p>
                    <p>New Balance: {user.balance} ETB</p>
                </div>
                <p>You can close this window and return to the bot.</p>
            </body>
        </html>
        """

    except Exception as e:
        logger.error(f"Error in success page: {str(e)}")
        return "An error occurred", 500 