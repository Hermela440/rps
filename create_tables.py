from app import app, db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest, DailyStats, Cooldown

def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_db() 