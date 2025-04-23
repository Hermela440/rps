from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import User, Game, Transaction, WithdrawalRequest, GameParticipant
from payments import PaymentSystem
from config import LOGGER
from decimal import Decimal
from typing import Dict, List, Optional


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
    def get_system_stats() -> Dict:
        """Get system-wide statistics"""
        try:
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            
            stats = {
                "total_users": User.query.count(),
                "new_users_24h": User.query.filter(User.created_at >= day_ago).count(),
                "total_games": Game.query.count(),
                "games_24h": Game.query.filter(Game.created_at >= day_ago).count(),
                "active_users_24h": User.query.filter(User.last_active >= day_ago).count(),
                "pending_withdrawals": WithdrawalRequest.query.filter_by(status='pending').count()
            }
            
            # Calculate transaction volumes
            total_volume = db.session.query(
                db.func.sum(Transaction.amount)
            ).filter(
                Transaction.status == 'completed',
                Transaction.transaction_type.in_(['deposit', 'withdrawal'])
            ).scalar() or 0
            
            volume_24h = db.session.query(
                db.func.sum(Transaction.amount)
            ).filter(
                Transaction.status == 'completed',
                Transaction.transaction_type.in_(['deposit', 'withdrawal']),
                Transaction.created_at >= day_ago
            ).scalar() or 0
            
            stats["total_volume"] = float(total_volume)
            stats["volume_24h"] = float(volume_24h)
            
            return stats
            
        except Exception as e:
            LOGGER.error(f"Error getting system stats: {e}")
            return {}

    @staticmethod
    def search_user(query: str) -> List[User]:
        """Search for users by username or telegram ID"""
        try:
            # Try to convert query to telegram_id
            try:
                telegram_id = int(query)
                user_by_id = User.query.filter_by(telegram_id=telegram_id).first()
                if user_by_id:
                    return [user_by_id]
            except ValueError:
                pass
            
            # Search by username
            return User.query.filter(User.username.ilike(f"%{query}%")).all()
            
        except Exception as e:
            LOGGER.error(f"Error searching users: {e}")
            return []

    @staticmethod
    def get_user_details(user_id: int) -> Optional[Dict]:
        """Get detailed information about a user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return None
            
            # Get recent transactions
            transactions = Transaction.query.filter_by(
                user_id=user_id
            ).order_by(
                Transaction.created_at.desc()
            ).limit(5).all()
            
            # Get recent games
            games = Game.query.join(
                GameParticipant
            ).filter(
                GameParticipant.user_id == user_id
            ).order_by(
                Game.created_at.desc()
            ).limit(5).all()
            
            return {
                "user": user,
                "recent_transactions": transactions,
                "recent_games": games,
                "total_wagered": sum(g.bet_amount for g in games),
                "total_games": len(games)
            }
            
        except Exception as e:
            LOGGER.error(f"Error getting user details: {e}")
            return None

    @staticmethod
    def adjust_balance(user_id: int, amount: float, reason: str) -> bool:
        """Adjust a user's balance (add or subtract funds)"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                transaction_type='admin_adjustment',
                status='completed',
                reference_id=f"ADJ_{datetime.utcnow().timestamp()}",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                notes=reason
            )
            
            # Update user balance
            user.balance += Decimal(str(amount))
            
            db.session.add(transaction)
            db.session.commit()
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error adjusting balance: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def get_recent_games(limit: int = 10) -> List[Game]:
        """Get recent games with their participants"""
        try:
            return Game.query.order_by(Game.created_at.desc()).limit(limit).all()
        except Exception as e:
            LOGGER.error(f"Error getting recent games: {e}")
            return []

    @staticmethod
    def get_recent_users(limit: int = 10) -> List[User]:
        """Get recently created user accounts"""
        try:
            return User.query.order_by(User.created_at.desc()).limit(limit).all()
        except Exception as e:
            LOGGER.error(f"Error getting recent users: {e}")
            return []

    @staticmethod
    def get_pending_withdrawals() -> List[WithdrawalRequest]:
        """Get pending withdrawal requests"""
        try:
            return WithdrawalRequest.query.filter_by(
                status='pending'
            ).order_by(
                WithdrawalRequest.created_at.asc()
            ).all()
        except Exception as e:
            LOGGER.error(f"Error getting pending withdrawals: {e}")
            return []

    @staticmethod
    def toggle_admin(user_id: int) -> bool:
        """Toggle admin status for a user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            user.is_admin = not user.is_admin
            db.session.commit()
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error toggling admin status: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def cancel_game(game_id: int) -> bool:
        """Cancel an active game and refund bets"""
        try:
            game = Game.query.get(game_id)
            if not game or game.status not in ['waiting', 'active']:
                return False
            
            # Refund bets to participants
            participants = GameParticipant.query.filter_by(game_id=game_id).all()
            for participant in participants:
                user = User.query.get(participant.user_id)
                user.balance += Decimal(str(game.bet_amount))
                
                # Create refund transaction
                transaction = Transaction(
                    user_id=user.id,
                    amount=game.bet_amount,
                    transaction_type='game_refund',
                    status='completed',
                    reference_id=f"REFUND_{game_id}_{datetime.utcnow().timestamp()}",
                    created_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    notes=f"Game #{game_id} cancelled by admin"
                )
                db.session.add(transaction)
            
            # Mark game as cancelled
            game.status = 'cancelled'
            game.completed_at = datetime.utcnow()
            db.session.commit()
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Error cancelling game: {e}")
            db.session.rollback()
            return False
