"""Payment routes for handling deposits and withdrawals"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from decimal import Decimal
from extensions import db
from models import Transaction
from payment_service import PaymentService
from config import TEST_MODE

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

@payment_bp.route('/methods')
def payment_methods():
    """Get available payment methods"""
    return jsonify({
        "methods": [
            {
                "id": "chapa",
                "name": "Chapa",
                "description": "Pay with Chapa",
                "icon": "chapa-icon.png"
            }
        ]
    })

@payment_bp.route('/deposit', methods=['GET'])
@login_required
def deposit():
    """Show deposit form"""
    return render_template('deposit.html', user=current_user)

@payment_bp.route('/deposit', methods=['POST'])
@login_required
def process_deposit():
    """Process deposit request"""
    try:
        amount = Decimal(request.form.get('amount', '0'))
        if amount <= 0:
            flash('Invalid amount', 'error')
            return redirect(url_for('payment.deposit'))
        
        # Initialize payment
        success, message, checkout_url = PaymentService.initialize_payment(
            current_user.id,
            float(amount),
            test_mode=TEST_MODE
        )
        
        if success:
            if checkout_url:
                return redirect(checkout_url)
            flash('Deposit completed successfully', 'success')
            return redirect(url_for('payment.success'))
        else:
            flash(message, 'error')
            return redirect(url_for('payment.deposit'))
            
    except Exception as e:
        flash(f'Error processing deposit: {str(e)}', 'error')
        return redirect(url_for('payment.deposit'))

@payment_bp.route('/initialize', methods=['POST'])
@login_required
def initialize_payment():
    """Initialize a new payment"""
    try:
        data = request.get_json()
        amount = Decimal(str(data.get('amount', 0)))
        
        if amount <= 0:
            return jsonify({
                'success': False,
                'message': 'Invalid amount'
            }), 400
        
        success, message, checkout_url = PaymentService.initialize_payment(
            current_user.id,
            float(amount),
            test_mode=TEST_MODE
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'checkout_url': checkout_url
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@payment_bp.route('/callback', methods=['POST'])
def payment_callback():
    """Handle Chapa webhook callback"""
    try:
        data = request.get_json()
        tx_ref = data.get('tx_ref')
        
        if not tx_ref:
            return jsonify({'status': 'error', 'message': 'Missing transaction reference'}), 400
        
        success, message, payment_data = PaymentService.verify_payment(tx_ref)
        
        if success:
            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@payment_bp.route('/success')
@login_required
def success():
    """Handle successful payment redirect"""
    tx_ref = request.args.get('tx_ref')
    if tx_ref:
        success, message, payment_data = PaymentService.verify_payment(tx_ref)
        if success:
            flash('Payment completed successfully', 'success')
        else:
            flash(message, 'error')
    return redirect(url_for('payment.complete'))

@payment_bp.route('/complete')
@login_required
def complete():
    """Show payment completion page"""
    return render_template('payment_complete.html', user=current_user)

@payment_bp.route('/error')
@login_required
def error():
    """Show payment error page"""
    return render_template('payment_error.html', user=current_user) 