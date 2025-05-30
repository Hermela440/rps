"""Main application file"""
import os
from flask import Flask
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from database.extensions import init_db
from bot.handlers.deposit import get_deposit_handler
from bot.handlers.withdraw import get_withdraw_handler
from bot.handlers.admin import handle_approve, handle_reject, handle_pending
from bot.handlers.game import get_game_handler
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

async def start(update, context):
    """Handle /start command"""
    user = update.effective_user
    await update.message.reply_text(
        f"🎮 Yo {user.first_name}! Ready to rock (paper scissors) your way to riches? 🚀\n\n"
        "🎲 Welcome to the coolest Rock Paper Scissors bot in town! We're not just playing for fun - "
        "we're playing for real money! 💰\n\n"
        "🎯 What's in it for you?\n"
        "• Double your money when you win! 🤑\n"
        "• Quick deposits and withdrawals 💸\n"
        "• Track your wins (and maybe a few losses 😅)\n\n"
        "🎮 Let's Get Started!\n"
        "1️⃣ First, load up your account:\n"
        "   /deposit 100  (or any amount you're comfy with)\n\n"
        "2️⃣ Ready to play? Let's go!\n"
        "   /play 50  (bet what you can afford to lose!)\n\n"
        "3️⃣ Feeling lucky? Check your balance:\n"
        "   /balance  (because knowing is winning!)\n\n"
        "4️⃣ Time to cash out?\n"
        "   /withdraw  (take your winnings and run! 🏃‍♂️)\n\n"
        "🎲 How to Play (It's super easy!):\n"
        "1. Place your bet\n"
        "2. Choose your weapon:\n"
        "   🪨 Rock (for the strong and steady)\n"
        "   📄 Paper (for the strategic minds)\n"
        "   ✂️ Scissors (for the swift and sharp)\n"
        "3. Watch the magic happen! ✨\n\n"
        "💡 Pro Tips (from a bot who's seen it all):\n"
        "• Start small, dream big! 🌟\n"
        "• Don't bet your lunch money! 🍔\n"
        "• If you're winning, maybe it's time to quit! 🎯\n"
        "• If you're losing, definitely time to quit! 😅\n\n"
        "🎪 Need help? Just type /help and I'll be your guide!\n\n"
        "Remember: The house always wins... unless you're really good! 😉\n"
        "Good luck, and may the odds be ever in your favor! 🍀"
    )

async def help(update, context):
    """Handle /help command"""
    await update.message.reply_text(
        "🎮 Game Commands:\n\n"
        "/start - Begin your adventure\n"
        "/deposit - Load up your wallet\n"
        "/withdraw - Cash out your winnings\n"
        "/balance - Check your fortune\n"
        "/play - Start the game\n"
        "/help - Show this message\n\n"
        "👑 Admin Commands:\n"
        "/approve <tx_ref> - Give the green light\n"
        "/reject <tx_ref> - Say no to withdrawal\n"
        "/pending - Check waiting withdrawals"
    )

def main():
    """Main function"""
    # Get bot token from environment
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment")

    # Create application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(get_deposit_handler())
    application.add_handler(get_withdraw_handler())
    application.add_handler(get_game_handler())
    
    # Admin handlers
    application.add_handler(CommandHandler("approve", handle_approve))
    application.add_handler(CommandHandler("reject", handle_reject))
    application.add_handler(CommandHandler("pending", handle_pending))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main() 