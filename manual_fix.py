#!/usr/bin/env python3
"""
Manual fix for dollar sign issues in Telegram bot messages
"""

import os
import re

def fix_telegram_bot_file():
    """Fix dollar sign issues in telegram_bot.py"""
    
    file_path = 'telegram_bot.py'
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match function definitions for specific commands
    functions_to_fix = [
        'create_account',
        'balance',
        'deposit',
        'withdraw',
        'join_game',
        'game_status',
        'profile'
    ]
    
    # Track fixes
    fixes_made = 0
    
    # Process each function that might have dollar sign issues
    for func_name in functions_to_fix:
        # Find the function definition
        func_pattern = rf'async def {func_name}\([^)]*\).*?(?=async def|\Z)'
        func_match = re.search(func_pattern, content, re.DOTALL)
        
        if func_match:
            func_code = func_match.group(0)
            
            # Check if this function contains both dollar signs and parse_mode='Markdown'
            if '$' in func_code and 'parse_mode=' in func_code:
                # Fix: Replace dollar signs with escaped dollar signs when parse_mode is used
                updated_func_code = func_code.replace('$', '\\$')
                
                # Or alternatively, remove parse_mode altogether from reply_text calls with dollar signs
                reply_text_pattern = r'(await update\.message\.reply_text\([^)]*\$[^)]*\))(,\s*parse_mode=[\'"]Markdown[\'"])'
                updated_func_code = re.sub(reply_text_pattern, r'\1', func_code)
                
                if updated_func_code != func_code:
                    content = content.replace(func_code, updated_func_code)
                    fixes_made += 1
                    print(f"Fixed dollar sign issues in {func_name}() function")
    
    if fixes_made > 0:
        # Write the updated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Total fixes made: {fixes_made}")
    else:
        print("No specific dollar sign issues found to fix")
        
    # As a failsafe, let's add a special debug function that will work regardless
    add_debug_command(file_path)

def add_debug_command(file_path):
    """Add a debug command to help diagnose further issues"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the debug function already exists
    if 'async def debug_command' not in content:
        # Find the main function to insert before it
        main_match = re.search(r'async def main\(\)', content)
        if main_match:
            # Position to insert before main function
            insert_pos = main_match.start()
            
            # Create our debug command function
            debug_func = '''
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to test bot functionality."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Simple message without parse_mode
    await update.message.reply_text(
        f"Debug command works!\\n"
        f"Your Telegram ID: {user_id}\\n"
        f"Your username: {username}"
    )
    
    # Check if user exists in database
    user = get_user_by_telegram_id(user_id)
    if user:
        # Send a second message with user info
        await update.message.reply_text(
            f"Database info:\\n"
            f"DB ID: {user.id}\\n"
            f"Username: {user.username}\\n"
            f"Balance: {user.balance:.2f}\\n"
            f"Exists in DB: Yes"
        )
    else:
        await update.message.reply_text(
            f"You don't exist in the database.\\n"
            f"Use /create_account to create an account."
        )

'''
            # Insert the debug function
            updated_content = content[:insert_pos] + debug_func + content[insert_pos:]
            
            # Now add the command handler to main function
            handler_pattern = r'(# Add callback query handler.*?\n.*?\))'
            handler_match = re.search(handler_pattern, updated_content, re.DOTALL)
            
            if handler_match:
                handler_pos = handler_match.end()
                debug_handler = '\n    # Add debug command\n    application.add_handler(CommandHandler("debug", debug_command))'
                updated_content = updated_content[:handler_pos] + debug_handler + updated_content[handler_pos:]
                
                # Write the updated content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                print("Added /debug command to help diagnose issues")
                return
    
    print("Could not add debug command, please add it manually")

if __name__ == "__main__":
    fix_telegram_bot_file() 