from app import app  # noqa: F401
# from telegram_bot import main as run_bot (temporarily disabled for web app only)
import threading
import logging
import os
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def start_bot_thread():
    """Run the Telegram bot in a separate thread"""
    logger.info("Starting Telegram bot thread")
    try:
        # Temporarily disabled for web app only
        # run_bot()
        logger.info("Telegram bot is disabled for web app")
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")

if __name__ == "__main__":
    # Check if we're just running the web app (without the bot)
    web_only = os.environ.get("WEB_ONLY", "true").lower() == "true"
    
    if not web_only:
        # Start the bot in a separate thread (disabled for now)
        logger.info("Telegram bot is disabled for web app")
        # bot_thread = threading.Thread(target=start_bot_thread)
        # bot_thread.daemon = True
        # bot_thread.start()
    
    # Start the Flask web app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
