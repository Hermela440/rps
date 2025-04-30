# models.py
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.sql import func
from extensions import db

class User(db.Model):
    """User model for the RPS game"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

class Room(db.Model):
    """Game room model"""
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    bet_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    message_id = db.Column(db.BigInteger)  # For live status updates
    chat_id = db.Column(db.BigInteger)     # For live status updates
    
    # Relationships
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='created_rooms', foreign_keys=[creator_id])
    players = db.relationship('RoomPlayer', backref='room', lazy='dynamic')

class RoomPlayer(db.Model):
    """Model for room players and their moves"""
    __tablename__ = 'room_players'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    move = db.Column(db.String(10))  # rock, paper, scissors
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    move_made_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='room_participations')

class Transaction(db.Model):
    """Model for storing financial transactions"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # deposit, bet, win
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    reference_id = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='transactions')

class WithdrawalRequest(db.Model):
    """Model for storing withdrawal requests"""
    __tablename__ = 'withdrawal_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    wallet_address = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
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
