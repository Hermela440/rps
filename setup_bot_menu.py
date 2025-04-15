#!/usr/bin/env python3
"""
Set up command menu for Telegram bot
"""

import requests
import os
from config import BOT_TOKEN

def setup_bot_commands():
    """Set up the command menu for the bot using Telegram API"""
    print("Setting up bot command menu...")
    
    # Define command categories and their commands
    commands = [
        # Account Commands
        {"command": "start", "description": "Start the bot"},
        {"command": "create_account", "description": "Create a new account"},
        {"command": "delete_account", "description": "Delete your account"},
        {"command": "balance", "description": "Check your wallet balance"},
        {"command": "deposit", "description": "Add funds to your wallet"},
        {"command": "withdraw", "description": "Withdraw funds from your wallet"},
        {"command": "history", "description": "View your transaction history"},
        
        # Game Commands
        {"command": "join_game", "description": "Join a match with default bet ($10)"},
        {"command": "game_status", "description": "Check status of current game"},
        
        # Stats Commands
        {"command": "leaderboard", "description": "View top players"},
        {"command": "profile", "description": "View your profile stats"},
        
        # Help Commands
        {"command": "help", "description": "Show all available commands"},
        {"command": "about", "description": "About the RPS Arena bot"}
    ]
    
    # API endpoint to set bot commands
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
    
    # Make the API request
    response = requests.post(url, json={"commands": commands})
    
    if response.status_code == 200 and response.json().get("ok"):
        print("✅ Command menu set up successfully!")
        print("Users will now see the commands menu when they click the '/' button in chat")
    else:
        print(f"❌ Failed to set up command menu: {response.text}")

def add_welcome_menu_to_bot():
    """Add a menu keyboard to the bot's welcome message"""
    file_path = 'telegram_bot.py'
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we need to add imports for ReplyKeyboardMarkup
    if 'from telegram import ReplyKeyboardMarkup' not in content:
        # Add the import
        import_line = 'from telegram import InlineKeyboardButton, InlineKeyboardMarkup'
        new_import = 'from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton'
        content = content.replace(import_line, new_import)
    
    # Find the start function
    start_pattern = r'async def start\(update: Update, context: ContextTypes\.DEFAULT_TYPE\).*?await update\.message\.reply_text\([^)]*\)'
    start_match = content.find('async def start(')
    
    if start_match != -1:
        # Find the end of the function or beginning of next function
        end_match = content.find('async def', start_match + 1)
        if end_match != -1:
            start_func = content[start_match:end_match]
            
            # Check if we already have a keyboard menu
            if 'ReplyKeyboardMarkup' not in start_func:
                # Create updated start function with menu
                new_start_func = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    # Create a keyboard with command categories
    keyboard = [
        [KeyboardButton("💰 Account"), KeyboardButton("🎮 Game")],
        [KeyboardButton("📊 Stats"), KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome to RPS Arena Bot! Choose a command category or use / to see all commands:",
        reply_markup=reply_markup
    )
'''
                # Replace the old function
                content = content.replace(content[start_match:end_match], new_start_func)
                
                # Also add a message handler for the keyboard buttons
                if 'async def handle_menu_button' not in content:
                    # Find the position to add the new handler
                    main_position = content.find('async def main()')
                    if main_position != -1:
                        handler_code = '''
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu button selections"""
    text = update.message.text
    
    if text == "💰 Account":
        await update.message.reply_text(
            "📋 *Account Commands*\\n\\n"
            "/create_account - Create your account\\n"
            "/balance - Check your wallet balance\\n"
            "/deposit - Add funds to your wallet\\n"
            "/withdraw - Withdraw funds\\n"
            "/delete_account - Delete your account\\n"
            "/history - View your transaction history",
            parse_mode='Markdown'
        )
    elif text == "🎮 Game":
        await update.message.reply_text(
            "📋 *Game Commands*\\n\\n"
            "/join_game - Join a match with default bet ($10)\\n"
            "/join_game [amount] - Join with custom bet amount\\n"
            "/game_status - Check current game status",
            parse_mode='Markdown'
        )
    elif text == "📊 Stats":
        await update.message.reply_text(
            "📋 *Stats Commands*\\n\\n"
            "/leaderboard - View top players\\n"
            "/profile - View your stats",
            parse_mode='Markdown'
        )
    elif text == "ℹ️ Help":
        await update.message.reply_text(
            "📋 *Help Commands*\\n\\n"
            "/help - Show all available commands\\n"
            "/about - About the RPS Arena bot",
            parse_mode='Markdown'
        )

'''
                        content = content[:main_position] + handler_code + content[main_position:]
                        
                        # Now add the handler registration in main()
                        handler_registration = 'application.add_handler(MessageHandler(filters.COMMAND, unknown_command))'
                        if handler_registration in content:
                            new_handler = 'application.add_handler(MessageHandler(filters.COMMAND, unknown_command))\n    \n    # Add menu button handler\n    application.add_handler(MessageHandler(filters.Regex("^(💰 Account|🎮 Game|📊 Stats|ℹ️ Help)$"), handle_menu_button))'
                            content = content.replace(handler_registration, new_handler)
                
                # Write the updated content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("✅ Added menu keyboard to welcome message")
            else:
                print("Menu keyboard is already present in the start function")
    else:
        print("Could not find start function")

if __name__ == "__main__":
    # Set up commands with Telegram
    setup_bot_commands()
    
    # Add menu to welcome message
    add_welcome_menu_to_bot()
    
    print("\nSetup complete! Restart your bot to see the changes.")
    print("\nUsers will now have two ways to access commands:")
    print("1. Through the '/' menu in Telegram")
    print("2. Through the button menu when they start the bot")