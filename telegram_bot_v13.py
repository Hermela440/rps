import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters
)
from datetime import datetime
import os
import asyncio
from decimal import Decimal
import json
import pytz
from typing import Optional, List, Dict, Any
import random
import time

from app import db
from models import User, Game, GameParticipant, Transaction, WithdrawalRequest
from utils import (
    get_user_by_telegram_id,
    format_currency,
    user_exists,
    cooldown,
    admin_required,
    update_user_activity,
    get_leaderboard,
    validate_username
)
from admin import AdminService
from config import (
    BOT_TOKEN,
    ADMIN_USERS,
    LOGGER,
    BET_AMOUNT_DEFAULT,
    MIN_DEPOSIT_AMOUNT,
    MAX_DEPOSIT_AMOUNT,
    MIN_WITHDRAW_AMOUNT,
    MAX_WITHDRAW_AMOUNT
)

# Platform fee percentage for game winnings
PLATFORM_FEE_PERCENT = 5.0

@cooldown()
async def create_account(update: Update, context: CallbackContext) -> None:
    """Create a new user account."""
    try:
        telegram_id = update.effective_user.id
        telegram_username = update.effective_user.username
        
        # Log the request
        LOGGER.info(f"Account creation request from Telegram ID: {telegram_id}, Username: {telegram_username}")
    
        # Check if user already exists
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            await update.message.reply_text(
                "❌ You already have an account.\n"
                f"Balance: ETB {float(existing_user.balance):,.2f}\n"
                "Use /join_game to play!"
            )
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
                f"❌ Username '{username}' must be between 3 and 32 characters."
            )
            return
            
        # Simplified validation to avoid regex issues
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not all(c in valid_chars for c in username):
            await update.message.reply_text(
                f"❌ Username '{username}' contains invalid characters.\n"
                "Only letters, numbers, underscores, and hyphens are allowed."
            )
            return
        
        # Check if username is already taken
        try:
            existing_name = User.query.filter_by(username=username).first()
            if existing_name:
                await update.message.reply_text(
                    f"❌ Username '{username}' is already taken.\n"
                    "Please try another one."
                )
                return
        except Exception as e:
            LOGGER.error(f"Database error checking username: {e}")
            await update.message.reply_text("Error checking username availability. Please try again later.")
            return
        
        # Create new user with error handling
        try:
            # Create user with welcome bonus
            welcome_bonus = 100.0  # ETB 100 welcome bonus
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=welcome_bonus,
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                is_admin=telegram_id in ADMIN_USERS
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Create welcome bonus transaction
            transaction = Transaction(
                user_id=user.id,
                amount=welcome_bonus,
                transaction_type='bonus',
                status='completed',
                reference_id='welcome_bonus',
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(transaction)
            db.session.commit()
            
            LOGGER.info(f"Account created successfully for {username} (ID: {user.id})")
            
            # Success message with main menu keyboard
            keyboard = [
                [KeyboardButton("💰 Account"), KeyboardButton("🎮 Game")],
                [KeyboardButton("📊 Stats"), KeyboardButton("ℹ️ Help")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"✅ Account created!\n"
                f"Balance: ETB {welcome_bonus:,.2f}\n"
                "Use /join_game to enter the game room.",
                reply_markup=reply_markup
            )

        except Exception as e:
            LOGGER.error(f"Error creating account: {e}")
            db.session.rollback()
            await update.message.reply_text("❌ Error creating account. Please try again later.")

    except Exception as e:
        LOGGER.error(f"Unexpected error in create_account: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        if user:
            # User exists - show main menu
            keyboard = [
                [KeyboardButton("💰 Account"), KeyboardButton("🎮 Game")],
                [KeyboardButton("📊 Stats"), KeyboardButton("ℹ️ Help")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            welcome_text = (
                f"👋 Welcome back, {user.username}!\n\n"
                "🎮 *Rock Paper Scissors Game*\n\n"
                f"💰 Your balance: ETB {float(user.balance):,.2f}\n\n"
                "What would you like to do?"
            )
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            # New user - show create account button
            keyboard = [[
                InlineKeyboardButton("✨ Create Account", callback_data="create_account"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_text = (
                "👋 Welcome to Rock Paper Scissors Bot! 🎮\n\n"
                "Please create your account to begin."
            )
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
            
    except Exception as e:
        LOGGER.error(f"Error in start command: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a help message when the command /help is issued."""
    help_text = "📚 *Rock Paper Scissors Commands* 📚\n\n"
    
    for category, commands in COMMANDS.items():
        help_text += f"{category}:\n"
        for cmd, desc in commands.items():
            help_text += f"{cmd} - {desc}\n"
        help_text += "\n"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about(update: Update, context: CallbackContext) -> None:
    """Send information about the bot."""
    await update.message.reply_text(
        "🎮 *Rock Paper Scissors Bot* 🎮\n\n"
        "A fun and interactive bot that lets you play Rock Paper Scissors with other players!\n\n"
        "Features:\n"
        "• Play with custom bet amounts\n"
        "• Win rewards for victories\n"
        "• Track your stats and history\n"
        "• Compete on the leaderboard\n\n"
        "Created with ❤️ by @YourUsername",
        parse_mode='Markdown'
    )

@cooldown()
async def delete_account(update: Update, context: CallbackContext) -> None:
    """Delete a user account."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with confirm/cancel buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=f"delete_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"delete_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store user ID in context for callback handling
        context.user_data['pending_delete'] = user.id
        
        await update.message.reply_text(
            "⚠️ *Are you sure you want to delete your account?* ⚠️\n\n"
            "This action cannot be undone. All your data, including:\n"
            "• Balance\n"
            "• Game history\n"
            "• Statistics\n\n"
            "Will be permanently deleted.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in delete_account: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
async def balance(update: Update, context: CallbackContext) -> None:
    """Check user balance."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with deposit/withdraw buttons
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 *Your Balance*\n\n"
            f"Current balance: ETB {user.balance:.2f}\n\n"
            f"Use the buttons below to manage your funds:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error checking balance: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def deposit(update: Update, context: CallbackContext) -> None:
    """Handle deposit command."""
    if not user_exists(update):
        return
    
    try:
        # Create inline keyboard with preset amounts
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="deposit_10"),
                InlineKeyboardButton("$20", callback_data="deposit_20"),
                InlineKeyboardButton("$50", callback_data="deposit_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="deposit_100"),
                InlineKeyboardButton("$200", callback_data="deposit_200"),
                InlineKeyboardButton("$500", callback_data="deposit_500")
            ],
            [InlineKeyboardButton("Custom Amount", callback_data="deposit_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "💰 *Deposit Funds*\n\n"
            "Choose an amount to deposit or select custom amount:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in deposit command: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def withdraw(update: Update, context: CallbackContext) -> None:
    """Handle withdraw command."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create inline keyboard with preset amounts
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="withdraw_10"),
                InlineKeyboardButton("$20", callback_data="withdraw_20"),
                InlineKeyboardButton("$50", callback_data="withdraw_50")
            ],
            [
                InlineKeyboardButton("$100", callback_data="withdraw_100"),
                InlineKeyboardButton("$200", callback_data="withdraw_200"),
                InlineKeyboardButton("$500", callback_data="withdraw_500")
            ],
            [InlineKeyboardButton("Custom Amount", callback_data="withdraw_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"💸 *Withdraw Funds*\n\n"
            f"Current balance: ${user.balance:.2f}\n\n"
            f"Choose an amount to withdraw or select custom amount:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in withdraw command: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

@cooldown()
def history(update: Update, context: CallbackContext) -> None:
    """Show user transaction history."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Get last 10 transactions
        transactions = get_user_transactions(user.id, limit=10)
        
        if not transactions:
            update.message.reply_text(
                "📜 *Transaction History*\n\n"
                "No transactions found.",
                parse_mode='Markdown'
            )
            return
        
        history_text = "📜 *Transaction History*\n\n"
        for tx in transactions:
            amount = f"+${tx.amount:.2f}" if tx.type == 'deposit' else f"-${tx.amount:.2f}"
            status = "✅" if tx.status == 'completed' else "⏳"
            history_text += f"{status} {amount} - {tx.type.title()} - {tx.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Create navigation buttons
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Previous", callback_data="history_prev"),
                InlineKeyboardButton("Next ➡️", callback_data="history_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error showing history: {e}")
        update.message.reply_text("An error occurred. Please try again later.")

async def admin_stats(update: Update, context: CallbackContext):
    """Get system-wide statistics (admin only)"""
    if not await is_admin(update, context):
        return
    
    stats = AdminService.get_system_stats()
    if not stats:
        await update.message.reply_text("Error fetching system stats")
        return
    
    message = (
        "📊 *System Statistics*\n\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"➕ New Users (24h): {stats['new_users_24h']}\n"
        f"🎮 Total Games: {stats['total_games']}\n"
        f"🎲 Games (24h): {stats['games_24h']}\n"
        f"👤 Active Users (24h): {stats['active_users_24h']}\n"
        f"💰 Total Volume: ETB {stats['total_volume']:,.2f}\n"
        f"📈 Volume (24h): ETB {stats['volume_24h']:,.2f}\n"
        f"⏳ Pending Withdrawals: {stats['pending_withdrawals']}"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_search(update: Update, context: CallbackContext):
    """Search for users (admin only)"""
    if not await is_admin(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a search query")
        return
    
    query = ' '.join(context.args)
    users = AdminService.search_user(query)
    
    if not users:
        await update.message.reply_text("No users found")
        return
    
    message = "🔍 *Search Results*\n\n"
    for user in users:
        message += (
            f"*ID:* {user.telegram_id}\n"
            f"*Username:* @{user.username}\n"
            f"*Balance:* ETB {float(user.balance):,.2f}\n"
            f"*Joined:* {user.created_at.strftime('%Y-%m-%d')}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_user(update: Update, context: CallbackContext):
    """Get detailed user information (admin only)"""
    if not await is_admin(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a user ID")
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID")
        return
    
    details = AdminService.get_user_details(user_id)
    if not details:
        await update.message.reply_text("User not found")
        return
    
    user = details['user']
    message = (
        f"👤 *User Details*\n\n"
        f"*ID:* {user.telegram_id}\n"
        f"*Username:* @{user.username}\n"
        f"*Balance:* ETB {float(user.balance):,.2f}\n"
        f"*Joined:* {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"*Last Active:* {user.last_active.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"*Total Games:* {details['total_games']}\n"
        f"*Total Wagered:* ETB {float(details['total_wagered']):,.2f}\n\n"
    )
    
    if details['recent_transactions']:
        message += "*Recent Transactions:*\n"
        for tx in details['recent_transactions']:
            message += (
                f"• {tx.transaction_type.title()}: ETB {float(tx.amount):,.2f} "
                f"({tx.status}) - {tx.created_at.strftime('%Y-%m-%d')}\n"
            )
    
    if details['recent_games']:
        message += "\n*Recent Games:*\n"
        for game in details['recent_games']:
            message += (
                f"• Game #{game.id}: ETB {float(game.bet_amount):,.2f} "
                f"({game.status}) - {game.created_at.strftime('%Y-%m-%d')}\n"
            )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_adjust(update: Update, context: CallbackContext):
    """Adjust a user's balance (admin only)"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /admin_adjust <user_id> <amount> <reason>"
        )
        return
    
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        reason = ' '.join(context.args[2:])
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid arguments")
        return
    
    if AdminService.adjust_balance(user_id, amount, reason):
        await update.message.reply_text(
            f"Successfully adjusted balance for user {user_id} "
            f"by ETB {amount:,.2f}\nReason: {reason}"
        )
    else:
        await update.message.reply_text("Failed to adjust balance")

async def admin_withdrawals(update: Update, context: CallbackContext):
    """List pending withdrawal requests (admin only)"""
    if not await is_admin(update, context):
        return
    
    withdrawals = AdminService.get_pending_withdrawals()
    if not withdrawals:
        await update.message.reply_text("No pending withdrawals")
        return
    
    message = "⏳ *Pending Withdrawals*\n\n"
    for w in withdrawals:
        user = User.query.get(w.user_id)
        message += (
            f"*Request #{w.id}*\n"
            f"User: @{user.username}\n"
            f"Amount: ETB {float(w.amount):,.2f}\n"
            f"Bank: {w.bank_name}\n"
            f"Account: {w.account_number}\n"
            f"Requested: {w.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_cancel_game(update: Update, context: CallbackContext):
    """Cancel an active game (admin only)"""
    if not await is_admin(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a game ID")
        return
    
    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid game ID")
        return
    
    if AdminService.cancel_game(game_id):
        await update.message.reply_text(f"Successfully cancelled game #{game_id}")
    else:
        await update.message.reply_text("Failed to cancel game")

async def is_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is an admin"""
    user = User.query.filter_by(telegram_id=update.effective_user.id).first()
    if not user or not user.is_admin:
        await update.message.reply_text("This command is for admins only")
        return False
    return True

async def is_super_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is a super admin"""
    return update.effective_user.id == SUPER_ADMIN_ID

async def admin_toggle(update: Update, context: CallbackContext) -> None:
    """Toggle admin status for a user (super admin only)."""
    if not await is_super_admin(update, context):
        return
    
    try:
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "Usage: /admin_toggle <user_id>"
            )
            return
        
        target_id = int(context.args[0])
        target_user = User.query.filter_by(telegram_id=target_id).first()
        
        if not target_user:
            await update.message.reply_text("❌ User not found.")
            return
        
        # Toggle admin status
        target_user.is_admin = not target_user.is_admin
        db.session.commit()
        
        status = "granted" if target_user.is_admin else "revoked"
        await update.message.reply_text(
            f"✅ Admin status {status} for @{target_user.username}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
    except Exception as e:
        LOGGER.error(f"Error in admin_toggle: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

def register_admin_handlers(application: Application):
    """Register admin command handlers"""
    application.add_handler(CommandHandler('admin_stats', admin_stats))
    application.add_handler(CommandHandler('admin_search', admin_search))
    application.add_handler(CommandHandler('admin_user', admin_user))
    application.add_handler(CommandHandler('admin_adjust', admin_adjust))
    application.add_handler(CommandHandler('admin_withdrawals', admin_withdrawals))
    application.add_handler(CommandHandler('admin_cancel_game', admin_cancel_game))
    application.add_handler(CommandHandler('admin_toggle', admin_toggle))

async def send_battle_animation(context, chat_id, moves_data):
    """Send battle animation to a chat."""
    try:
        # Get the appropriate animation based on moves
        animation_path = get_rps_animation(moves_data)
        
        with open(animation_path, 'rb') as animation:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=animation,
                caption="🎥 Simulating Battle..."
            )
    except Exception as e:
        LOGGER.error(f"Error sending battle animation: {e}")

def get_rps_animation(moves_data):
    """Get the appropriate animation file based on moves."""
    # Sort moves to get a consistent key
    sorted_moves = sorted(moves_data.values())
    moves_key = '_'.join(sorted_moves)
    
    # Map of move combinations to animation files
    animations = {
        'paper_rock_scissors': 'static/animations/rps-battle-all.gif',
        'paper_paper_paper': 'static/animations/rps-tie.gif',
        'rock_rock_rock': 'static/animations/rps-tie.gif',
        'scissors_scissors_scissors': 'static/animations/rps-tie.gif',
        'paper_rock': 'static/animations/paper-beats-rock.gif',
        'scissors_paper': 'static/animations/scissors-beats-paper.gif',
        'rock_scissors': 'static/animations/rock-beats-scissors.gif'
    }
    
    return animations.get(moves_key, 'static/animations/rps-battle-default.gif')

@cooldown()
def wallet(update: Update, context: CallbackContext) -> None:
    """Handle wallet command - shows different options for users and admins."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Create user wallet keyboard
        user_keyboard = [
            [
                InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton("📊 Transaction History", callback_data="history"),
                InlineKeyboardButton("❌ Delete Account", callback_data="delete_confirm")
            ]
        ]
        
        # Add admin panel button if user is admin
        if user.is_admin:
            admin_keyboard = [
                [
                    InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
                    InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")
                ],
                [
                    InlineKeyboardButton("🎮 Force Start Game", callback_data="admin_force_start"),
                    InlineKeyboardButton("📈 System Stats", callback_data="admin_stats")
                ]
            ]
            keyboard = user_keyboard + [[InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")]]
        else:
            keyboard = user_keyboard
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Format balance with commas for thousands
        formatted_balance = "{:,.2f}".format(float(user.balance))
        
        message = (
            f"💰 *Your Wallet*\n\n"
            f"Balance: ETB {formatted_balance}\n\n"
            f"Select an option:"
        )
        
        update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        LOGGER.error(f"Error in wallet command: {e}")
        update.message.reply_text("❌ An error occurred. Please try again later.")

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Admin panel handling
        if query.data == "admin_panel":
            user = get_user_by_telegram_id(query.from_user.id)
            if not user or not user.is_admin:
                await query.message.edit_text("❌ You don't have admin privileges.")
                return
            
            keyboard = [
                [
                    InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
                    InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")
                ],
                [
                    InlineKeyboardButton("🎮 Force Start Game", callback_data="admin_force_start"),
                    InlineKeyboardButton("📈 System Stats", callback_data="admin_stats")
                ],
                [InlineKeyboardButton("🔙 Back to Wallet", callback_data="back_to_wallet")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                "🛠 *Admin Panel*\n\n"
                "Select an admin action:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_add_balance":
            # Store state in user_data
            context.user_data['admin_action'] = 'add_balance'
            await query.message.edit_text(
                "💰 *Add Balance*\n\n"
                "Format: `<user_id> <amount> <reason>`\n"
                "Example: `123456789 100 Welcome bonus`\n\n"
                "Reply with the command or click Cancel.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_view_users":
            users = User.query.order_by(User.created_at.desc()).limit(10).all()
            message = "👥 *Recent Users*\n\n"
            
            for user in users:
                message += (
                    f"*ID:* {user.telegram_id}\n"
                    f"*Username:* @{user.username}\n"
                    f"*Balance:* ETB {float(user.balance):,.2f}\n"
                    f"*Joined:* {user.created_at.strftime('%Y-%m-%d')}\n\n"
                )
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_force_start":
            # Get waiting games
            waiting_games = Game.query.filter_by(status='waiting').all()
            
            if not waiting_games:
                message = "❌ No waiting games found to force start."
            else:
                # Force start the oldest waiting game
                game = waiting_games[0]
                game.status = 'active'
                db.session.commit()
                
                message = f"✅ Force started game #{game.id}"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                message,
                reply_markup=reply_markup
            )
        
        elif query.data == "admin_stats":
            stats = AdminService.get_system_stats()
            message = (
                "📊 *System Statistics*\n\n"
                f"👥 Total Users: {stats['total_users']}\n"
                f"➕ New Users (24h): {stats['new_users_24h']}\n"
                f"🎮 Total Games: {stats['total_games']}\n"
                f"🎲 Games (24h): {stats['games_24h']}\n"
                f"👤 Active Users (24h): {stats['active_users_24h']}\n"
                f"💰 Total Volume: ETB {stats['total_volume']:,.2f}\n"
                f"📈 Volume (24h): ETB {stats['volume_24h']:,.2f}\n"
                f"⏳ Pending Withdrawals: {stats['pending_withdrawals']}"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data == "back_to_wallet":
            # Return to main wallet view
            user = get_user_by_telegram_id(query.from_user.id)
            formatted_balance = "{:,.2f}".format(float(user.balance))
            
            keyboard = [
                [
                    InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
                    InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
                ],
                [
                    InlineKeyboardButton("📊 Transaction History", callback_data="history"),
                    InlineKeyboardButton("❌ Delete Account", callback_data="delete_confirm")
                ]
            ]
            
            if user.is_admin:
                keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                f"💰 *Your Wallet*\n\n"
                f"Balance: ETB {formatted_balance}\n\n"
                f"Select an option:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data.startswith("move_"):
            # Handle game moves
            _, game_id, move = query.data.split("_")
            game_id = int(game_id)
            
            # Get user and game
            user = get_user_by_telegram_id(query.from_user.id)
            game = Game.query.get(game_id)
            
            if not game or game.status != 'active':
                await query.message.reply_text("❌ This game is no longer active.")
                return
            
            # Get participant
            participant = GameParticipant.query.filter_by(
                game_id=game_id,
                user_id=user.id
            ).first()
            
            if not participant:
                await query.message.reply_text("❌ You are not part of this game.")
                return
            
            if participant.move:
                await query.message.reply_text("❌ You have already made your move.")
                return
            
            # Record the move
            participant.move = move
            participant.move_time = datetime.utcnow()
            db.session.commit()
            
            # Confirm move to user
            move_emojis = {"rock": "🪨", "paper": "🧻", "scissors": "✂️"}
            await query.message.edit_text(
                f"✅ You chose {move_emojis[move]} {move.title()}!\n"
                "Waiting for other players..."
            )
            
            # Check if all players have moved
            all_participants = GameParticipant.query.filter_by(game_id=game_id).all()
            moves_made = sum(1 for p in all_participants if p.move)
            
            if moves_made == 3:
                # All players have moved - determine winner
                moves = {p.user_id: p.move for p in all_participants}
                usernames = {p.user_id: User.query.get(p.user_id).username for p in all_participants}
                
                # Get unique moves
                unique_moves = set(moves.values())
                
                # Send initial moves summary to all participants
                moves_summary = "\n".join(
                    f"{move_emojis[move]} {usernames[uid]} chose {move.title()}"
                    for uid, move in moves.items()
                )
                
                # Send battle animation to all participants
                for p in all_participants:
                    user_id = User.query.get(p.user_id).telegram_id
                    await send_battle_animation(context, user_id, moves)
                
                # Calculate results after a short delay for animation
                await asyncio.sleep(2)  # Wait for animation to play
                
                if len(unique_moves) == 1:
                    # It's a tie - refund everyone
                    result_message = (
                        "🤝 It's a tie! Everyone chose the same move.\n"
                        "All bets have been refunded."
                    )
                    
                    for p in all_participants:
                        user = User.query.get(p.user_id)
                        user.balance += game.bet_amount
                        
                        # Create refund transaction
                        transaction = Transaction(
                            user_id=p.user_id,
                            amount=game.bet_amount,
                            transaction_type='game_refund',
                            status='completed',
                            reference_id=f'tie_refund_{game_id}',
                            created_at=datetime.utcnow(),
                            completed_at=datetime.utcnow()
                        )
                        db.session.add(transaction)
                    
                elif len(unique_moves) == 3:
                    # It's a tie - refund everyone
                    result_message = (
                        "🤝 It's a tie! All different moves were chosen.\n"
                        "All bets have been refunded."
                    )
                    
                    for p in all_participants:
                        user = User.query.get(p.user_id)
                        user.balance += game.bet_amount
                        
                        # Create refund transaction
                        transaction = Transaction(
                            user_id=p.user_id,
                            amount=game.bet_amount,
                            transaction_type='game_refund',
                            status='completed',
                            reference_id=f'tie_refund_{game_id}',
                            created_at=datetime.utcnow(),
                            completed_at=datetime.utcnow()
                        )
                        db.session.add(transaction)
                
                else:
                    # Determine winner based on moves
                    winners = []
                    total_pot = game.bet_amount * 3
                    win_reason = ""
                    
                    if 'rock' in unique_moves and 'scissors' in unique_moves:
                        winners.extend(uid for uid, move in moves.items() if move == 'rock')
                        win_reason = "Rock crushes Scissors"
                    elif 'scissors' in unique_moves and 'paper' in unique_moves:
                        winners.extend(uid for uid, move in moves.items() if move == 'scissors')
                        win_reason = "Scissors cuts Paper"
                    elif 'paper' in unique_moves and 'rock' in unique_moves:
                        winners.extend(uid for uid, move in moves.items() if move == 'paper')
                        win_reason = "Paper covers Rock"
                    
                    # Calculate winnings
                    winnings_per_player = total_pot / len(winners)
                    
                    # Update balances and create transactions
                    for winner_id in winners:
                        winner = User.query.get(winner_id)
                        winner.balance += winnings_per_player
                        
                        transaction = Transaction(
                            user_id=winner_id,
                            amount=winnings_per_player,
                            transaction_type='game_win',
                            status='completed',
                            reference_id=f'win_{game_id}',
                            created_at=datetime.utcnow(),
                            completed_at=datetime.utcnow()
                        )
                        db.session.add(transaction)
                    
                    # Create result message
                    winner_names = [f"@{usernames[uid]}" for uid in winners]
                    result_message = (
                        f"🏆 Winner: {', '.join(winner_names)} ({win_reason})\n"
                        f"💰 +{winnings_per_player:.0f} ETB added to balance!"
                    )
                
                # Mark game as completed
                game.status = 'completed'
                game.completed_at = datetime.utcnow()
                db.session.commit()
                
                # Send final results to all participants
                final_message = (
                    f"{moves_summary}\n\n"
                    f"{result_message}"
                )
                
                for p in all_participants:
                    context.bot.send_message(
                        User.query.get(p.user_id).telegram_id,
                        final_message
                    )
        
        elif query.data == "create_account":
            # Show username input instructions
            text = (
                "To create your account, use the command:\n\n"
                "/create_account [username]\n\n"
                "Example: /create_account john123\n\n"
                "Username requirements:\n"
                "• 3-32 characters\n"
                "• Letters, numbers, underscores, and hyphens only\n"
                "• Must be unique"
            )
            await query.message.edit_text(text)
            
        elif query.data == "help":
            # Show help message
            text = (
                "🎮 *Rock Paper Scissors Bot Help*\n\n"
                "*Getting Started:*\n"
                "1. Create an account with /create_account\n"
                "2. Join a game with /join_game\n"
                "3. Make your choice and win rewards!\n\n"
                "*Main Commands:*\n"
                "• /balance - Check your balance\n"
                "• /deposit - Add funds\n"
                "• /withdraw - Withdraw funds\n"
                "• /history - View transactions\n"
                "• /profile - View your stats\n"
                "• /leaderboard - See top players\n\n"
                "*Game Commands:*\n"
                "• /join_game - Join or create a game\n"
                "• /game_status - Check current game\n"
                "• /simulate - Play against AI\n\n"
                "*Need more help? Use /help for full command list.*"
            )
            await query.message.edit_text(text, parse_mode='Markdown')
        
    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}")
        await query.message.reply_text("❌ An error occurred. Please try again later.")

@cooldown()
def join_game(update: Update, context: CallbackContext) -> None:
    """Join or create a game."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Check if user is already in a game
        active_game = GameParticipant.query.filter_by(
            user_id=user.id,
            status='active'
        ).first()
        
        if active_game:
            update.message.reply_text(
                "❌ You are already in an active game.\n"
                "Use /game_status to check your current game."
            )
            return
        
        # Get or set bet amount
        bet_amount = BET_AMOUNT_DEFAULT
        if context.args:
            try:
                bet_amount = float(context.args[0])
                if bet_amount <= 0:
                    update.message.reply_text("❌ Bet amount must be greater than 0 ETB.")
                    return
            except ValueError:
                update.message.reply_text("❌ Invalid bet amount. Please enter a valid number.")
                return
        
        # Check user balance
        if user.balance < bet_amount:
            update.message.reply_text(
                f"❌ Insufficient balance.\n"
                f"Required: ETB {bet_amount:,.2f}\n"
                f"Your balance: ETB {float(user.balance):,.2f}\n\n"
                "Use /deposit to add funds."
            )
            return
        
        # Look for an existing waiting game with same bet amount
        waiting_game = Game.query.filter_by(
            status='waiting',
            bet_amount=bet_amount
        ).first()
        
        if waiting_game:
            # Join existing game
            participants = GameParticipant.query.filter_by(game_id=waiting_game.id).all()
            
            if len(participants) >= 3:
                update.message.reply_text("❌ This game is already full. Please join another game or create a new one.")
                return
            
            # Check if user is already in this game
            for participant in participants:
                if participant.user_id == user.id:
                    update.message.reply_text("❌ You are already in this game.")
                    return
            
            # Add user to game
            participant = GameParticipant(
                game_id=waiting_game.id,
                user_id=user.id,
                status='active',
                joined_at=datetime.utcnow()
            )
            
            # Deduct bet amount
            user.balance -= bet_amount
            
            db.session.add(participant)
            db.session.commit()
            
            # Get updated participant list
            all_participants = GameParticipant.query.filter_by(game_id=waiting_game.id).all()
            participant_list = "\n".join(
                f"{i+1}. @{User.query.get(p.user_id).username}"
                for i, p in enumerate(all_participants)
            )
            
            if len(all_participants) < 3:
                # Game still waiting for more players
                message = (
                    f"✅ You joined the game!\n\n"
                    f"💰 Bet amount: ETB {bet_amount:,.2f}\n\n"
                    f"👥 Current players ({len(all_participants)}/3):\n"
                    f"{participant_list}\n\n"
                    f"Waiting for {3 - len(all_participants)} more players..."
                )
                update.message.reply_text(message)
                
                # Notify other participants
                for p in all_participants:
                    if p.user_id != user.id:
                        context.bot.send_message(
                            User.query.get(p.user_id).telegram_id,
                            f"@{user.username} joined the game!\n"
                            f"Waiting for {3 - len(all_participants)} more players..."
                        )
            else:
                # Game is full - start the game!
                waiting_game.status = 'active'
                db.session.commit()
                
                # Create inline keyboard for moves
                keyboard = [[
                    InlineKeyboardButton("🪨 Rock", callback_data=f"move_{waiting_game.id}_rock"),
                    InlineKeyboardButton("🧻 Paper", callback_data=f"move_{waiting_game.id}_paper"),
                    InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{waiting_game.id}_scissors")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send game start message to all participants
                game_start_message = (
                    f"👥 Players in this round:\n"
                    f"{participant_list}\n\n"
                    f"🎮 Game is starting... Choose your move!"
                )
                
                for p in all_participants:
                    context.bot.send_message(
                        User.query.get(p.user_id).telegram_id,
                        game_start_message,
                        reply_markup=reply_markup
                    )
        
        else:
            # Create new game
            game = Game(
                bet_amount=bet_amount,
                status='waiting',
                created_at=datetime.utcnow(),
                created_by=user.id
            )
            db.session.add(game)
            db.session.commit()
            
            # Add creator as first participant
            participant = GameParticipant(
                game_id=game.id,
                user_id=user.id,
                status='active',
                joined_at=datetime.utcnow()
            )
            
            # Deduct bet amount
            user.balance -= bet_amount
            
            db.session.add(participant)
            db.session.commit()
            
            message = (
                f"✅ Game created!\n\n"
                f"💰 Bet amount: ETB {bet_amount:,.2f}\n\n"
                f"👥 Current players (1/3):\n"
                f"1. @{user.username}\n\n"
                f"Waiting for 2 more players..."
            )
            update.message.reply_text(message)
        
    except Exception as e:
        LOGGER.error(f"Error in join_game: {e}")
        db.session.rollback()
        update.message.reply_text("❌ An error occurred. Please try again later.")

@cooldown()
async def game_status(update: Update, context: CallbackContext) -> None:
    """Check the status of current game."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Find active game participation
        participant = GameParticipant.query.join(Game).filter(
            GameParticipant.user_id == user.id,
            Game.status.in_(['waiting', 'active'])
        ).first()
        
        if not participant:
            await update.message.reply_text(
                "❌ You are not in any active game.\n"
                "Use /join_game to start or join a game!"
            )
            return
        
        game = participant.game
        all_participants = GameParticipant.query.filter_by(game_id=game.id).all()
        
        # Format participant list
        participant_list = []
        for p in all_participants:
            p_user = User.query.get(p.user_id)
            status = "✅" if p.move else "⏳"
            participant_list.append(f"{status} @{p_user.username}")
        
        participants_text = "\n".join(participant_list)
        
        if game.status == 'waiting':
            message = (
                f"🎮 *Game #{game.id} Status*\n\n"
                f"💰 Bet amount: ETB {float(game.bet_amount):,.2f}\n\n"
                f"👥 Current players ({len(all_participants)}/3):\n"
                f"{participants_text}\n\n"
                f"Waiting for {3 - len(all_participants)} more players..."
            )
        else:
            # Show game status with moves
            moves_made = sum(1 for p in all_participants if p.move)
            message = (
                f"🎮 *Game #{game.id} Status*\n\n"
                f"💰 Bet amount: ETB {float(game.bet_amount):,.2f}\n\n"
                f"👥 Players ({moves_made}/3 moved):\n"
                f"{participants_text}\n\n"
            )
            
            # If user hasn't moved yet, show move buttons
            if not participant.move:
                keyboard = [[
                    InlineKeyboardButton("🪨 Rock", callback_data=f"move_{game.id}_rock"),
                    InlineKeyboardButton("🧻 Paper", callback_data=f"move_{game.id}_paper"),
                    InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{game.id}_scissors")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message += "Make your move!"
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        LOGGER.error(f"Error in game_status: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

@cooldown()
async def simulate_rps(update: Update, context: CallbackContext) -> None:
    """Simulate a game against AI players."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Check if user is already in a game
        active_game = GameParticipant.query.filter_by(
            user_id=user.id,
            status='active'
        ).first()
        
        if active_game:
            await update.message.reply_text(
                "❌ You are already in an active game.\n"
                "Use /game_status to check your current game."
            )
            return
        
        # Get or set bet amount
        bet_amount = BET_AMOUNT_DEFAULT
        if context.args:
            try:
                bet_amount = float(context.args[0])
                if bet_amount <= 0:
                    await update.message.reply_text("❌ Bet amount must be greater than 0 ETB.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid bet amount. Please enter a valid number.")
                return
        
        # Check user balance
        if user.balance < bet_amount:
            await update.message.reply_text(
                f"❌ Insufficient balance.\n"
                f"Required: ETB {bet_amount:,.2f}\n"
                f"Your balance: ETB {float(user.balance):,.2f}\n\n"
                "Use /deposit to add funds."
            )
            return
        
        # Create AI players
        ai_names = ["🤖 AI-Alpha", "🤖 AI-Beta"]
        ai_users = []
        
        for ai_name in ai_names:
            ai_user = User(
                telegram_id=random.randint(1000000, 9999999),
                username=ai_name,
                balance=1000000,  # Large balance for AI
                is_admin=False,
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow()
            )
            db.session.add(ai_user)
            ai_users.append(ai_user)
        
        try:
            db.session.commit()
        except Exception as e:
            LOGGER.error(f"Error creating AI users: {e}")
            db.session.rollback()
            await update.message.reply_text("❌ Error creating game. Please try again.")
            return
        
        # Create game
        game = Game(
            bet_amount=bet_amount,
            status='active',  # Start immediately
            created_at=datetime.utcnow(),
            created_by=user.id
        )
        db.session.add(game)
        
        try:
            db.session.commit()
        except Exception as e:
            LOGGER.error(f"Error creating game: {e}")
            db.session.rollback()
            await update.message.reply_text("❌ Error creating game. Please try again.")
            return
        
        # Add participants (user and AI)
        participants = []
        
        # Add human player
        human = GameParticipant(
            game_id=game.id,
            user_id=user.id,
            status='active',
            joined_at=datetime.utcnow()
        )
        participants.append(human)
        
        # Deduct bet amount from human
        user.balance -= bet_amount
        
        # Add AI players
        for ai_user in ai_users:
            ai_participant = GameParticipant(
                game_id=game.id,
                user_id=ai_user.id,
                status='active',
                joined_at=datetime.utcnow(),
                # AI makes move immediately
                move=random.choice(['rock', 'paper', 'scissors']),
                move_time=datetime.utcnow()
            )
            participants.append(ai_participant)
        
        # Add all participants
        for participant in participants:
            db.session.add(participant)
        
        try:
            db.session.commit()
        except Exception as e:
            LOGGER.error(f"Error adding participants: {e}")
            db.session.rollback()
            # Refund human player
            user.balance += bet_amount
            db.session.commit()
            await update.message.reply_text("❌ Error creating game. Please try again.")
            return
        
        # Create keyboard for moves
        keyboard = [[
            InlineKeyboardButton("🪨 Rock", callback_data=f"move_{game.id}_rock"),
            InlineKeyboardButton("🧻 Paper", callback_data=f"move_{game.id}_paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data=f"move_{game.id}_scissors")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Format participant list
        participant_list = "\n".join(
            f"{'✅' if p.move else '⏳'} @{User.query.get(p.user_id).username}"
            for p in participants
        )
        
        await update.message.reply_text(
            f"🎮 *Game #{game.id} Created!*\n\n"
            f"💰 Bet amount: ETB {bet_amount:,.2f}\n\n"
            f"👥 Players:\n{participant_list}\n\n"
            "Make your move!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error in simulate_rps: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

@cooldown()
async def leaderboard(update: Update, context: CallbackContext) -> None:
    """Show the global leaderboard."""
    try:
        # Get top players by total winnings
        top_players = User.query.filter(
            User.games_played > 0
        ).order_by(
            User.total_winnings.desc()
        ).limit(10).all()
        
        if not top_players:
            await update.message.reply_text(
                "📊 *Leaderboard*\n\n"
                "No games played yet!",
                parse_mode='Markdown'
            )
            return
        
        # Format leaderboard message
        message = "📊 *Global Leaderboard*\n\n"
        
        for i, player in enumerate(top_players, 1):
            # Calculate win rate
            win_rate = (player.games_won / player.games_played * 100) if player.games_played > 0 else 0
            
            # Add medal for top 3
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            message += (
                f"{medal} @{player.username}\n"
                f"💰 Winnings: ETB {float(player.total_winnings):,.2f}\n"
                f"🎮 Games: {player.games_played}\n"
                f"✨ Win Rate: {win_rate:.1f}%\n\n"
            )
        
        # Add footer with refresh info
        message += "_Updated in real-time_"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        LOGGER.error(f"Error showing leaderboard: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

@cooldown()
async def profile(update: Update, context: CallbackContext) -> None:
    """Show user profile and stats."""
    if not user_exists(update):
        return
    
    try:
        telegram_id = update.effective_user.id
        user = get_user_by_telegram_id(telegram_id)
        
        # Calculate stats
        win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
        
        # Get recent games
        recent_games = (
            GameParticipant.query.join(Game)
            .filter(GameParticipant.user_id == user.id)
            .order_by(Game.created_at.desc())
            .limit(5)
            .all()
        )
        
        # Get recent transactions
        recent_transactions = (
            Transaction.query
            .filter(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(5)
            .all()
        )
        
        # Format profile message
        message = (
            f"👤 *Profile: @{user.username}*\n\n"
            f"💰 Balance: ETB {float(user.balance):,.2f}\n"
            f"🎮 Games Played: {user.games_played}\n"
            f"🏆 Games Won: {user.games_won}\n"
            f"✨ Win Rate: {win_rate:.1f}%\n"
            f"💎 Total Winnings: ETB {float(user.total_winnings):,.2f}\n"
            f"📅 Joined: {user.created_at.strftime('%Y-%m-%d')}\n\n"
        )
        
        if recent_games:
            message += "*Recent Games:*\n"
            for participant in recent_games:
                game = participant.game
                result = "Won 🏆" if game.winner_id == user.id else "Lost 💔" if game.status == 'completed' else "Playing 🎮"
                message += (
                    f"• Game #{game.id}: {result}\n"
                    f"  Bet: ETB {float(game.bet_amount):,.2f}\n"
                )
            message += "\n"
        
        if recent_transactions:
            message += "*Recent Transactions:*\n"
            for tx in recent_transactions:
                amount = f"+ETB {float(tx.amount):,.2f}" if tx.amount > 0 else f"ETB {float(tx.amount):,.2f}"
                status = "✅" if tx.status == 'completed' else "⏳" if tx.status == 'pending' else "❌"
                message += f"• {status} {amount} ({tx.transaction_type})\n"
        
        # Create inline keyboard for actions
        keyboard = [
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton("🎮 Play Game", callback_data="join_game"),
                InlineKeyboardButton("📊 Leaderboard", callback_data="leaderboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        LOGGER.error(f"Error showing profile: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def handle_menu_button(update: Update, context: CallbackContext) -> None:
    """Handle menu button presses."""
    try:
        text = update.message.text
        
        if text == "💰 Account":
            await wallet(update, context)
        elif text == "🎮 Game":
            # Show game options
            keyboard = [
                [
                    InlineKeyboardButton("🎮 Join Game", callback_data="join_game"),
                    InlineKeyboardButton("🤖 Play vs AI", callback_data="simulate")
                ],
                [
                    InlineKeyboardButton("📊 Game Status", callback_data="game_status"),
                    InlineKeyboardButton("📜 Game History", callback_data="game_history")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎮 *Game Menu*\n\n"
                "Choose an option:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif text == "📊 Stats":
            # Show stats options
            keyboard = [
                [
                    InlineKeyboardButton("👤 My Profile", callback_data="profile"),
                    InlineKeyboardButton("📊 Leaderboard", callback_data="leaderboard")
                ],
                [
                    InlineKeyboardButton("📈 Transaction History", callback_data="history"),
                    InlineKeyboardButton("🏆 Achievements", callback_data="achievements")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📊 *Statistics Menu*\n\n"
                "Choose an option:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif text == "ℹ️ Help":
            await help_command(update, context)
    
    except Exception as e:
        LOGGER.error(f"Error handling menu button: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def unknown_command(update: Update, context: CallbackContext) -> None:
    """Handle unknown commands."""
    command = update.message.text.split()[0]
    await update.message.reply_text(
        f"❌ Unknown command: {command}\n"
        "Use /help to see available commands."
    )

def main():
    """Start the bot."""
    try:
        # Create the Application
        application = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about))
        application.add_handler(CommandHandler("create_account", create_account))
        application.add_handler(CommandHandler("delete_account", delete_account))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("deposit", deposit))
        application.add_handler(CommandHandler("withdraw", withdraw))
        application.add_handler(CommandHandler("join_game", join_game))
        application.add_handler(CommandHandler("simulate", simulate_rps))
        application.add_handler(CommandHandler("profile", profile))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("stats", admin_stats))
        application.add_handler(CommandHandler("cancel", admin_cancel_game))

        # Add callback query handler for menu buttons
        application.add_handler(CallbackQueryHandler(button_callback))

        # Add message handler for menu buttons
        application.add_handler(MessageHandler(filters.Regex("^(🎮 Join Game|💰 Balance|📊 Leaderboard|👤 Profile|❓ Help|ℹ️ About)$"), handle_menu_button))

        LOGGER.info("All command handlers registered successfully")
        LOGGER.info("Starting bot...")

        # Start the Bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        LOGGER.error("Error in bot startup: %s", str(e))
        LOGGER.exception("Full traceback:")
        raise e

if __name__ == "__main__":
    main() 