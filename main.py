from app import app, db
from telegram_bot import main as run_bot
import threading
import logging
import os
import asyncio
from datetime import datetime, timedelta
from config import GAME_TIMEOUT, LOGGER
from models import Game, GameParticipant, User, Transaction

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def run_async_bot():
    """Run the async bot in the current thread"""
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_bot())
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")
        logger.exception("Full traceback:")

def start_bot_thread():
    """Run the Telegram bot in a separate thread"""
    logger.info("Starting Telegram bot thread")
    try:
        run_async_bot()
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")
        logger.exception("Full traceback:")

def maintenance_thread_func():
    """Background thread for maintenance tasks like cleaning stale games"""
    logger.info("Starting maintenance thread")
    
    while True:
        try:
            # Sleep first to allow app to fully initialize
            time.sleep(60)
            
            with app.app_context():
                # Clean stale games
                cleanup_stale_games()
                
                # Start games with 2 players if they've been waiting too long
                check_waiting_games()
                
                logger.debug("Maintenance tasks completed")
        except Exception as e:
            logger.error(f"Error in maintenance task: {e}")
        
        # Run maintenance every minute
        time.sleep(60)

def cleanup_stale_games():
    """Clean up games that have been waiting too long"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=GAME_TIMEOUT)
    
    stale_games = Game.query.filter(
        Game.status == 'waiting',
        Game.created_at < cutoff_time
    ).all()
    
    for game in stale_games:
        # Refund all participants
        for participant in GameParticipant.query.filter_by(game_id=game.id).all():
            user = User.query.get(participant.user_id)
            if user:
                user.balance += game.bet_amount
                
                # Create refund transaction
                transaction = Transaction(
                    user_id=user.id,
                    amount=game.bet_amount,
                    transaction_type='refund',
                    status='completed',
                    reference_id=f"timeout_{game.id}",
                    created_at=datetime.utcnow(),
                    completed_at=datetime.utcnow()
                )
                db.session.add(transaction)
        
        # Mark game as cancelled
        game.status = 'cancelled'
        game.completed_at = datetime.utcnow()
    
    if stale_games:
        logger.info(f"Cleaned up {len(stale_games)} stale games")
        db.session.commit()

def check_waiting_games():
    """Check for games with exactly 2 players waiting for too long"""
    from config import FALLBACK_TO_TWO_PLAYER
    
    cutoff_time = datetime.utcnow() - timedelta(minutes=FALLBACK_TO_TWO_PLAYER)
    
    waiting_games = Game.query.filter(
        Game.status == 'waiting',
        Game.created_at < cutoff_time
    ).all()
    
    started_games = 0
    
    for game in waiting_games:
        # Count participants
        participant_count = GameParticipant.query.filter_by(game_id=game.id).count()
        
        # If exactly 2 players, start the game
        if participant_count == 2:
            game.status = 'active'
            started_games += 1
    
    if started_games > 0:
        logger.info(f"Started {started_games} games with 2 players due to timeout")
        db.session.commit()

# Always run the bot unless explicitly disabled
os.environ["WEB_ONLY"] = os.environ.get("WEB_ONLY", "false")

if __name__ == "__main__":
    # Make sure database tables exist
    with app.app_context():
        db.create_all()
    
    # Check if we're running web-only
    web_only = os.environ.get("WEB_ONLY", "false").lower() == "true"
    
    if not web_only:
        # Start the bot in a separate thread
        import time
        bot_thread = threading.Thread(target=start_bot_thread)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Start maintenance thread
        maintenance_thread = threading.Thread(target=maintenance_thread_func)
        maintenance_thread.daemon = True
        maintenance_thread.start()
        
        logger.info("Bot and maintenance threads started")
    
    # Start the Flask web app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
