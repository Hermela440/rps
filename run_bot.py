import requests
import time
import json
import logging
from config import BOT_TOKEN

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GIF URLs for different game outcomes
ROCK_GIF = "https://media.giphy.com/media/3o7TKNjg8dxB5ysRnW/giphy.gif"
PAPER_GIF = "https://media.giphy.com/media/3o7527Rn1HxXWqgxuo/giphy.gif"
SCISSORS_GIF = "https://media.giphy.com/media/3o7TKRXwArnzrW52MM/giphy.gif"
ROCK_WINS_GIF = "https://media.giphy.com/media/3oxHQfvDdo6OrXwOPK/giphy.gif"
PAPER_WINS_GIF = "https://media.giphy.com/media/3o7TKH6gFrV1TCxfgs/giphy.gif"
SCISSORS_WINS_GIF = "https://media.giphy.com/media/3o7TKB3yoARvULNBmM/giphy.gif"
DRAW_GIF = "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif"

def get_updates(offset=None):
    """Get updates from Telegram API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {'timeout': 30}
    if offset:
        params['offset'] = offset
    
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return {'ok': False}

def send_message(chat_id, text):
    """Send message to Telegram chat"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return {'ok': False}

def send_animation(chat_id, animation_url, caption=None):
    """Send GIF animation to Telegram chat"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAnimation"
    params = {
        'chat_id': chat_id,
        'animation': animation_url
    }
    
    if caption:
        params['caption'] = caption
    
    try:
        response = requests.post(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending animation: {e}")
        return {'ok': False}

def send_game_choices(chat_id):
    """Send game choice buttons"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '🗿 Rock', 'callback_data': 'choice_rock'},
                {'text': '📄 Paper', 'callback_data': 'choice_paper'},
                {'text': '✂️ Scissors', 'callback_data': 'choice_scissors'}
            ]
        ]
    }
    
    params = {
        'chat_id': chat_id,
        'text': 'Choose your move:',
        'reply_markup': json.dumps(keyboard)
    }
    
    try:
        response = requests.post(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending game choices: {e}")
        return {'ok': False}

def process_game_choice(chat_id, choice):
    """Process user's game choice and show animation"""
    # Simulate computer choice
    import random
    computer_choice = random.choice(['rock', 'paper', 'scissors'])
    
    # Send user's choice GIF
    if choice == 'rock':
        send_animation(chat_id, ROCK_GIF, "You chose ROCK")
    elif choice == 'paper':
        send_animation(chat_id, PAPER_GIF, "You chose PAPER")
    elif choice == 'scissors':
        send_animation(chat_id, SCISSORS_GIF, "You chose SCISSORS")
    
    # Wait for dramatic effect
    time.sleep(1)
    
    # Send computer's choice message
    send_message(chat_id, f"Computer chose *{computer_choice.upper()}*")
    
    # Determine winner and send result GIF
    if choice == computer_choice:
        # Draw
        time.sleep(1)
        send_animation(chat_id, DRAW_GIF, "It's a DRAW! No winner.")
    elif (choice == 'rock' and computer_choice == 'scissors') or \
         (choice == 'paper' and computer_choice == 'rock') or \
         (choice == 'scissors' and computer_choice == 'paper'):
        # User wins
        time.sleep(1)
        if choice == 'rock':
            send_animation(chat_id, ROCK_WINS_GIF, "ROCK crushes SCISSORS. You WIN! 🎉")
        elif choice == 'paper':
            send_animation(chat_id, PAPER_WINS_GIF, "PAPER covers ROCK. You WIN! 🎉")
        else:
            send_animation(chat_id, SCISSORS_WINS_GIF, "SCISSORS cut PAPER. You WIN! 🎉")
    else:
        # Computer wins
        time.sleep(1)
        if computer_choice == 'rock':
            send_animation(chat_id, ROCK_WINS_GIF, "ROCK crushes SCISSORS. Computer WINS! 😔")
        elif computer_choice == 'paper':
            send_animation(chat_id, PAPER_WINS_GIF, "PAPER covers ROCK. Computer WINS! 😔")
        else:
            send_animation(chat_id, SCISSORS_WINS_GIF, "SCISSORS cut PAPER. Computer WINS! 😔")

def main():
    """Main bot loop"""
    logger.info("Starting bot...")
    offset = None
    
    while True:
        updates = get_updates(offset)
        
        if updates.get('ok', False):
            for update in updates.get('result', []):
                # Update offset to acknowledge this update
                offset = update['update_id'] + 1
                
                # Process callback query (button clicks)
                if 'callback_query' in update:
                    callback_query = update['callback_query']
                    chat_id = callback_query['message']['chat']['id']
                    data = callback_query['data']
                    
                    if data.startswith('choice_'):
                        choice = data.split('_')[1]
                        process_game_choice(chat_id, choice)
                
                # Process message if present
                elif 'message' in update and 'text' in update['message']:
                    message_text = update['message']['text']
                    chat_id = update['message']['chat']['id']
                    user = update['message'].get('from', {}).get('username', 'User')
                    
                    logger.info(f"Received message from {user}: {message_text}")
                    
                    # Handle commands
                    if message_text.startswith('/start'):
                        send_message(chat_id, "Hello! Welcome to the RPS Arena Bot.\n\nUse /help to see available commands.")
                    
                    elif message_text.startswith('/help'):
                        help_text = (
                            "📚 *Available Commands* 📚\n\n"
                            "*🔐 Account Commands*\n"
                            "/create_account - Create your account (first step!)\n"
                            "/balance - Check your wallet balance\n"
                            "/deposit - Add funds to your wallet\n"
                            "/withdraw - Withdraw funds\n"
                            "/delete_account - Delete your account\n"
                            "/history - View your game history\n\n"
                            
                            "*🎮 Game Commands*\n"
                            "/join_game - Join a match with default bet ($10)\n"
                            "/join_game [amount] - Join with custom bet amount\n"
                            "/game_status - Check current game status\n\n"
                            
                            "*📊 Stats Commands*\n"
                            "/leaderboard - View top players\n"
                            "/profile - View your stats\n\n"
                            
                            "*ℹ️ Help Commands*\n"
                            "/help - Show all available commands\n"
                            "/about - Learn about the bot"
                        )
                        send_message(chat_id, help_text)
                    
                    elif message_text.startswith('/about'):
                        about_text = (
                            "📱 *RPS Arena Bot* 📱\n\n"
                            "A Telegram bot for playing Rock-Paper-Scissors with virtual betting.\n\n"
                            "Features:\n"
                            "• Play RPS with 3 players\n"
                            "• Virtual wallet system\n"
                            "• Betting on matches\n"
                            "• Leaderboard and statistics\n\n"
                            "Created as a sample project for demonstration purposes."
                        )
                        send_message(chat_id, about_text)
                    
                    elif message_text.startswith('/create_account'):
                        send_message(chat_id, f"Account created successfully! Welcome, {user}.\nYou've received a welcome bonus of $100.00 in your wallet.")
                    
                    elif message_text.startswith('/balance'):
                        send_message(chat_id, f"Your current balance: $100.00")
                    
                    elif message_text.startswith('/deposit'):
                        send_message(chat_id, "To deposit funds, please follow these steps:\n1. Choose an amount\n2. Complete payment\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/withdraw'):
                        send_message(chat_id, "To withdraw funds, please specify an amount:\n/withdraw [amount]\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/delete_account'):
                        send_message(chat_id, "Are you sure you want to delete your account? This action cannot be undone.\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/history'):
                        send_message(chat_id, "Your transaction history:\n\n- Welcome bonus: +$100.00\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/join_game'):
                        send_message(chat_id, "Joining game with $10 bet. Waiting for other players...\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/game_status'):
                        send_message(chat_id, "Current game status: Waiting for players (1/3)\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/leaderboard'):
                        send_message(chat_id, "🏆 *Top Players*\n\n1. Player1 - $500\n2. Player2 - $350\n3. Player3 - $200\n\n(This is a demo message)")
                    
                    elif message_text.startswith('/profile'):
                        profile_text = (
                            "👤 *Your Profile*\n\n"
                            "Username: " + user + "\n"
                            "Balance: $100.00\n"
                            "Games played: 0\n"
                            "Wins: 0\n"
                            "Losses: 0\n"
                            "Win rate: 0%\n\n"
                            "(This is a demo message)"
                        )
                        send_message(chat_id, profile_text)
                    
                    else:
                        send_message(chat_id, "Unknown command. Use /help to see available commands.")
        
        # Sleep to avoid hitting API limits
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
