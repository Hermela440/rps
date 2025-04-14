import os
import logging

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Only require BOT_TOKEN if not in web-only mode
WEB_ONLY = os.environ.get("WEB_ONLY", "true").lower() == "true"
if not BOT_TOKEN and not WEB_ONLY:
    raise ValueError("No BOT_TOKEN environment variable set")

# Game Settings
BET_AMOUNT_DEFAULT = 10
PLATFORM_FEE_PERCENT = 5
COOLDOWN_SECONDS = 5
MIN_DEPOSIT_AMOUNT = 5
MAX_DEPOSIT_AMOUNT = 1000
MIN_WITHDRAW_AMOUNT = 10
MAX_WITHDRAW_AMOUNT = 500

# Admin Users (Telegram IDs as integers)
ADMIN_USERS = [int(id) for id in os.environ.get("ADMIN_USERS", "").split(",") if id]

# Database settings
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///rps_game.db")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
LOGGER = logging.getLogger(__name__)

# Web app settings
WEB_PORT = 5000
BOT_PORT = 8000
HOST = "0.0.0.0"
