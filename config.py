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

# Cooldown settings (in seconds)
CREATE_ACCOUNT_COOLDOWN = 86400  # 24 hours
DELETE_ACCOUNT_COOLDOWN = 86400  # 24 hours
DEPOSIT_COOLDOWN = 300  # 5 minutes
WITHDRAW_COOLDOWN = 3600  # 1 hour
JOIN_GAME_COOLDOWN = 60  # 1 minute

# Telegram Bot settings
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    LOGGER.warning("Telegram bot token not set. Bot will not be available.")

# Capa Wallet settings
CAPA_API_URL = os.environ.get("CAPA_API_URL", "https://api.capawallet.com/v1")
CAPA_API_KEY = os.environ.get("CAPA_API_KEY", "")
CAPA_SECRET_KEY = os.environ.get("CAPA_SECRET_KEY", "")

if not CAPA_API_KEY or not CAPA_SECRET_KEY:
    LOGGER.warning("Capa Wallet API keys not configured. Using mock payment system.")