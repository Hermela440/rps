# models.py
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.sql import func
from extensions import db

class User(db.Model):
    """User model for storing player information"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    username = db.Column(db.String(32), unique=True, nullable=False)
    balance = db.Column(db.Numeric(10, 2), default=0.0)
    games_played = db.Column(db.Integer, default=0)
    games_won = db.Column(db.Integer, default=0)
    total_winnings = db.Column(db.Numeric(10, 2), default=0.0)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    games = db.relationship('GameParticipant', back_populates='user')
    transactions = db.relationship('Transaction', back_populates='user')
    withdrawals = db.relationship('WithdrawalRequest', back_populates='user')
    
    def __repr__(self):
        return f'<User {self.username}>'

class Game(db.Model):
    """Game model for storing RPS game information"""
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='waiting')  # waiting, active, completed, cancelled
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    participants = db.relationship('GameParticipant', back_populates='game')
    winner = db.relationship('User', foreign_keys=[winner_id])
    
    def __repr__(self):
        return f'<Game {self.id}>'

class GameParticipant(db.Model):
    """Model for storing game participants and their moves"""
    __tablename__ = 'game_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    move = db.Column(db.String(10), nullable=True)  # rock, paper, scissors
    move_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, left
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    game = db.relationship('Game', back_populates='participants')
    user = db.relationship('User', back_populates='games')
    
    def __repr__(self):
        return f'<GameParticipant {self.user_id} in Game {self.game_id}>'

class Transaction(db.Model):
    """Model for storing all financial transactions"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdraw, game_win, game_loss, bonus
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    reference_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', back_populates='transactions')
    
    def __repr__(self):
        return f'<Transaction {self.id} ({self.transaction_type})>'

class WithdrawalRequest(db.Model):
    """Model for storing withdrawal requests"""
    __tablename__ = 'withdrawal_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', back_populates='withdrawals')
    
    def __repr__(self):
        return f'<WithdrawalRequest {self.id}>'

class DailyStats(db.Model):
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    total_games = db.Column(db.Integer, default=0)
    total_players = db.Column(db.Integer, default=0)
    total_volume = db.Column(db.Numeric(10, 2), default=0.0)
    house_earnings = db.Column(db.Numeric(10, 2), default=0.0)
    new_users = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    
    @classmethod
    def get_or_create(cls, date):
        stats = cls.query.filter_by(date=date).first()
        if not stats:
            stats = cls(date=date)
            db.session.add(stats)
            db.session.commit()
        return stats

class Cooldown(db.Model):
    """Model for storing command cooldowns per user"""
    __tablename__ = 'cooldowns'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    command_name = db.Column(db.String(50), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with User
    user = db.relationship('User', backref=db.backref('cooldowns', lazy=True))
    
    def is_expired(self) -> bool:
        """Check if the cooldown has expired"""
        return datetime.utcnow() >= self.expires_at
    
    @classmethod
    def get_active_cooldown(cls, user_id: int, command_name: str) -> 'Cooldown':
        """Get active cooldown for a user and command if it exists"""
        return cls.query.filter_by(
            user_id=user_id,
            command_name=command_name
        ).filter(
            cls.expires_at > datetime.utcnow()
        ).first()
    
    @classmethod
    def create_cooldown(cls, user_id: int, command_name: str, duration_seconds: int = 60) -> 'Cooldown':
        """Create a new cooldown for a user and command"""
        cooldown = cls(
            user_id=user_id,
            command_name=command_name,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds)
        )
        db.session.add(cooldown)
        db.session.commit()
        return cooldown
