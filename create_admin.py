from app import app, db
from models import User
from datetime import datetime

def create_admin_user():
    with app.app_context():
        # Check if admin already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists!")
            return
        
        # Create admin user
        admin = User(
            username='admin',
            balance=1000.0,
            is_admin=True,
            created_at=datetime.utcnow()
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Created admin user with ID: {admin.id}")

if __name__ == '__main__':
    create_admin_user() 