"""
Configuration settings for the RPS Arena application
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

# Game settings
BET_AMOUNT_DEFAULT = 10.0
MIN_BET_AMOUNT = 1.0
MAX_BET_AMOUNT = 1000.0
PLATFORM_FEE_PERCENT = 5.0

# Payment settings
MIN_DEPOSIT_AMOUNT = 10.0
MAX_DEPOSIT_AMOUNT = 1000.0
MIN_WITHDRAW_AMOUNT = 20.0
MAX_WITHDRAW_AMOUNT = 500.0

# Cooldown settings (in seconds) - reduced for better testing
CREATE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DELETE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DEPOSIT_COOLDOWN = 10  # Was 300 (5 minutes)
WITHDRAW_COOLDOWN = 10  # Was 3600 (1 hour)
JOIN_GAME_COOLDOWN = 10  # Was 60 (1 minute)

# Telegram Bot settings
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Add all admin users - update with actual Telegram IDs
ADMIN_USERS = [1418773713]  # Your admin ID is directly included

# Application URLs
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
PAYMENT_SUCCESS_URL = f"{BASE_URL}/payment/success"
PAYMENT_CANCEL_URL = f"{BASE_URL}/payment/cancel"
PAYMENT_WEBHOOK_URL = f"{BASE_URL}/api/payment/webhook"

# Database settings
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///rps_bot.db')

# Debug mode
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

# Game timeout (minutes)
GAME_TIMEOUT = 30  # Games waiting longer than this will be automatically canceled

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
CHAPA_API_URL = os.getenv('CHAPA_API_URL', 'https://api.chapa.co/v1')
CHAPA_SECRET_KEY = os.getenv('CHAPA_SECRET_KEY')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')