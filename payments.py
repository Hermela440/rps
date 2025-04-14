from datetime import datetime
from app import db
from models import User, Transaction, WithdrawalRequest
from config import MIN_DEPOSIT_AMOUNT, MAX_DEPOSIT_AMOUNT, MIN_WITHDRAW_AMOUNT, MAX_WITHDRAW_AMOUNT, LOGGER
from capa_wallet import CapaWallet

class PaymentSystem:
    """Handle virtual currency transactions"""
    
    @staticmethod
    def deposit(user_id, amount):
        """Process a deposit into a user's wallet using Capa Wallet"""
        if amount < MIN_DEPOSIT_AMOUNT:
            return False, f"Minimum deposit amount is ${MIN_DEPOSIT_AMOUNT}."
        
        if amount > MAX_DEPOSIT_AMOUNT:
            return False, f"Maximum deposit amount is ${MAX_DEPOSIT_AMOUNT}."
        
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        # Generate payment link with Capa Wallet
        description = f"Deposit to RPS Arena - User {user.username}"
        success, payment_data = CapaWallet.generate_payment_link(amount, user_id, description)
        
        if not success:
            LOGGER.error(f"Failed to generate payment link: {payment_data}")
            return False, "Payment service temporarily unavailable. Please try again later."
        
        # Get payment data safely
        payment_id = ""
        payment_url = ""
        expires_at = ""
        
        if isinstance(payment_data, dict):
            payment_id = payment_data.get('payment_id', f"DEP-{int(datetime.utcnow().timestamp())}")
            payment_url = payment_data.get('payment_url', "")
            expires_at = payment_data.get('expires_at', "")
        else:
            payment_id = f"DEP-{int(datetime.utcnow().timestamp())}"
        
        # Create pending transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='deposit',
            status='pending',
            reference_id=payment_id
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # In a production app, we'd redirect to the payment URL
        # For our demo, we'll simulate instant payment to avoid the actual payment flow
        PaymentSystem._process_successful_payment(transaction.id)
        
        return True, {
            "message": f"Please complete your payment of ${amount:.2f} using Capa Wallet",
            "payment_url": payment_url,
            "payment_id": payment_id,
            "expires_at": expires_at
        }
        
    @staticmethod
    def _process_successful_payment(transaction_id):
        """Process a successful payment (used for demo purposes)"""
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            LOGGER.error(f"Transaction {transaction_id} not found")
            return False
            
        if transaction.status != 'pending':
            return False  # Already processed
            
        # Update transaction status
        transaction.status = 'completed'
        transaction.completed_at = datetime.utcnow()
        
        # Update user balance
        user = User.query.get(transaction.user_id)
        user.balance += transaction.amount
        
        db.session.commit()
        return True
    
    @staticmethod
    def request_withdrawal(user_id, amount):
        """Request a withdrawal from a user's wallet using Capa Wallet"""
        if amount < MIN_WITHDRAW_AMOUNT:
            return False, f"Minimum withdrawal amount is ${MIN_WITHDRAW_AMOUNT}."
        
        if amount > MAX_WITHDRAW_AMOUNT:
            return False, f"Maximum withdrawal amount is ${MAX_WITHDRAW_AMOUNT}."
        
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        if user.balance < amount:
            return False, f"Insufficient balance. You have ${user.balance:.2f}."
        
        # Create a pending transaction record
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
        
        # In a real application, we'd show a form to collect the user's Capa Wallet address
        # For demo purposes, we'll assume the request is submitted and awaiting admin approval
        
        return True, {
            "message": f"Withdrawal request for ${amount:.2f} has been submitted and is awaiting approval.",
            "transaction_id": transaction.id,
            "withdrawal_id": withdrawal.id,
            "status": "pending"
        }
    
    @staticmethod
    def approve_withdrawal(withdrawal_id, admin_id):
        """Approve a withdrawal request using Capa Wallet"""
        withdrawal = WithdrawalRequest.query.get(withdrawal_id)
        if not withdrawal:
            return False, "Withdrawal request not found."
        
        if withdrawal.status != 'pending':
            return False, f"This withdrawal has already been {withdrawal.status}."
        
        user = User.query.get(withdrawal.user_id)
        if not user:
            return False, "User not found."
            
        # In a real application, we would have collected the user's Capa Wallet address
        # For demo purposes, we'll use a placeholder address
        wallet_address = "capa_wallet_address_placeholder"
        
        # Process withdrawal through Capa Wallet
        description = f"Withdrawal from RPS Arena - User {user.username}"
        success, result = CapaWallet.process_withdrawal(
            user.id, 
            withdrawal.amount,
            wallet_address,
            description
        )
        
        if not success:
            LOGGER.error(f"Failed to process withdrawal: {result}")
            return False, "Payment service temporarily unavailable. Please try again later."
        
        # Update withdrawal request
        withdrawal.status = 'approved'
        withdrawal.processed_at = datetime.utcnow()
        withdrawal.processed_by = admin_id
        
        # Update related transaction
        transaction = Transaction.query.get(withdrawal.transaction_id)
        transaction.status = 'completed'
        transaction.completed_at = datetime.utcnow()
        if isinstance(result, dict) and 'withdrawal_id' in result:
            transaction.reference_id = result['withdrawal_id']
        
        db.session.commit()
        
        return True, f"Withdrawal request of ${withdrawal.amount:.2f} has been approved and processed through Capa Wallet."
    
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
