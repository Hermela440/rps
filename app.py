from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from decimal import Decimal
from datetime import datetime, timedelta
from extensions import db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest
import os

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rps_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_123')

# Initialize extensions
db.init_app(app)

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
    total_games = Game.query.count()
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
    app.run(debug=True)
