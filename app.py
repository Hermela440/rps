from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import text
from extensions import db, migrate
import os
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rps_game.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False}  # Required for SQLite
    }
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    return app

# Create the Flask application
app = create_app()

# Import models after db initialization to avoid circular imports
from models import User, Room, RoomPlayer, Transaction, WithdrawalRequest, DailyStats, Cooldown

def init_db():
    """Initialize the database"""
    try:
        # Create database directory if it doesn't exist
        db_dir = os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            LOGGER.info("Created database directory")
        
        # Drop all tables if they exist
        with app.app_context():
            db.drop_all()
            LOGGER.info("Dropped existing tables")
        
        # Create all tables
        with app.app_context():
            db.create_all()
            LOGGER.info("Created all tables")
            
            # Test database connection
            db.session.execute(text('SELECT 1'))
            LOGGER.info("Database connection test successful")
            
            # Create initial admin user if none exists
            admin = User.query.filter_by(is_admin=True).first()
            if not admin:
                admin = User(
                    telegram_id=123456789,  # Replace with actual admin Telegram ID
                    username='admin',
                    balance=0.0,
                    wins=0,
                    losses=0,
                    is_admin=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(admin)
                db.session.commit()
                LOGGER.info("Initial admin user created")
            
            LOGGER.info("Database initialized successfully")
            
    except Exception as e:
        LOGGER.error(f"Failed to initialize database: {e}")
        raise

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount = request.form.get('amount')
        if not amount:
            flash('Please enter an amount', 'error')
            return redirect(url_for('deposit'))
        
        try:
            amount = Decimal(amount)
            if amount < Decimal('10.00'):
                flash('Minimum deposit amount is ETB 10.00', 'error')
                return redirect(url_for('deposit'))
            if amount > Decimal('1000.00'):
                flash('Maximum deposit amount is ETB 1000.00', 'error')
                return redirect(url_for('deposit'))
            
            # Create a pending transaction
            transaction = Transaction(
                user_id=1,  # Replace with actual user ID
                amount=amount,
                transaction_type='deposit',
                status='pending',
                reference_id=f"DEP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            )
            db.session.add(transaction)
            db.session.commit()
            
            # Redirect to payment processing
            return redirect(url_for('process_payment', transaction_id=transaction.id))
            
        except (ValueError, decimal.InvalidOperation):
            flash('Invalid amount', 'error')
            return redirect(url_for('deposit'))
    
    return render_template('deposit.html')

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
    with app.app_context():
        init_db()  # Initialize database only when running the app directly
    app.run(debug=True)
