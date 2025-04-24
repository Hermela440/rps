"""Payment routes for handling Chapa callbacks and success"""
from flask import Blueprint, request, jsonify, redirect, url_for
from payment_service import PaymentService
from app import app

payment_bp = Blueprint('payment', __name__)

@payment_bp.route('/payment/callback', methods=['POST'])
def payment_callback():
    """Handle Chapa webhook callback"""
    # Verify signature
    signature = request.headers.get('X-Chapa-Signature')
    if not signature:
        return jsonify({'status': 'error', 'message': 'No signature provided'}), 400
    
    # Get raw request body
    payload = request.get_data()
    if not PaymentService.verify_webhook_signature(signature, payload):
        return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400
    
    # Process the webhook
    data = request.json
    tx_ref = data.get('tx_ref')
    if not tx_ref:
        return jsonify({'status': 'error', 'message': 'No transaction reference'}), 400
    
    # Verify the payment
    success, message = PaymentService.verify_payment(tx_ref)
    if success:
        return jsonify({'status': 'success', 'message': message}), 200
    else:
        return jsonify({'status': 'error', 'message': message}), 400

@payment_bp.route('/payment/success')
def payment_success():
    """Handle successful payment redirect"""
    tx_ref = request.args.get('tx_ref')
    if not tx_ref:
        return "Payment verification failed: No transaction reference", 400
    
    # Verify the payment
    success, message = PaymentService.verify_payment(tx_ref)
    if success:
        return f"Payment successful! {message}"
    else:
        return f"Payment verification failed: {message}", 400

@payment_bp.route('/deposit', methods=['POST'])
def initiate_deposit():
    """Initiate a deposit"""
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    if not user_id or not amount:
        return jsonify({
            'status': 'error',
            'message': 'Missing user_id or amount'
        }), 400
    
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid amount'
        }), 400
    
    success, message, checkout_url = PaymentService.initialize_payment(user_id, amount)
    if success:
        return jsonify({
            'status': 'success',
            'message': message,
            'checkout_url': checkout_url
        })
    else:
        return jsonify({
            'status': 'error',
            'message': message
        }), 400

# Register the blueprint
app.register_blueprint(payment_bp) 