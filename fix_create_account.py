#!/usr/bin/env python3
"""
Fix for /creat_account command not working
"""

import os
import re

def fix_telegram_bot():
    """Add support for misspelled /creat_account command"""
    file_path = 'telegram_bot.py'
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the main function where we register command handlers
    main_pattern = r'async def main\(\).*?application\.run_polling\('
    main_match = re.search(main_pattern, content, re.DOTALL)
    
    if not main_match:
        print("Could not find main function!")
        return
    
    main_content = main_match.group(0)
    
    # Check if create_account command is registered
    if 'application.add_handler(CommandHandler("create_account", create_account))' in main_content:
        # Add a handler for the misspelled command right after the correct one
        original = 'application.add_handler(CommandHandler("create_account", create_account))'
        replacement = 'application.add_handler(CommandHandler("create_account", create_account))\n    # Also support misspelled version\n    application.add_handler(CommandHandler("creat_account", create_account))'
        
        updated_main = main_content.replace(original, replacement)
        
        if updated_main != main_content:
            # Replace the main function
            updated_content = content.replace(main_content, updated_main)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print("Added support for misspelled /creat_account command")
        else:
            print("Could not update command handlers")
    else:
        print("Could not find create_account command handler")
        
    # Also check for parse_mode issues in create_account function
    create_account_pattern = r'async def create_account\(update: Update, context: ContextTypes\.DEFAULT_TYPE\).*?(?=async def|\Z)'
    create_account_match = re.search(create_account_pattern, content, re.DOTALL)
    
    if create_account_match:
        create_account_content = create_account_match.group(0)
        
        # Check if the function has issues with Markdown
        if 'parse_mode=\'Markdown\'' in create_account_content and '$' in create_account_content:
            # Remove parse_mode or add escape_markdown
            if 'escape_markdown(' in content:
                # We have the escape function, let's use it
                message_pattern = r'(await update\.message\.reply_text\(\s*)(f[\'"].*?[\'"])(,\s*parse_mode=[\'"]Markdown[\'"])'
                message_match = re.search(message_pattern, create_account_content, re.DOTALL)
                
                if message_match:
                    original_message = message_match.group(0)
                    escaped_message = f'{message_match.group(1)}escape_markdown({message_match.group(2)}){message_match.group(3)}'
                    
                    updated_create_account = create_account_content.replace(original_message, escaped_message)
                    updated_content = content.replace(create_account_content, updated_create_account)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                    
                    print("Fixed Markdown escaping in create_account function")
            else:
                # No escape function, just remove parse_mode
                message_pattern = r'(await update\.message\.reply_text\(\s*f[\'"].*?[\'"])(,\s*parse_mode=[\'"]Markdown[\'"])'
                updated_create_account = re.sub(message_pattern, r'\1', create_account_content)
                
                if updated_create_account != create_account_content:
                    updated_content = content.replace(create_account_content, updated_create_account)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
                    
                    print("Removed parse_mode from create_account function")

if __name__ == "__main__":
    fix_telegram_bot()
    print("\nFix applied! To test:")
    print("1. Restart your bot")
    print("2. Try the command: /creat_account")
    print("3. If it still doesn't work, try: /create_account (with the correct spelling)") 