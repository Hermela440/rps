from flask import Flask
from extensions import db
from routes import register_routes
import os
from config import DATABASE_URL, DEBUG, LOGGER

def create_app():
    app = Flask(__name__)
    
    # Use DATABASE_URL from config
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    app.config['DEBUG'] = DEBUG
    
    db.init_app(app)

    # Register routes
    register_routes(app)

    return app

app = create_app()

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    LOGGER.info("Database tables created/verified")

if __name__ == '__main__':
    app.run(debug=DEBUG)
