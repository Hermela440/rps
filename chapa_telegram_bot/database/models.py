"""Database models"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """User model"""
    __tablename__ = 'users'

    id: Mapped[int] = Column(Integer, primary_key=True)
    telegram_id: Mapped[int] = Column(Integer, unique=True, nullable=False)
    username: Mapped[str] = Column(String(255), nullable=True)
    full_name: Mapped[str] = Column(String(255), nullable=True)
    balance: Mapped[float] = Column(Float, default=0.0)
    is_admin: Mapped[bool] = Column(Boolean, default=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="user")

    def __repr__(self):
        return f"<User {self.username}>"

class Transaction(Base):
    """Transaction model"""
    __tablename__ = 'transactions'

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=False)
    tx_ref: Mapped[str] = Column(String(50), unique=True, nullable=False)
    type: Mapped[str] = Column(String(20), nullable=False)  # 'deposit' or 'withdrawal'
    amount: Mapped[float] = Column(Float, nullable=False)
    status: Mapped[str] = Column(String(20), default='pending')  # 'pending', 'completed', 'failed', 'rejected'
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction {self.tx_ref}>"

class WithdrawalRequest(Base):
    """Withdrawal request model"""
    __tablename__ = 'withdrawal_requests'

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount: Mapped[float] = Column(Float, nullable=False)
    wallet_address: Mapped[str] = Column(String(255), nullable=False)
    status: Mapped[str] = Column(String(20), default='pending')  # 'pending', 'completed', 'rejected'
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<WithdrawalRequest {self.id}>" 