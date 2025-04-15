#!/usr/bin/env python3
"""
This script disables all cooldowns in the database
"""

from app import app, db
from models import Cooldown
from datetime import datetime

def disable_all_cooldowns():
    """Delete all cooldowns from the database"""
    with app.app_context():
        count = Cooldown.query.delete()
        db.session.commit()
        print(f"Deleted {count} cooldown records")
        print("All cooldowns have been disabled")

if __name__ == "__main__":
    disable_all_cooldowns() 