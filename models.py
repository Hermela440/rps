# models.py
from datetime import datetime
from extensions import db  # ⬅️ This is now safe
from sqlalchemy import func

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    games_played = db.Column(db.Integer, default=0)
    games_won = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    games = db.relationship('GameParticipant', back_populates='user')
    transactions = db.relationship('Transaction', back_populates='user')

    def __repr__(self):
        return f"<User {self.username}>"


class Game(db.Model):
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='waiting')
    bet_amount = db.Column(db.Float, nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    participants = db.relationship('GameParticipant', back_populates='game')
    winner = db.relationship('User', foreign_keys=[winner_id])

    def __repr__(self):
        return f"<Game {self.id} - {self.status}>"


class GameParticipant(db.Model):
    __tablename__ = 'game_participants'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    choice = db.Column(db.String(10), nullable=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    game = db.relationship('Game', back_populates='participants')
    user = db.relationship('User', back_populates='games')

    def __repr__(self):
        return f"<GameParticipant {self.user_id} in Game {self.game_id}>"


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    reference_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='transactions')

    def __repr__(self):
        return f"<Transaction {self.id} - {self.transaction_type} - {self.amount}>"


class WithdrawalRequest(db.Model):
    __tablename__ = 'withdrawal_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id])
    admin = db.relationship('User', foreign_keys=[processed_by])
    transaction = db.relationship('Transaction')

    def __repr__(self):
        return f"<WithdrawalRequest {self.id} - {self.amount} - {self.status}>"


class Cooldown(db.Model):
    __tablename__ = 'cooldowns'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    command = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User')

    def __repr__(self):
        return f"<Cooldown {self.user_id} - {self.command} - {self.expires_at}>"
