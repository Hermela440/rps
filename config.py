"""
Configuration settings for the RPS Arena application
"""

import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

# Game settings
BET_AMOUNT_DEFAULT = 10  # Default bet amount for games
MAX_PLAYERS_PER_GAME = 3  # Number of players in a game
PLATFORM_FEE_PERCENT = 5  # Platform fee percentage for game winnings

# Payment settings
MIN_DEPOSIT_AMOUNT = 10  # Minimum deposit amount
MAX_DEPOSIT_AMOUNT = 1000  # Maximum deposit amount
MIN_WITHDRAW_AMOUNT = 20  # Minimum withdrawal amount
MAX_WITHDRAW_AMOUNT = 1000  # Maximum withdrawal amount

# Cooldown settings (in seconds) - reduced for better testing
CREATE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DELETE_ACCOUNT_COOLDOWN = 10  # Was 86400 (24 hours)
DEPOSIT_COOLDOWN = 10  # Was 300 (5 minutes)
WITHDRAW_COOLDOWN = 10  # Was 3600 (1 hour)
JOIN_GAME_COOLDOWN = 10  # Was 60 (1 minute)

# Telegram Bot settings
BOT_TOKEN = "7832695308:AAHlQ3bXJT5rbIeP8OzoujBB2M9ZZBuEB-U"

# Add all admin users - update with actual Telegram IDs
ADMIN_USERS = []  # Empty by default, add IDs manually

# Application URLs
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
PAYMENT_SUCCESS_URL = f"{BASE_URL}/payment/success"
PAYMENT_CANCEL_URL = f"{BASE_URL}/payment/cancel"
PAYMENT_WEBHOOK_URL = f"{BASE_URL}/api/payment/webhook"

# Database settings
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///rps_game.db")

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