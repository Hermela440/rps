from app import app  # noqa: F401
# Temporarily disable the bot import to focus on web animations
# from telegram_bot import main as run_bot
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
        # run_bot()
        logger.info("Telegram bot is temporarily disabled to focus on web animations")
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")

# Set environment variable to run web-only mode
os.environ["WEB_ONLY"] = "true"

if __name__ == "__main__":
    # Check if we're just running the web app (without the bot)
    web_only = os.environ.get("WEB_ONLY", "true").lower() == "true"
    
    if not web_only:
        # Start the bot in a separate thread
        logger.info("Telegram bot is temporarily disabled")
        # bot_thread = threading.Thread(target=start_bot_thread)
        # bot_thread.daemon = True
        # bot_thread.start()
    
    # Start the Flask web app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
