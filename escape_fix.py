#!/usr/bin/env python3
"""
Fix for Telegram bot Markdown escaping issues
"""

import os
import re

def add_escape_markdown_function(file_path):
    """Add an escape_markdown utility function to the file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the function already exists
    if 'def escape_markdown(' not in content:
        # Add the function after the imports
        import_section_end = content.find('from config import')
        import_section_end = content.find('\n', import_section_end) + 1
        
        escape_function = '''
def escape_markdown(text):
    """
    Helper function to escape Markdown special characters in text.
    This allows using dollar signs and other special characters in messages.
    """
    if not text:
        return ""
    
    # Characters that need escaping in Markdown V2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escape backslash first to avoid double-escaping
    text = text.replace('\\\\', '\\\\\\\\')
    
    # Escape all other special characters
    for char in special_chars:
        text = text.replace(char, f'\\\\{char}')
    
    # Special handling for $ which is problematic in Telegram Markdown
    text = text.replace('$', '\\\\$')
    
    return text

'''
        # Insert the escape function
        updated_content = content[:import_section_end] + escape_function + content[import_section_end:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print("Added escape_markdown() function")
        return updated_content
    else:
        print("escape_markdown() function already exists")
        return content

def update_message_functions(content):
    """Update message sending functions to use escape_markdown"""
    # List of functions to update
    functions_to_fix = [
        'create_account',
        'balance',
        'deposit',
        'withdraw',
        'join_game',
        'game_status', 
        'profile',
        'leaderboard',
        'history'
    ]
    
    # Track modifications
    fixes_made = 0
    
    for func_name in functions_to_fix:
        # Find each reply_text call in the function that uses parse_mode='Markdown'
        pattern = rf'(async def {func_name}.*?)(await update\.message\.reply_text\(\s*f[\'"].*?\$.*?[\'"].*?,\s*parse_mode=[\'"]Markdown[\'"])'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            # Extract the whole message string
            message_pattern = r'await update\.message\.reply_text\(\s*(f[\'"].*?[\'"])'
            message_match = re.search(message_pattern, match.group(2))
            
            if message_match:
                # Get the original message
                original_message = message_match.group(1)
                
                # Create the escaped version
                escaped_message = f'escape_markdown({original_message})'
                
                # Replace in the function
                fixed_section = match.group(2).replace(original_message, escaped_message)
                content = content.replace(match.group(2), fixed_section)
                
                fixes_made += 1
                print(f"Fixed message in {func_name}()")
    
    # Also find any other reply_text calls with dollar signs
    pattern = r'(await (?:update\.message|context\.bot|query)\.(?:reply_text|send_message|edit_message_text)\(\s*f[\'"].*?\$.*?[\'"].*?,\s*parse_mode=[\'"]Markdown[\'"])'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        # Extract the whole message string
        message_pattern = r'(?:reply_text|send_message|edit_message_text)\(\s*(f[\'"].*?[\'"])'
        message_match = re.search(message_pattern, match.group(1))
        
        if message_match:
            # Get the original message
            original_message = message_match.group(1)
            
            # Create the escaped version
            escaped_message = f'escape_markdown({original_message})'
            
            # Replace in the content
            fixed_section = match.group(1).replace(original_message, escaped_message)
            content = content.replace(match.group(1), fixed_section)
            
            fixes_made += 1
            print(f"Fixed additional message call")
    
    print(f"Total message fixes: {fixes_made}")
    return content

def main():
    """Apply all fixes"""
    file_path = 'telegram_bot.py'
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    # Add the escape_markdown function
    content = add_escape_markdown_function(file_path)
    
    # Update message functions to use escape_markdown
    content = update_message_functions(content)
    
    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\nAll fixes applied! This should resolve the Markdown escaping issues.")
    print("Restart your bot for the changes to take effect.")

if __name__ == "__main__":
    main() 