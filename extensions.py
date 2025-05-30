"""Flask extensions module"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Create extension instances
db = SQLAlchemy()
migrate = Migrate()
