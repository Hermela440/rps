from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import User, Game, Transaction, WithdrawalRequest
from payments import PaymentSystem
from config import LOGGER


class AdminService:
    """Admin functionality for the RPS game"""
    
    @staticmethod
    def get_user_count():
        """Get total number of users"""
        return User.query.count()
    
    @staticmethod
    def get_game_count():
        """Get total number of games"""
        return Game.query.count()
    
    @staticmethod
    def get_total_transaction_volume():
        """Get total transaction volume"""
        return db.session.query(func.sum(Transaction.amount)).scalar() or 0
    
    @staticmethod
    def get_platform_revenue():
        """Get platform revenue from fees"""
        # This is a simplification - in a real system you'd calculate this more precisely
        return db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type == 'fee'
        ).scalar() or 0
    
    @staticmethod
    def get_recent_users(limit=10):
        """Get recently created users"""
        return User.query.order_by(
            User.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_recent_games(limit=10):
        """Get recently played games"""
        return Game.query.filter_by(
            status='completed'
        ).order_by(
            Game.completed_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_pending_withdrawals():
        """Get pending withdrawal requests"""
        return PaymentSystem.get_pending_withdrawals()
    
    @staticmethod
    def approve_withdrawal(withdrawal_id, admin_id):
        """Approve a withdrawal request"""
        return PaymentSystem.approve_withdrawal(withdrawal_id, admin_id)
    
    @staticmethod
    def reject_withdrawal(withdrawal_id, admin_id):
        """Reject a withdrawal request"""
        return PaymentSystem.reject_withdrawal(withdrawal_id, admin_id)
    
    @staticmethod
    def search_user(query):
        """Search for a user by username or ID"""
        if query.isdigit():
            # Search by ID
            user = User.query.get(int(query))
            return [user] if user else []
        else:
            # Search by username (partial match)
            return User.query.filter(User.username.like(f"%{query}%")).all()
    
    @staticmethod
    def get_user_details(user_id):
        """Get detailed information about a user"""
        user = User.query.get(user_id)
        if not user:
            return None
        
        # Get user's games
        games_played = Game.query.join(
            GameParticipant, Game.id == GameParticipant.game_id
        ).filter(
            GameParticipant.user_id == user_id
        ).count()
        
        # Get user's transactions
        transactions = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(
            Transaction.created_at.desc()
        ).limit(10).all()
        
        # Calculate win rate
        win_rate = (user.games_won / user.games_played) * 100 if user.games_played > 0 else 0
        
        return {
            'user': user,
            'games_played': games_played,
            'win_rate': win_rate,
            'transactions': transactions
        }
    
    @staticmethod
    def make_admin(user_id):
        """Make a user an admin"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        user.is_admin = True
        db.session.commit()
        
        return True, f"User {user.username} is now an admin."
    
    @staticmethod
    def remove_admin(user_id):
        """Remove admin privileges from a user"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found."
        
        user.is_admin = False
        db.session.commit()
        
        return True, f"User {user.username} is no longer an admin."
    
    @staticmethod
    def get_system_stats():
        """Get system statistics"""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # Total users
        total_users = User.query.count()
        new_users_24h = User.query.filter(User.created_at >= yesterday).count()
        
        # Total games
        total_games = Game.query.count()
        games_24h = Game.query.filter(Game.created_at >= yesterday).count()
        
        # Transaction volume
        total_volume = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type.in_(['deposit', 'withdraw', 'win'])
        ).scalar() or 0
        
        volume_24h = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type.in_(['deposit', 'withdraw', 'win']),
            Transaction.created_at >= yesterday
        ).scalar() or 0
        
        # Active users
        active_users_24h = User.query.filter(User.last_active >= yesterday).count()
        
        return {
            'total_users': total_users,
            'new_users_24h': new_users_24h,
            'total_games': total_games,
            'games_24h': games_24h,
            'total_volume': total_volume,
            'volume_24h': volume_24h,
            'active_users_24h': active_users_24h,
            'pending_withdrawals': WithdrawalRequest.query.filter_by(status='pending').count()
        }
