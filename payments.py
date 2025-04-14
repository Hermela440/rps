from datetime import datetime
from app import db
from models import User, Transaction, WithdrawalRequest
from config import MIN_DEPOSIT_AMOUNT, MAX_DEPOSIT_AMOUNT, MIN_WITHDRAW_AMOUNT, MAX_WITHDRAW_AMOUNT, LOGGER

class PaymentSystem:
    """Handle virtual currency transactions"""
    
    @staticmethod
    def deposit(user_id, amount):
        """Process a deposit into a user's wallet"""
        if amount < MIN_DEPOSIT_AMOUNT:
            return False, f"Minimum deposit amount is ${MIN_DEPOSIT_AMOUNT}."
        
        if amount > MAX_DEPOSIT_AMOUNT:
            return False, f"Maximum deposit amount is ${MAX_DEPOSIT_AMOUNT}."
        
        # In a real system, this would interface with a payment gateway
        # For now, we'll simulate a successful payment
        
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='deposit',
            status='completed',
            reference_id=f"DEP-{int(datetime.utcnow().timestamp())}",
            completed_at=datetime.utcnow()
        )
        
        # Update user balance
        user.balance += amount
        
        db.session.add(transaction)
        db.session.commit()
        
        return True, f"Successfully deposited ${amount:.2f} to your wallet."
    
    @staticmethod
    def request_withdrawal(user_id, amount):
        """Request a withdrawal from a user's wallet"""
        if amount < MIN_WITHDRAW_AMOUNT:
            return False, f"Minimum withdrawal amount is ${MIN_WITHDRAW_AMOUNT}."
        
        if amount > MAX_WITHDRAW_AMOUNT:
            return False, f"Maximum withdrawal amount is ${MAX_WITHDRAW_AMOUNT}."
        
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        if user.balance < amount:
            return False, f"Insufficient balance. You have ${user.balance:.2f}."
        
        # Create pending transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=-amount,  # Negative as it's a withdrawal
            transaction_type='withdraw',
            status='pending',
            reference_id=f"WDR-{int(datetime.utcnow().timestamp())}"
        )
        db.session.add(transaction)
        db.session.flush()  # Get the transaction ID before committing
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest(
            user_id=user_id,
            amount=amount,
            transaction_id=transaction.id,
            status='pending'
        )
        
        # Hold the amount from user's balance
        user.balance -= amount
        
        db.session.add(withdrawal)
        db.session.commit()
        
        return True, f"Withdrawal request for ${amount:.2f} has been submitted and is awaiting approval."
    
    @staticmethod
    def approve_withdrawal(withdrawal_id, admin_id):
        """Approve a withdrawal request"""
        withdrawal = WithdrawalRequest.query.get(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal request not found."
        
        if withdrawal.status != 'pending':
            return False, f"This withdrawal has already been {withdrawal.status}."
        
        # In a real system, this would interface with a payment gateway
        # For now, we'll simulate a successful payout
        
        # Update withdrawal request
        withdrawal.status = 'approved'
        withdrawal.processed_at = datetime.utcnow()
        withdrawal.processed_by = admin_id
        
        # Update related transaction
        transaction = Transaction.query.get(withdrawal.transaction_id)
        transaction.status = 'completed'
        transaction.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return True, f"Withdrawal request of ${withdrawal.amount:.2f} has been approved."
    
    @staticmethod
    def reject_withdrawal(withdrawal_id, admin_id):
        """Reject a withdrawal request"""
        withdrawal = WithdrawalRequest.query.get(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal request not found."
        
        if withdrawal.status != 'pending':
            return False, f"This withdrawal has already been {withdrawal.status}."
        
        # Update withdrawal request
        withdrawal.status = 'rejected'
        withdrawal.processed_at = datetime.utcnow()
        withdrawal.processed_by = admin_id
        
        # Update related transaction
        transaction = Transaction.query.get(withdrawal.transaction_id)
        transaction.status = 'rejected'
        
        # Refund the amount to user's balance
        user = User.query.get(withdrawal.user_id)
        user.balance += withdrawal.amount
        
        db.session.commit()
        
        return True, f"Withdrawal request of ${withdrawal.amount:.2f} has been rejected and the amount has been refunded."
    
    @staticmethod
    def get_transactions(user_id, limit=10):
        """Get recent transactions for a user"""
        return Transaction.query.filter_by(
            user_id=user_id
        ).order_by(
            Transaction.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_pending_withdrawals():
        """Get all pending withdrawal requests"""
        return WithdrawalRequest.query.filter_by(
            status='pending'
        ).order_by(
            WithdrawalRequest.created_at.asc()
        ).all()
