from app import app, db
from models import GameParticipant
from sqlalchemy import text

def migrate_choice_time():
    with app.app_context():
        # Add choice_time column and rename move to choice
        with db.engine.connect() as conn:
            # Check if move column exists
            conn.execute(text("""
                ALTER TABLE game_participants 
                RENAME COLUMN move TO choice;
            """))
            
            # Add choice_time column if it doesn't exist
            conn.execute(text("""
                ALTER TABLE game_participants 
                ADD COLUMN choice_time TIMESTAMP;
            """))
            
            # Update choice_time for existing records
            conn.execute(text("""
                UPDATE game_participants 
                SET choice_time = move_time 
                WHERE choice_time IS NULL AND move_time IS NOT NULL;
            """))
            
            # Drop old move_time column
            conn.execute(text("""
                ALTER TABLE game_participants 
                DROP COLUMN move_time;
            """))
            
            conn.commit()
            
        print("Migration completed successfully!")

if __name__ == "__main__":
    migrate_choice_time() 