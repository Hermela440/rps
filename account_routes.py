"""Account management routes"""
from flask import Blueprint, request, jsonify, current_app, render_template
from werkzeug.security import generate_password_hash
from app import db
from models import User, Transaction
from chapa_payment import ChapaPayment
from config import MIN_DEPOSIT_AMOUNT
import logging

account_bp = Blueprint('account', __name__)
logger = logging.getLogger(__name__)

@account_bp.route('/account/create', methods=['GET'])
def create_account_form():
    """Render account creation form"""
    return render_template('create_account.html', min_deposit_amount=MIN_DEPOSIT_AMOUNT)

@account_bp.route('/account/create', methods=['POST'])
def create_account():
    """Create a new user account"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'full_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Check if username exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                'status': 'error',
                'message': 'Username already exists'
            }), 400
        
        # Check if email exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({
                'status': 'error',
                'message': 'Email already exists'
            }), 400
        
        # Validate password
        if len(data['password']) < 8:
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 8 characters'
            }), 400
        
        # Create user
        user = User(
            username=data['username'],
            email=data['email'],
            password=generate_password_hash(data['password']),
            full_name=data['full_name'],
            balance=0.00
        )
        db.session.add(user)
        db.session.commit()
        
        # Handle initial deposit if provided
        if 'initial_deposit' in data:
            try:
                amount = float(data['initial_deposit'])
                
                # Validate amount
                if amount < MIN_DEPOSIT_AMOUNT:
                    return jsonify({
                        'status': 'error',
                        'message': f'Minimum deposit amount is ETB {MIN_DEPOSIT_AMOUNT}'
                    }), 400
                
                # Initialize payment
                success, message, checkout_url = ChapaPayment.initialize_payment(
                    user_id=user.id,
                    amount=amount,
                    email=user.email,
                    first_name=user.full_name,
                    last_name='',
                    callback_url=request.url_root + 'payment/callback',
                    return_url=request.url_root + 'payment/success'
                )
                
                if not success:
                    return jsonify({
                        'status': 'error',
                        'message': message
                    }), 400
                
                return jsonify({
                    'status': 'success',
                    'message': 'Account created successfully',
                    'checkout_url': checkout_url
                }), 201
                
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid deposit amount'
                }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Account created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error creating account: {str(e)}'
        }), 500

@account_bp.route('/account/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    try:
        # Get user from token
        user = get_current_user()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized'
            }), 401
        
        return jsonify({
            'status': 'success',
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.full_name,
                'created_at': user.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting profile: {str(e)}'
        }), 500

@account_bp.route('/account/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    try:
        # Get user from token
        user = get_current_user()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized'
            }), 401
        
        data = request.get_json()
        
        # Update fields if provided
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'email' in data:
            # Check if email exists
            if User.query.filter_by(email=data['email']).first():
                return jsonify({
                    'status': 'error',
                    'message': 'Email already exists'
                }), 400
            user.email = data['email']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Profile updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error updating profile: {str(e)}'
        }), 500

def get_current_user():
    """Get current user from token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        token = auth_header.split(' ')[1]
        user_id = User.verify_token(token)
        if not user_id:
            return None
        
        return User.query.get(user_id)
    except:
        return None 