#!/usr/bin/env python3
"""
Fix dollar sign issues in Telegram bot messages
"""

import re
import os

def fix_telegram_bot_file():
    """Fix dollar sign issues in telegram_bot.py"""
    
    file_path = 'telegram_bot.py'
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for patterns where we have $, followed by parse_mode='Markdown'
    # Use regex capture groups to preserve the text but remove the parse_mode
    pattern = r'(await update\.message\.reply_text\([^)]*\$[^)]*\))(,\s*parse_mode=\'Markdown\')'
    
    # Replace with just the first group (removing parse_mode='Markdown')
    fixed_content = re.sub(pattern, r'\1', content)
    
    # Count replacements
    replacements = content.count('parse_mode=\'Markdown\'') - fixed_content.count('parse_mode=\'Markdown\'')
    
    # Only write if changes were made
    if replacements > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print(f"Fixed {replacements} instances of dollar sign with Markdown issues in {file_path}")
    else:
        print("No dollar sign issues found or already fixed")

if __name__ == "__main__":
    fix_telegram_bot_file() 