# models.py
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey, Numeric, func, BigInteger
from sqlalchemy.orm import relationship
from extensions import db

class User(db.Model):
    """User model for the RPS game"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    subscription_plan = db.Column(db.String(50), default='basic')
    balance = db.Column(db.Float, default=0.0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    wallet_id = db.Column(db.String(255), unique=True, nullable=True)  # Capa wallet ID
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    created_rooms = db.relationship('GameRoom', backref='creator', lazy=True, foreign_keys='GameRoom.created_by')
    participations = db.relationship('Participant', backref='user', lazy=True, cascade='all, delete-orphan')
    referrals_made = db.relationship('Referral', backref='referrer', lazy=True, foreign_keys='Referral.referrer_id')
    referred_by = db.relationship('Referral', backref='referred', lazy=True, foreign_keys='Referral.referred_id')

class Room(db.Model):
    """Game room model"""
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    bet_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    message_id = db.Column(db.BigInteger)
    chat_id = db.Column(db.BigInteger)
    
    # Relationships
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='owned_rooms', foreign_keys=[creator_id])
    players = db.relationship('RoomPlayer', backref='room', lazy='dynamic')

class RoomPlayer(db.Model):
    """Model for room players and their moves"""
    __tablename__ = 'room_players'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    move = db.Column(db.String(10))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    move_made_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='room_participations')

class Transaction(db.Model):
    """Transaction model for deposits and withdrawals"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tx_ref = db.Column(db.String(255), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'deposit' or 'withdrawal'
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'pending', 'completed', 'failed'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    
    def __repr__(self):
        return f'<Transaction {self.tx_ref}>'

class WithdrawalRequest(db.Model):
    """Model for storing withdrawal requests"""
    __tablename__ = 'withdrawal_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
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
    def get_active_cooldown(cls, user_id: int, command_name: str):
        """Get active cooldown for a user and command if it exists"""
        return cls.query.filter_by(
            user_id=user_id,
            command_name=command_name
        ).filter(
            cls.expires_at > datetime.utcnow()
        ).first()
    
    @classmethod
    def create_cooldown(cls, user_id: int, command_name: str, duration_seconds: int = 60):
        """Create a new cooldown for a user and command"""
        cooldown = cls(
            user_id=user_id,
            command_name=command_name,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds)
        )
        db.session.add(cooldown)
        db.session.commit()
        return cooldown

class GameRoom(db.Model):
    __tablename__ = 'game_rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True)
    bet_amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='waiting')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    participants = db.relationship('Participant', backref='room', lazy=True, cascade='all, delete-orphan')

class Participant(db.Model):
    __tablename__ = 'participants'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    room_id = db.Column(db.Integer, db.ForeignKey('game_rooms.id', ondelete='CASCADE'))
    move = db.Column(db.String(20))
    is_winner = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=func.now())

class Referral(db.Model):
    __tablename__ = 'referrals'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    created_at = db.Column(db.DateTime, default=func.now())
    bonus_paid = db.Column(db.Boolean, default=False)

class Game(db.Model):
    """Game model for tracking individual games"""
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, in_progress, completed
    min_players = db.Column(db.Integer, default=3)
    max_players = db.Column(db.Integer, default=3)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=func.now())
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('created_games', lazy=True))
    winner = db.relationship('User', foreign_keys=[winner_id], backref=db.backref('won_games', lazy=True))
    participants = db.relationship('GameParticipant', backref='game', lazy=True)

class GameParticipant(db.Model):
    """Game participant model for tracking player moves and results"""
    __tablename__ = 'game_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    move = db.Column(db.String(10))  # rock, paper, scissors
    result = db.Column(db.String(10))  # win, lose, draw
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('game_participations', lazy=True))