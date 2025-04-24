from datetime import datetime
from app import db

class User(db.Model):
    """User model for the RPS game"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    games_played = db.Column(db.Integer, default=0)
    games_won = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    def __init__(self, username, balance=0.0):
        self.username = username
        self.balance = balance
        
    def __repr__(self):
        return f'<User {self.username}>' 