"""Main Flask application"""
import sqlalchemy_patch  # Import patch before SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import text
from extensions import db, migrate
import os
import logging
from account_routes import account_bp
from payment_routes import payment_bp
from admin.routes import admin_bp
from webhooks import webhooks
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

# Import models before init_db to avoid NameError
from models import User, Room, RoomPlayer, Transaction, WithdrawalRequest, DailyStats, Cooldown

def init_db(app):
    """Initialize the database"""
    try:
        # Create database directory if it doesn't exist
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            LOGGER.info(f"Created database directory: {db_dir}")
        
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            LOGGER.info("Created all tables")
            
            # Test database connection
            db.session.execute(text('SELECT 1'))
            LOGGER.info("Database connection test successful")
            
            # Create initial admin user if none exists
            try:
                admin = User.query.filter_by(is_admin=True).first()
                if not admin:
                    admin = User(
                        telegram_id=123456789,  # Default admin ID
                        username='admin',
                        full_name='System Administrator',
                        email='admin@system.local',
                        password='admin123',  # Default admin password
                        balance=0.0,
                        wins=0,
                        losses=0,
                        is_admin=True,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(admin)
                    db.session.commit()
                    LOGGER.info("Initial admin user created")
            except Exception as e:
                LOGGER.warning(f"Could not query admin user, may need to run migrations: {e}")
            
            LOGGER.info("Database initialized successfully")
            
    except Exception as e:
        LOGGER.error(f"Failed to initialize database: {e}")
        raise

def create_app(config_class=Config):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    app.register_blueprint(webhooks, url_prefix='/webhooks')
    app.register_blueprint(account_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(admin_bp)
    
    # Initialize database
    with app.app_context():
        init_db(app)
    
    return app

# Create the Flask application
app = create_app()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None
    if not user_id:
        flash('You must be logged in to make a deposit.', 'danger')
        return render_template('deposit.html', user=None, test_mode=app.config['TEST_MODE'])

    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            from payments import PaymentSystem
            valid, message = PaymentSystem.validate_amount(amount, 'deposit')
            if not valid:
                flash(message, 'danger')
                return render_template('deposit.html', user=user, test_mode=app.config['TEST_MODE'])

            from payment_service import PaymentService
            payment_service = PaymentService()
            success, result = payment_service.create_deposit(user_id, amount)

            if success:
                if isinstance(result, dict) and 'checkout_url' in result:
                    return redirect(result['checkout_url'])
                flash(f'Test deposit of ETB {amount:.2f} completed successfully!', 'success')
                return redirect(url_for('profile'))
            else:
                flash(result, 'danger')
                return render_template('deposit.html', user=user, test_mode=app.config['TEST_MODE'])

        except ValueError:
            flash('Invalid amount.', 'danger')
            return render_template('deposit.html', user=user, test_mode=app.config['TEST_MODE'])
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('deposit.html', user=user, test_mode=app.config['TEST_MODE'])

    return render_template('deposit.html', user=user, test_mode=app.config['TEST_MODE'])

@app.route('/process_payment/<int:transaction_id>')
def process_payment(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    # Implement payment processing logic here
    return render_template('process_payment.html', transaction=transaction)

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if request.method == 'POST':
        amount = request.form.get('amount')
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')
        
        if not all([amount, bank_name, account_number]):
            flash('Please fill in all fields', 'error')
            return redirect(url_for('withdraw'))
        
        try:
            amount = Decimal(amount)
            if amount < Decimal('50.00'):
                flash('Minimum withdrawal amount is ETB 50.00', 'error')
                return redirect(url_for('withdraw'))
            if amount > Decimal('10000.00'):
                flash('Maximum withdrawal amount is ETB 10000.00', 'error')
                return redirect(url_for('withdraw'))
            
            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                user_id=1,  # Replace with actual user ID
                amount=amount,
                bank_name=bank_name,
                account_number=account_number,
                status='pending'
            )
            db.session.add(withdrawal)
            
            # Create corresponding transaction
            transaction = Transaction(
                user_id=1,  # Replace with actual user ID
                amount=-amount,  # Negative amount for withdrawals
                transaction_type='withdraw',
                status='pending',
                reference_id=f"WD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            )
            db.session.add(transaction)
            
            db.session.commit()
            flash('Withdrawal request submitted successfully', 'success')
            return redirect(url_for('index'))
            
        except (ValueError, decimal.InvalidOperation):
            flash('Invalid amount', 'error')
            return redirect(url_for('withdraw'))
    
    return render_template('withdraw.html')

@app.route('/admin')
def admin_dashboard():
    # Get system stats
    total_users = User.query.count()
    total_games = Room.query.count()
    total_volume = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.status == 'completed',
        Transaction.transaction_type.in_(['deposit', 'withdraw'])
    ).scalar() or Decimal('0')
    
    # Get recent transactions
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    # Get pending withdrawals
    pending_withdrawals = WithdrawalRequest.query.filter_by(status='pending').all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_games=total_games,
                         total_volume=total_volume,
                         recent_transactions=recent_transactions,
                         pending_withdrawals=pending_withdrawals)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
