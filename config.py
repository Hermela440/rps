"""
Configuration settings for the RPS Arena application
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot token
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Admin users (list of telegram IDs)
ADMIN_USERS = [int(id) for id in os.getenv('ADMIN_USERS', '').split(',') if id]

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

# Game settings
BET_AMOUNT_DEFAULT = 10.0  # Default bet amount in ETB
MIN_DEPOSIT_AMOUNT = 10.0  # Minimum deposit amount in ETB
MAX_DEPOSIT_AMOUNT = 1000.0  # Maximum deposit amount in ETB
MIN_WITHDRAW_AMOUNT = 10.0  # Minimum withdrawal amount in ETB
MAX_WITHDRAW_AMOUNT = 1000.0  # Maximum withdrawal amount in ETB

# Cooldown settings (in seconds)
CREATE_ACCOUNT_COOLDOWN = 60
DELETE_ACCOUNT_COOLDOWN = 300
DEPOSIT_COOLDOWN = 60
WITHDRAW_COOLDOWN = 300
JOIN_GAME_COOLDOWN = 30
SIMULATE_COOLDOWN = 30

# Game settings
BET_AMOUNT_DEFAULT = 10.0
MIN_BET_AMOUNT = 5.0
MAX_BET_AMOUNT = 1000.0
PLATFORM_FEE_PERCENT = 5.0

# Payment settings
MIN_DEPOSIT_AMOUNT = 10.0
MAX_DEPOSIT_AMOUNT = 10000.0
MIN_WITHDRAW_AMOUNT = 50.0
MAX_WITHDRAW_AMOUNT = 5000.0

# Cooldown settings (in seconds) - reduced for better testing
CREATE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DELETE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DEPOSIT_COOLDOWN = 10  # Was 300 (5 minutes)
WITHDRAW_COOLDOWN = 10  # Was 3600 (1 hour)
JOIN_GAME_COOLDOWN = 10  # Was 60 (1 minute)

# Application URLs
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
PAYMENT_SUCCESS_URL = f"{BASE_URL}/payment/success"
PAYMENT_CANCEL_URL = f"{BASE_URL}/payment/cancel"
PAYMENT_WEBHOOK_URL = f"{BASE_URL}/api/payment/webhook"

# Database settings
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///rps_game.db')

# Debug mode
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

# Game timeout (minutes)
GAME_TIMEOUT = 60  # seconds

# Fallback to 2-player mode if 3rd player doesn't join after X minutes
FALLBACK_TO_TWO_PLAYER = 5

# Capa Wallet settings
CAPA_API_URL = os.environ.get("CAPA_API_URL", "https://api.capawallet.com/v1")
CAPA_API_KEY = os.environ.get("CAPA_API_KEY", "")
CAPA_SECRET_KEY = os.environ.get("CAPA_SECRET_KEY", "")

if not CAPA_API_KEY or not CAPA_SECRET_KEY:
    LOGGER.warning("Capa Wallet API keys not configured. Using mock payment system.")

# Chapa API settings
CHAPA_API_KEY = "CHASECK_TEST-WQATsMezrNPxr8bsVH1TAGwAfDBofhqq"
CHAPA_API_URL = "https://api.chapa.co/v1"
CHAPA_SECRET_KEY = os.getenv('CHAPA_SECRET_KEY')
CHAPA_PUBLIC_KEY = os.getenv('CHAPA_PUBLIC_KEY')

# Transaction Limits
MIN_DEPOSIT = 10  # ETB
MAX_DEPOSIT = 10000  # ETB
MIN_WITHDRAW = 50  # ETB
MAX_WITHDRAW = 5000  # ETB
DAILY_DEPOSIT_LIMIT = 20000  # ETB
DAILY_WITHDRAW_LIMIT = 10000  # ETB

# Prize Distribution
PRIZE_DISTRIBUTION = {
    'winner': 0.60,  # 60% to winner
    'second': 0.20,  # 20% to second place
    'third': 0.10,   # 10% to third place
    'house': 0.10    # 10% house fee
}

# Game States
GAME_STATES = {
    'WAITING': 'waiting',
    'STARTING': 'starting',
    'IN_PROGRESS': 'in_progress',
    'COMPLETED': 'completed',
    'CANCELLED': 'cancelled'
}

# Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'rps_bot.log',
            'formatter': 'default',
            'level': 'INFO'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

# Configure logger
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['root']['level']),
    format=LOGGING_CONFIG['formatters']['default']['format'],
    handlers=[
        logging.FileHandler(LOGGING_CONFIG['handlers']['file']['filename']),
        logging.StreamHandler()
    ]
)

LOGGER = logging.getLogger(__name__)