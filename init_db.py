from app import app, db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest, DailyStats, Cooldown

def init_db():
    """Initialize database with all required tables"""
    with app.app_context():
        print("Creating database tables if they don't exist...")
        db.create_all()  # Create tables only if they don't exist
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_db() 