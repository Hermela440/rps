from app import create_app, init_db
from extensions import db
from models import User
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_db_connection():
    """Test database connection and print user information"""
    try:
        # Create test application
        app = create_app()
        
        with app.app_context():
            # Initialize database
            init_db()
            
            # Test basic connection
            result = db.session.execute(text('SELECT 1')).scalar()
            logger.info(f"Database connection test result: {result}")
            
            # Test User table access
            users = User.query.all()
            logger.info(f"Found {len(users)} users in database")
            for user in users:
                logger.info(f"User: {user.username}, ID: {user.id}, Balance: {user.balance}")
            
            return True
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_db_connection()
    if success:
        logger.info("Database test completed successfully")
    else:
        logger.error("Database test failed") 