import os
import hmac
import hashlib
import logging
import sqlite3
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_db_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect('rps_game.db', timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def verify_chapa_signature(payload, signature):
    """Verify Chapa webhook signature."""
    try:
        secret = os.getenv("CHAPA_WEBHOOK_SECRET")
        if not secret or not signature:
            return False
            
        computed_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

@app.route('/chapa-webhook', methods=['POST'])
def chapa_webhook():
    """Handle Chapa payment webhook notifications."""
    try:
        # Verify signature
        signature = request.headers.get('Chapa-Signature')
        if not verify_chapa_signature(request.get_data(), signature):
            logger.warning("Invalid webhook signature")
            return jsonify({"status": "error", "message": "Invalid signature"}), 401

        # Parse webhook data
        data = request.json
        tx_ref = data.get('tx_ref')
        status = data.get('status')
        amount = float(data.get('amount', 0))
        
        if not tx_ref or not status:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Handle different transaction types
        if tx_ref.startswith('deposit_'):
            return handle_deposit_webhook(tx_ref, status, amount)
        elif tx_ref.startswith('withdraw_'):
            return handle_withdrawal_webhook(tx_ref, status, amount)
        else:
            logger.warning(f"Unknown transaction type: {tx_ref}")
            return jsonify({"status": "error", "message": "Unknown transaction type"}), 400

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

def handle_deposit_webhook(tx_ref, status, amount):
    """Handle deposit webhook notifications."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500

        try:
            c = conn.cursor()
            
            # Get transaction details
            c.execute('''
                SELECT user_id, status as current_status
                FROM transactions
                WHERE tx_ref = ?
            ''', (tx_ref,))
            result = c.fetchone()
            
            if not result:
                return jsonify({"status": "error", "message": "Transaction not found"}), 404
                
            user_id = result['user_id']
            current_status = result['current_status']
            
            # Only process if not already completed
            if current_status != 'completed':
                if status == 'success':
                    c.execute('BEGIN TRANSACTION')
                    
                    # Update transaction status
                    c.execute('''
                        UPDATE transactions
                        SET status = 'completed'
                        WHERE tx_ref = ?
                    ''', (tx_ref,))
                    
                    # Update user balance
                    c.execute('''
                        UPDATE users
                        SET balance = balance + ?
                        WHERE user_id = ?
                    ''', (amount, user_id))
                    
                    conn.commit()
                    
                    # Try to send notification to user (implement in main bot)
                    logger.info(f"Deposit completed: {tx_ref} for user {user_id}")
                    
                elif status == 'failed':
                    c.execute('''
                        UPDATE transactions
                        SET status = 'failed'
                        WHERE tx_ref = ?
                    ''', (tx_ref,))
                    conn.commit()
                    
                    logger.info(f"Deposit failed: {tx_ref}")
            
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error in deposit webhook: {e}")
            return jsonify({"status": "error", "message": "Database error"}), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Deposit webhook error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

def handle_withdrawal_webhook(tx_ref, status, amount):
    """Handle withdrawal webhook notifications."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500

        try:
            c = conn.cursor()
            
            # Get transaction details
            c.execute('''
                SELECT user_id, status as current_status, amount
                FROM transactions
                WHERE tx_ref = ?
            ''', (tx_ref,))
            result = c.fetchone()
            
            if not result:
                return jsonify({"status": "error", "message": "Transaction not found"}), 404
                
            user_id = result['user_id']
            current_status = result['current_status']
            
            # Only process if pending
            if current_status == 'pending':
                if status == 'failed':
                    c.execute('BEGIN TRANSACTION')
                    
                    # Update transaction status
                    c.execute('''
                        UPDATE transactions
                        SET status = 'failed'
                        WHERE tx_ref = ?
                    ''', (tx_ref,))
                    
                    # Refund the amount
                    c.execute('''
                        UPDATE users
                        SET balance = balance + ?
                        WHERE user_id = ?
                    ''', (abs(amount), user_id))
                    
                    # Add refund transaction
                    c.execute('''
                        INSERT INTO transactions (user_id, type, amount, balance_after, tx_ref, status)
                        SELECT ?, 'refund', ?, balance, ?, 'completed'
                        FROM users WHERE user_id = ?
                    ''', (user_id, abs(amount), f"refund_{tx_ref}", user_id))
                    
                    conn.commit()
                    logger.info(f"Withdrawal failed and refunded: {tx_ref}")
                    
                elif status == 'success':
                    c.execute('''
                        UPDATE transactions
                        SET status = 'completed'
                        WHERE tx_ref = ?
                    ''', (tx_ref,))
                    conn.commit()
                    logger.info(f"Withdrawal completed: {tx_ref}")
            
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error in withdrawal webhook: {e}")
            return jsonify({"status": "error", "message": "Database error"}), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Withdrawal webhook error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port) 