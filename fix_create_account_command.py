#!/usr/bin/env python3
"""
Comprehensive fix for the /create_account command to work for all users
"""

import os
import re

def check_files():
    """Check if required files exist"""
    required_files = ['telegram_bot.py', 'utils.py']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Error: {file} not found!")
            return False
    return True

def fix_create_account_function():
    """Fix the create_account function in telegram_bot.py"""
    file_path = 'telegram_bot.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the create_account function
    pattern = r'async def create_account\(update: Update, context: ContextTypes\.DEFAULT_TYPE\).*?(?=async def|\Z)'
    create_account_match = re.search(pattern, content, re.DOTALL)
    
    if not create_account_match:
        print("Could not find create_account function!")
        return
    
    # Get the original function
    original_function = create_account_match.group(0)
    
    # Create completely rewritten version of the function
    new_function = '''async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new user account."""
    try:
        telegram_id = update.effective_user.id
        telegram_username = update.effective_user.username
        
        # Log the request
        LOGGER.info(f"Account creation request from Telegram ID: {telegram_id}, Username: {telegram_username}")
        
        # Check if user already exists
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            await update.message.reply_text("You already have an account.")
            return
        
        # Get username from message or use Telegram username
        if context.args and len(context.args) > 0:
            username = context.args[0]
            LOGGER.info(f"Provided username: {username}")
        else:
            # Use Telegram username if available
            if telegram_username:
                username = telegram_username
                LOGGER.info(f"Using Telegram username: {username}")
            else:
                await update.message.reply_text(
                    "Please provide a username: /create_account [username]"
                )
                return
        
        # Simple username validation (3-32 chars, alphanumeric, underscores, hyphens)
        if len(username) < 3 or len(username) > 32:
            await update.message.reply_text(
                f"Username '{username}' must be between 3 and 32 characters."
            )
            return
            
        # Simplified validation to avoid regex issues
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not all(c in valid_chars for c in username):
            await update.message.reply_text(
                f"Username '{username}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed."
            )
            return
        
        # Check if username is already taken (with error handling)
        try:
            existing_name = User.query.filter_by(username=username).first()
            if existing_name:
                await update.message.reply_text(f"Username '{username}' is already taken. Please try another one.")
                return
        except Exception as e:
            LOGGER.error(f"Database error checking username: {e}")
            await update.message.reply_text("Error checking username availability. Please try again later.")
            return
        
        # Create new user with error handling
        try:
            # Create user
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=100.0,  # Starting balance
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                is_admin=telegram_id in ADMIN_USERS  # Set admin status if in admin list
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Get user ID after commit
            user_id = user.id
            
            # Create initial bonus transaction
            transaction = Transaction(
                user_id=user_id,
                amount=100.0,
                transaction_type='bonus',
                status='completed',
                reference_id='welcome_bonus',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            LOGGER.info(f"Account created successfully for {username} (ID: {user_id})")
            
            # Success message - without Markdown to avoid $ parsing issues
            await update.message.reply_text(
                f"Account created successfully! Welcome, {username}.\n"
                f"You've received a welcome bonus of $100.00 in your wallet.\n\n"
                f"Your current balance: ${user.balance:.2f}\n\n"
                f"Use /join_game to start playing!"
            )
            
        except Exception as e:
            LOGGER.error(f"Error creating account: {e}")
            db.session.rollback()
            await update.message.reply_text("Error creating account. Please try again later.")
            
    except Exception as e:
        LOGGER.error(f"Unexpected error in create_account: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again.")
'''
    
    # Replace the function
    updated_content = content.replace(original_function, new_function)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print("✅ Fixed create_account function in telegram_bot.py")

def fix_utils_validation():
    """Fix the validate_username function in utils.py"""
    file_path = 'utils.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the validate_username function
    pattern = r'def validate_username\(username\):.*?return [^\n]+'
    validate_match = re.search(pattern, content, re.DOTALL)
    
    if not validate_match:
        print("Could not find validate_username function in utils.py!")
        return
    
    # Get the original function
    original_function = validate_match.group(0)
    
    # Create new version
    new_function = '''def validate_username(username):
    """
    Validate a username.
    Username must be 3-32 characters and contain only letters, numbers, underscores, and hyphens.
    """
    import re
    
    # Basic length check
    if not username or len(username) < 3 or len(username) > 32:
        return False
    
    # Simple character validation - more permissive than regex
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return all(c in valid_chars for c in username)'''
    
    # Replace the function
    updated_content = content.replace(original_function, new_function)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print("✅ Fixed validate_username function in utils.py")

def disable_cooldowns():
    """Disable cooldowns for create_account command"""
    file_path = 'utils.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the cooldown decorator
    pattern = r'def cooldown\(seconds=None\):.*?return decorator'
    cooldown_match = re.search(pattern, content, re.DOTALL)
    
    if not cooldown_match:
        print("Could not find cooldown decorator in utils.py!")
        return
    
    # Modify the cooldown logic
    cooldown_code = cooldown_match.group(0)
    
    # Check if we need to update it
    if 'if command_name == \'create_account\':' not in cooldown_code:
        # Add a bypass for create_account
        modified_code = cooldown_code.replace(
            'async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):',
            'async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):\n'
            '            # Skip cooldown for create_account\n'
            '            command_name = func.__name__\n'
            '            if command_name == \'create_account\':\n'
            '                return await func(update, context, *args, **kwargs)\n'
        )
        
        # Replace in content
        updated_content = content.replace(cooldown_code, modified_code)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print("✅ Disabled cooldowns for create_account command")
    else:
        print("Cooldowns already disabled for create_account")

def add_debug_command():
    """Add a debug command to telegram_bot.py to help diagnose issues"""
    file_path = 'telegram_bot.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if debug command already exists
    if 'async def debug_command' in content:
        print("Debug command already exists")
        return
    
    # Find a good place to insert the debug command
    main_pos = content.find('async def main()')
    
    if main_pos == -1:
        print("Could not find main function!")
        return
    
    # Create the debug command
    debug_command = '''

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to help diagnose issues."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Print debug info to console
    LOGGER.info(f"Debug command called by {user_id} (@{username})")
    
    # Check if user exists in database
    user = get_user_by_telegram_id(user_id)
    
    # Send debug info to user
    message = f"Debug Info:\\n\\n"
    message += f"Telegram ID: {user_id}\\n"
    message += f"Telegram Username: {username or 'None'}\\n"
    
    if user:
        message += f"\\nDatabase Info:\\n"
        message += f"User ID: {user.id}\\n"
        message += f"Username: {user.username}\\n"
        message += f"Balance: ${user.balance:.2f}\\n"
        message += f"Admin: {'Yes' if user.is_admin else 'No'}\\n"
        message += f"Created: {user.created_at}\\n"
    else:
        message += f"\\nNot found in database.\\n"
        message += f"Use /create_account [username] to create an account.\\n"
    
    # Send without parse_mode to avoid formatting issues
    await update.message.reply_text(message)

'''
    
    # Insert the debug command
    updated_content = content[:main_pos] + debug_command + content[main_pos:]
    
    # Add the command handler
    handler_pattern = r'# Add callback query handler.*?\n.*?\)'
    handler_match = re.search(handler_pattern, updated_content, re.DOTALL)
    
    if handler_match:
        handler_pos = handler_match.end()
        debug_handler = '\n    # Add debug command\n    application.add_handler(CommandHandler("debug", debug_command))'
        updated_content = updated_content[:handler_pos] + debug_handler + updated_content[handler_pos:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print("✅ Added debug command to help diagnose issues")

def create_direct_account_script():
    """Create a script to directly add accounts to the database"""
    file_path = 'create_direct_account.py'
    
    script_content = '''#!/usr/bin/env python3
"""
Create an account directly in the database
"""

from app import app, db
from models import User, Transaction
from datetime import datetime
import sys

def create_account(telegram_id, username):
    """Create an account directly in the database"""
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(telegram_id=telegram_id).first()
        if existing_user:
            print(f"User already exists: {existing_user.username} (ID: {existing_user.id})")
            return
        
        # Check if username is taken
        existing_name = User.query.filter_by(username=username).first()
        if existing_name:
            print(f"Username '{username}' is already taken by user ID: {existing_name.id}")
            return
        
        # Create user
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=100.0,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create welcome bonus transaction
        transaction = Transaction(
            user_id=user.id,
            amount=100.0,
            transaction_type='bonus',
            status='completed',
            reference_id='welcome_bonus',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(transaction)
        db.session.commit()
        
        print(f"✅ Account created successfully for {username}")
        print(f"Telegram ID: {telegram_id}")
        print(f"Username: {username}")
        print(f"Initial balance: $100.00")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_direct_account.py <telegram_id> <username>")
        print("Example: python create_direct_account.py 1234567890 test_user")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
        
        create_account(telegram_id, username)
    except ValueError:
        print(f"Error: Invalid Telegram ID '{sys.argv[1]}'. Must be a number.")
        sys.exit(1)
'''
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("✅ Created script for direct account creation")
    print("  Usage: python create_direct_account.py <telegram_id> <username>")

def main():
    """Apply all fixes"""
    print("Comprehensive Fix for /create_account Command")
    print("===========================================\n")
    
    if not check_files():
        return
    
    # Apply all fixes
    fix_create_account_function()
    fix_utils_validation()
    disable_cooldowns()
    add_debug_command()
    create_direct_account_script()
    
    print("\n✅ All fixes applied!")
    print("\nTo use the fixes:")
    print("1. Restart your bot")
    print("2. Try /create_account [username]")
    print("3. If any issues persist, use the /debug command")
    print("4. For manual account creation, use:")
    print("   python create_direct_account.py <telegram_id> <username>")

if __name__ == "__main__":
    main() 