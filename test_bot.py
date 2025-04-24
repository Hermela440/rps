import logging
import asyncio
import os
import time
import hmac
import hashlib
import requests
from decimal import Decimal
import sqlite3
import traceback
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

def create_battle_animation(choices):
    """Placeholder for battle animation."""
    return None

def create_battle_result_image(choices, winner=None):
    """Placeholder for result image."""
    return None

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Get logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Chapa API configuration
CHAPA_SECRET_KEY = os.getenv('CHAPA_SECRET_KEY')
CHAPA_PUBLIC_KEY = os.getenv('CHAPA_PUBLIC_KEY')
CHAPA_WEBHOOK_URL = os.getenv('CHAPA_WEBHOOK_URL')
CHAPA_API_URL = "https://api.chapa.co/v1"

# Payment limits
MIN_DEPOSIT = 10  # Minimum deposit amount in ETB
MAX_WITHDRAWAL = 5000  # Maximum withdrawal amount in ETB

def verify_chapa_signature(request_data, signature):
    """Verify Chapa webhook signature."""
    try:
        secret = os.getenv("CHAPA_WEBHOOK_SECRET")
        if not secret or not signature:
            return False
            
        computed_signature = hmac.new(
            secret.encode(),
            request_data,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def verify_chapa_payment(tx_ref):
    """Verify a Chapa payment transaction."""
    try:
        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
        response = requests.get(
            f"{CHAPA_API_URL}/transaction/verify/{tx_ref}",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        return None

def get_db_connection():
    """Create a database connection."""
    try:
        conn = sqlite3.connect('rps_game.db', timeout=20)  # Add timeout for busy database
        conn.row_factory = sqlite3.Row
        
        # Enable foreign keys
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Set journal mode to WAL for better concurrency
        conn.execute('PRAGMA journal_mode = WAL')
        
        # Set synchronous mode to NORMAL for better performance while maintaining safety
        conn.execute('PRAGMA synchronous = NORMAL')
        
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}\n{traceback.format_exc()}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in database connection: {e}\n{traceback.format_exc()}")
        return None

def init_db():
    """Initialize the database with required tables."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not initialize database - connection failed")
            return False
            
        c = conn.cursor()
        
        # Enable foreign keys
        c.execute('PRAGMA foreign_keys = ON')
        
        # Create users table with stats columns
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                balance DECIMAL DEFAULT 0.0 CHECK (balance >= 0),
                total_games INTEGER DEFAULT 0 CHECK (total_games >= 0),
                games_won INTEGER DEFAULT 0 CHECK (games_won >= 0),
                total_earnings DECIMAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phone_number TEXT
            )
        ''')
        
        # Create transactions table with better constraints and Chapa support
        c.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('deposit', 'withdraw', 'bet', 'win', 'bonus', 'refund')),
                amount DECIMAL NOT NULL CHECK (amount != 0),
                balance_after DECIMAL NOT NULL CHECK (balance_after >= 0),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tx_ref TEXT UNIQUE,
                status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
                payment_method TEXT,
                phone_number TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # Create games table with better constraints
        c.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_amount DECIMAL NOT NULL CHECK (bet_amount > 0),
                status TEXT DEFAULT 'waiting' CHECK (status IN ('waiting', 'ready', 'playing', 'completed', 'expired')),
                winner_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (winner_id) REFERENCES users (user_id) ON DELETE SET NULL
            )
        ''')
        
        # Create game_participants table with better constraints
        c.execute('''
            CREATE TABLE IF NOT EXISTS game_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                choice TEXT CHECK (choice IN ('rock', 'paper', 'scissors', NULL)),
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                UNIQUE(game_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}\n{traceback.format_exc()}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def user_exists(user_id):
    """Check if a user exists in the database."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not check user existence - connection failed")
            return None
            
        c = conn.cursor()
        c.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        exists = c.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking user existence: {e}\n{traceback.format_exc()}")
        return None

def get_user_balance(user_id):
    """Get user's current balance from the database."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not get user balance - connection failed")
            return None
            
        c = conn.cursor()
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        return None
    except Exception as e:
        logger.error(f"Error getting user balance: {e}\n{traceback.format_exc()}")
        return None

def update_user_balance(user_id, amount, is_deposit=True):
    """Update user's balance in the database."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not update balance - connection failed")
            return False
            
        c = conn.cursor()
        if is_deposit:
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        else:
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating user balance: {e}\n{traceback.format_exc()}")
        return False

def add_transaction(user_id, type, amount, balance_after):
    """Add a transaction record to the database."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not add transaction - connection failed")
            return False
            
        c = conn.cursor()
        c.execute('''
            INSERT INTO transactions (user_id, type, amount, balance_after)
            VALUES (?, ?, ?, ?)
        ''', (user_id, type, amount, balance_after))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding transaction: {e}\n{traceback.format_exc()}")
        return False

def get_user_transactions(user_id, limit=10):
    """Get user's recent transactions."""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not get transactions - connection failed")
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT type, amount, balance_after, created_at
            FROM transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        transactions = c.fetchall()
        conn.close()
        return transactions
    except Exception as e:
        logger.error(f"Error getting transactions: {e}\n{traceback.format_exc()}")
        return None

async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the create_account command."""
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username or user.first_name
        
        logger.info(f"Attempting to create account for user {user_id} ({username})")

        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if exists:
            await update.message.reply_text("❌ You already have an account!")
            return

        # Create new user account
        conn = get_db_connection()
        if conn is None:
            await update.message.reply_text("❌ Could not connect to the database. Please try again later.")
            return
            
        try:
            c = conn.cursor()
            c.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)',
                     (user_id, username, 100.0))  # Give 100 initial balance
            conn.commit()
            logger.info(f"Successfully created account for user {user_id}")
            
            await update.message.reply_text(
                f"✅ Account created successfully!\n"
                f"Welcome {username}! You've received 100.0 ETB as a welcome bonus.\n"
                f"Use /balance to check your balance and /help to see available commands."
            )
        except sqlite3.IntegrityError:
            logger.warning(f"Attempted to create duplicate account for user {user_id}")
            await update.message.reply_text("❌ You already have an account!")
        except Exception as e:
            logger.error(f"Database error while creating account: {e}\n{traceback.format_exc()}")
            await update.message.reply_text("❌ Failed to create account. Please try again later.")
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Account creation error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the delete_account command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"Attempting to delete account for user {user_id}")
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text("❌ You don't have an account to delete!")
            return

        # Delete user account
        conn = get_db_connection()
        if conn is None:
            await update.message.reply_text("❌ Could not connect to the database. Please try again later.")
            return
            
        try:
            c = conn.cursor()
            c.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            logger.info(f"Successfully deleted account for user {user_id}")
            
            await update.message.reply_text(
                "✅ Your account has been deleted successfully.\n"
                "You can create a new account anytime using /create_account."
            )
        except Exception as e:
            logger.error(f"Database error while deleting account: {e}\n{traceback.format_exc()}")
            await update.message.reply_text("❌ Failed to delete account. Please try again later.")
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Account deletion error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        logger.info(f"Start command received from user {user.id}")
        
        # Create keyboard layout
        keyboard = [
            ['🎮 Play', '💰 Balance'],
            ['📊 Stats', '❓ Help'],
            ['📋 History', '🎲 Game Status'],
            ['🏆 Leaderboard', '👤 Profile'],
            ['ℹ️ About']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        welcome_message = (
            f"👋 Hello {user.first_name}!\n\n"
            "Welcome to RPS Bot. Here's what you can do:\n"
            "• /start - Show this message\n"
            "• /about - Learn about the bot\n"
            "• /create_account - Create your game account\n"
            "• /delete_account - Delete your account\n"
            "• /deposit <amount> - Add funds to your account\n"
            "• /withdraw <amount> - Withdraw funds from your account\n"
            "• /history - View your transaction history\n"
            "• /join_game <amount> - Join or create a game\n"
            "• /game_status - Check your current game\n"
            "• /leaderboard - View top players\n"
            "• /profile - View your profile\n"
            "• /help - Show help information\n"
            "• /balance - Check your balance\n"
            "• /stats - View your statistics"
        )
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        help_text = (
            "🎮 *Available Commands:*\n\n"
            "*Account Management:*\n"
            "/start - Start the bot\n"
            "/about - Learn about the bot\n"
            "/create_account - Create your game account\n"
            "/delete_account - Delete your account\n"
            "/profile - View your profile\n\n"
            "*Payment Commands:*\n"
            f"/deposit <amount> - Add funds (min: {MIN_DEPOSIT} ETB)\n"
            f"/withdraw <amount> <phone> - Withdraw to mobile money (max: {MAX_WITHDRAWAL} ETB)\n"
            "/balance - Check your balance\n"
            "/history - View your transaction history\n\n"
            "*Game Commands:*\n"
            "/join_game <amount> - Join or create a game\n"
            "/game_status - Check your current game\n"
            "/rock - Play rock ✊\n"
            "/paper - Play paper ✋\n"
            "/scissors - Play scissors ✌️\n\n"
            "*Other Commands:*\n"
            "/leaderboard - View top players\n"
            "/stats - View your statistics\n"
            "/help - Show this help message\n\n"
            "*Payment Info:*\n"
            "• Deposits via Chapa (cards, mobile money)\n"
            "• Withdrawals to mobile money\n"
            "• Processing time: 24-48 hours\n"
            "• Need help? Contact @admin"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Help error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the balance command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"Balance check requested by user {user_id}")
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Get user balance
        balance = get_user_balance(user_id)
        if balance is None:
            await update.message.reply_text("❌ Failed to retrieve your balance. Please try again later.")
            return
            
        # Create keyboard with deposit and withdraw options
        keyboard = [
            ['💰 Deposit', '💸 Withdraw'],
            ['🎮 Play', '📊 Stats']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"💰 *Your Current Balance*\n"
            f"ETB {balance:.2f}\n\n"
            f"Use the buttons below to manage your balance:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Balance {balance:.2f} displayed for user {user_id}")

    except Exception as e:
        logger.error(f"Balance check error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the deposit command with Chapa integration."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Validate amount
        if not context.args:
            await update.message.reply_text(
                "Please specify the amount to deposit.\n"
                f"Example: `/deposit {MIN_DEPOSIT}`\n"
                f"Minimum deposit: ETB {MIN_DEPOSIT}",
                parse_mode='Markdown'
            )
            return

        try:
            amount = float(context.args[0])
            if amount < MIN_DEPOSIT:
                await update.message.reply_text(f"❌ Minimum deposit amount is ETB {MIN_DEPOSIT}.")
                return
            if amount != round(amount, 2):
                await update.message.reply_text("❌ Amount cannot have more than 2 decimal places.")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return

        # Generate unique transaction reference
        tx_ref = f"deposit_{user_id}_{int(time.time())}"
        
        # Create Chapa payment request
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "email": f"{user_id}@rpsbot.com",  # Placeholder email
            "first_name": user.first_name,
            "last_name": user.last_name or "User",
            "tx_ref": tx_ref,
            "callback_url": CHAPA_WEBHOOK_URL,
            "return_url": f"https://t.me/{context.bot.username}",
            "customization[title]": "RPS Bot Deposit",
            "customization[description]": f"Deposit {amount} ETB to your RPS Bot account"
        }

        try:
            response = requests.post(
                f"{CHAPA_API_URL}/transaction/initialize",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                payment_data = response.json()
                payment_url = payment_data["data"]["checkout_url"]
                
                # Record pending transaction
                conn = get_db_connection()
                if conn:
                    try:
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO transactions 
                            (user_id, type, amount, balance_after, tx_ref, status)
                            SELECT ?, 'deposit', ?, balance + ?, ?, 'pending'
                            FROM users WHERE user_id = ?
                        ''', (user_id, amount, amount, tx_ref, user_id))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Transaction recording error: {e}")
                    finally:
                        conn.close()
                
                # Create inline keyboard with payment buttons
                keyboard = [
                    [InlineKeyboardButton("💳 Pay Now", url=payment_url)],
                    [InlineKeyboardButton("✅ I've Paid", callback_data=f"verify_{tx_ref}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"💰 *Deposit ETB {amount:.2f}*\n\n"
                    "1️⃣ Click 'Pay Now' to proceed to Chapa\n"
                    "2️⃣ Complete the payment\n"
                    "3️⃣ Click 'I've Paid' to verify\n\n"
                    "⚠️ Payment link expires in 10 minutes\n"
                    "❓ Need help? Contact @admin",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "❌ Payment gateway error. Please try again later or contact support."
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa API error: {e}")
            await update.message.reply_text(
                "❌ Could not connect to payment gateway. Please try again later."
            )

    except Exception as e:
        logger.error(f"Deposit error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def verify_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit verification callback."""
    try:
        query = update.callback_query
        await query.answer()
        
        if not query.data.startswith("verify_"):
            return
            
        tx_ref = query.data.replace("verify_", "")
        user_id = update.effective_user.id
        
        # Check transaction status in our database
        conn = get_db_connection()
        if conn:
            try:
                c = conn.cursor()
                c.execute('''
                    SELECT status, amount 
                    FROM transactions 
                    WHERE tx_ref = ? AND user_id = ?
                ''', (tx_ref, user_id))
                result = c.fetchone()
                
                if not result:
                    await query.edit_message_text("❌ Transaction not found.")
                    return
                    
                status, amount = result
                if status == 'completed':
                    await query.edit_message_text(
                        "✅ Payment already confirmed!\n"
                        f"Amount: ETB {amount:.2f}"
                    )
                    return
                
                # Verify with Chapa
                payment_data = verify_chapa_payment(tx_ref)
                if payment_data and payment_data["status"] == "success":
                    # Update transaction and user balance
                    c.execute('BEGIN TRANSACTION')
                    
                    c.execute('''
                        UPDATE transactions 
                        SET status = 'completed' 
                        WHERE tx_ref = ? AND user_id = ?
                    ''', (tx_ref, user_id))
                    
                    c.execute('''
                        UPDATE users 
                        SET balance = balance + ? 
                        WHERE user_id = ?
                    ''', (amount, user_id))
                    
                    conn.commit()
                    
                    await query.edit_message_text(
                        "✅ Payment confirmed!\n"
                        f"Amount: ETB {amount:.2f}\n"
                        "Use /balance to check your new balance."
                    )
                else:
                    await query.edit_message_text(
                        "⏳ Payment not confirmed yet.\n"
                        "Please wait a few minutes and try again.\n"
                        "If you need help, contact @admin"
                    )
            except Exception as e:
                conn.rollback()
                logger.error(f"Verification error: {e}")
                await query.edit_message_text("❌ Verification failed. Please try again.")
            finally:
                conn.close()
        else:
            await query.edit_message_text("❌ System error. Please try again later.")
            
    except Exception as e:
        logger.error(f"Verify deposit error: {e}")
        try:
            await query.edit_message_text("❌ An error occurred. Please try again.")
        except:
            pass

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the withdraw command with Chapa integration."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Check command format
        if len(context.args) < 2:
            await update.message.reply_text(
                "Please provide amount and phone number.\n"
                "Example: `/withdraw 100 251912345678`\n"
                f"Maximum withdrawal: ETB {MAX_WITHDRAWAL}",
                parse_mode='Markdown'
            )
            return

        try:
            amount = float(context.args[0])
            phone = context.args[1]
            
            # Validate amount
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0.")
                return
            if amount > MAX_WITHDRAWAL:
                await update.message.reply_text(f"❌ Maximum withdrawal amount is ETB {MAX_WITHDRAWAL}.")
                return
            if amount != round(amount, 2):
                await update.message.reply_text("❌ Amount cannot have more than 2 decimal places.")
                return
                
            # Validate phone number
            if not phone.startswith("251") or not phone[3:].isdigit() or len(phone) != 12:
                await update.message.reply_text(
                    "❌ Invalid phone number format!\n"
                    "Use format: 251912345678"
                )
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return

        conn = get_db_connection()
        if conn is None:
            await update.message.reply_text("❌ Database connection error. Please try again later.")
            return

        try:
            c = conn.cursor()
            
            # Check current balance
            c.execute('SELECT balance, username FROM users WHERE user_id = ?', (user_id,))
            result = c.fetchone()
            if not result:
                await update.message.reply_text("❌ Account not found.")
                return
                
            current_balance, username = result
            if amount > current_balance:
                await update.message.reply_text(
                    f"❌ Insufficient balance!\n"
                    f"Your current balance is ETB {current_balance:.2f}"
                )
                return
            
            # Generate transaction reference
            tx_ref = f"withdraw_{user_id}_{int(time.time())}"
            
            # Create Chapa transfer request
            headers = {
                "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "account_name": username,
                "account_number": phone,
                "amount": str(amount),
                "currency": "ETB",
                "reference": tx_ref,
                "description": f"Withdrawal from RPS Bot"
            }
            
            try:
                response = requests.post(
                    f"{CHAPA_API_URL}/transfers",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    # Start transaction
                    c.execute('BEGIN TRANSACTION')
                    
                    # Deduct balance
                    c.execute('''
                        UPDATE users 
                        SET balance = balance - ? 
                        WHERE user_id = ? AND balance >= ?
                    ''', (amount, user_id, amount))
                    
                    if c.rowcount == 0:
                        conn.rollback()
                        await update.message.reply_text("❌ Failed to process withdrawal. Insufficient balance.")
                        return
                    
                    # Record transaction
                    c.execute('''
                        INSERT INTO transactions 
                        (user_id, type, amount, balance_after, tx_ref, status, phone_number)
                        SELECT ?, 'withdraw', -?, balance, ?, 'pending', ?
                        FROM users WHERE user_id = ?
                    ''', (user_id, amount, tx_ref, phone, user_id))
                    
                    conn.commit()
                    
                    await update.message.reply_text(
                        f"✅ Withdrawal of ETB {amount:.2f} initiated!\n\n"
                        f"📱 Phone: {phone}\n"
                        "⏳ Processing time: 24-48 hours\n\n"
                        "Use /history to check status."
                    )
                    logger.info(f"User {user_id} initiated withdrawal of {amount:.2f} to {phone}")
                else:
                    error_msg = response.json().get("message", "Unknown error")
                    await update.message.reply_text(
                        f"❌ Withdrawal failed: {error_msg}\n"
                        "Please try again later or contact support."
                    )
            except requests.exceptions.RequestException as e:
                logger.error(f"Chapa API error: {e}")
                await update.message.reply_text(
                    "❌ Could not process withdrawal. Please try again later."
                )
                
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during withdrawal: {e}\n{traceback.format_exc()}")
            await update.message.reply_text("❌ Failed to process withdrawal. Please try again later.")
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Withdrawal error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the history command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Get transactions
        transactions = get_user_transactions(user_id)
        if transactions is None:
            await update.message.reply_text("❌ Failed to retrieve transaction history. Please try again later.")
            return
        
        if not transactions:
            await update.message.reply_text("No transactions found in your history.")
            return
        
        # Format transaction history
        history_text = "📋 *Recent Transactions*\n\n"
        for type, amount, balance_after, created_at in transactions:
            symbol = "+" if type in ["deposit", "win", "bonus"] else "-"
            history_text += (
                f"*{type.title()}*\n"
                f"Amount: {symbol}ETB {abs(amount):.2f}\n"
                f"Balance: ETB {balance_after:.2f}\n"
                f"Date: {created_at}\n"
                f"{'─' * 20}\n"
            )
        
        await update.message.reply_text(history_text, parse_mode='Markdown')
        logger.info(f"Transaction history displayed for user {user_id}")

    except Exception as e:
        logger.error(f"History error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")

def get_waiting_game(bet_amount):
    """Get a waiting game with the specified bet amount."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT g.id, g.bet_amount, COUNT(gp.id) as player_count
            FROM games g
            LEFT JOIN game_participants gp ON g.id = gp.game_id
            WHERE g.status = 'waiting' AND g.bet_amount = ?
            GROUP BY g.id
            HAVING player_count < 3
            ORDER BY g.created_at ASC
            LIMIT 1
        ''', (bet_amount,))
        game = c.fetchone()
        conn.close()
        return game
    except Exception as e:
        logger.error(f"Error getting waiting game: {e}\n{traceback.format_exc()}")
        return None

def create_game(bet_amount):
    """Create a new game."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        c.execute('INSERT INTO games (bet_amount) VALUES (?)', (bet_amount,))
        game_id = c.lastrowid
        conn.commit()
        conn.close()
        return game_id
    except Exception as e:
        logger.error(f"Error creating game: {e}\n{traceback.format_exc()}")
        return None

def add_participant(game_id, user_id):
    """Add a participant to a game."""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, None, None
            
        c = conn.cursor()
        
        try:
            conn.execute('BEGIN TRANSACTION')
            
            # Check if user is already in this game
            c.execute('SELECT 1 FROM game_participants WHERE game_id = ? AND user_id = ?', 
                     (game_id, user_id))
            if c.fetchone():
                conn.rollback()
                return False, "already_joined", None
            
            # Check current player count
            c.execute('''
                SELECT COUNT(*), g.status 
                FROM game_participants gp
                JOIN games g ON g.id = gp.game_id
                WHERE g.id = ?
                GROUP BY g.id, g.status
            ''', (game_id,))
            result = c.fetchone()
            current_players = result[0] if result else 0
            game_status = result[1] if result else 'waiting'
            
            if current_players >= 3 or game_status != 'waiting':
                conn.rollback()
                return False, "game_full", None
            
            # Add participant
            c.execute('INSERT INTO game_participants (game_id, user_id) VALUES (?, ?)',
                     (game_id, user_id))
            
            # Get updated player count
            c.execute('SELECT COUNT(*) FROM game_participants WHERE game_id = ?', (game_id,))
            new_count = c.fetchone()[0]
            
            # If we now have exactly 3 players, start the game
            if new_count == 3:
                c.execute('UPDATE games SET status = ? WHERE id = ?', ('playing', game_id))
                game_status = 'playing'
            
            # Get all participants for this game
            c.execute('''
                SELECT u.user_id, u.username 
                FROM game_participants gp
                JOIN users u ON u.user_id = gp.user_id
                WHERE gp.game_id = ?
                ORDER BY gp.joined_at
            ''', (game_id,))
            participants = c.fetchall()
            
            conn.commit()
            return True, new_count, participants
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error adding participant: {e}\n{traceback.format_exc()}")
        return False, None, None

def get_game_participants(game_id):
    """Get participants of a game."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT u.user_id, u.username
            FROM game_participants gp
            JOIN users u ON gp.user_id = u.user_id
            WHERE gp.game_id = ?
        ''', (game_id,))
        participants = c.fetchall()
        conn.close()
        return participants
    except Exception as e:
        logger.error(f"Error getting game participants: {e}\n{traceback.format_exc()}")
        return None

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the join_game command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Check if bet amount is provided
        if not context.args:
            await update.message.reply_text(
                "Please specify the bet amount.\n"
                "Example: `/join_game 100`",
                parse_mode='Markdown'
            )
            return

        try:
            bet_amount = float(context.args[0])
            if bet_amount <= 0:
                await update.message.reply_text("❌ Bet amount must be greater than 0.")
                return
            if bet_amount > 1000:
                await update.message.reply_text("❌ Maximum bet amount is ETB 1,000.")
                return
            if bet_amount != round(bet_amount, 2):
                await update.message.reply_text("❌ Bet amount cannot have more than 2 decimal places.")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return

        # Check user balance
        balance = get_user_balance(user_id)
        if balance is None:
            await update.message.reply_text("❌ Failed to check your balance. Please try again later.")
            return
        
        if bet_amount > balance:
            await update.message.reply_text(
                f"❌ Insufficient balance!\n"
                f"Your current balance is ETB {balance:.2f}"
            )
            return

        # Look for a waiting game or create new one
        game = get_waiting_game(bet_amount)
        if game:
            game_id, bet_amount, current_players = game
            # Join existing game
            success, result, participants = add_participant(game_id, user_id)
            if success:
                # Deduct bet amount
                if update_user_balance(user_id, bet_amount, is_deposit=False):
                    new_balance = get_user_balance(user_id)
                    if new_balance is not None:
                        add_transaction(user_id, "bet", -bet_amount, new_balance)
                    
                    if participants:
                        players = ", ".join([p[1] for p in participants])
                        players_count = result  # This is the new count after adding the player
                        
                        if players_count < 3:
                            remaining = 3 - players_count
                            await update.message.reply_text(
                                f"✅ You've joined the game!\n"
                                f"💰 Bet amount: ETB {bet_amount:.2f}\n"
                                f"👥 Players ({players_count}/3): {players}\n"
                                f"Waiting for {remaining} more player{'s' if remaining > 1 else ''}..."
                            )
                            
                            # Notify other players
                            for p_id, _ in participants:
                                if p_id != user_id:
                                    try:
                                        await context.bot.send_message(
                                            chat_id=p_id,
                                            text=f"🎮 {update.effective_user.username or update.effective_user.first_name} has joined your game!\n"
                                                 f"Players ({players_count}/3): {players}\n"
                                                 f"Waiting for {remaining} more player{'s' if remaining > 1 else ''}..."
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to notify player {p_id}: {e}")
                        else:
                            # Game is starting - notify all players
                            game_start_message = (
                                f"🎮 Game is starting!\n"
                                f"💰 Bet amount: ETB {bet_amount:.2f}\n"
                                f"👥 Players (3/3): {players}\n\n"
                                f"Make your choice:\n"
                                f"• /rock - Play rock ✊\n"
                                f"• /paper - Play paper ✋\n"
                                f"• /scissors - Play scissors ✌️"
                            )
                            
                            await update.message.reply_text(game_start_message)
                            
                            # Notify other players
                            for p_id, _ in participants:
                                if p_id != user_id:
                                    try:
                                        await context.bot.send_message(
                                            chat_id=p_id,
                                            text=game_start_message
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to notify player {p_id}: {e}")
                    else:
                        await update.message.reply_text("✅ You've joined the game!")
                else:
                    await update.message.reply_text("❌ Failed to process bet. Please try again later.")
            elif result == "already_joined":
                await update.message.reply_text("❌ You're already in this game!")
            elif result == "game_full":
                await update.message.reply_text("❌ This game is already full. Try joining another game or create a new one.")
            else:
                await update.message.reply_text("❌ Failed to join game. Please try again.")
        else:
            # Create new game
            game_id = create_game(bet_amount)
            if game_id:
                success, result, participants = add_participant(game_id, user_id)
                if success:
                    # Deduct bet amount
                    if update_user_balance(user_id, bet_amount, is_deposit=False):
                        new_balance = get_user_balance(user_id)
                        if new_balance is not None:
                            add_transaction(user_id, "bet", -bet_amount, new_balance)
                        
                        await update.message.reply_text(
                            f"✅ New game created!\n"
                            f"💰 Bet amount: ETB {bet_amount:.2f}\n"
                            f"👥 Players (1/3): {update.effective_user.username or update.effective_user.first_name}\n"
                            f"Waiting for 2 more players...\n\n"
                            f"Share this message to invite others!"
                        )
                    else:
                        await update.message.reply_text("❌ Failed to process bet. Please try again later.")
                else:
                    await update.message.reply_text("❌ Failed to create game. Please try again.")
            else:
                await update.message.reply_text("❌ Failed to create game. Please try again.")

    except Exception as e:
        logger.error(f"Join game error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

def get_user_active_game(user_id):
    """Get user's active game if any."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT g.id, g.bet_amount, g.status, g.created_at,
                   COUNT(gp.id) as player_count
            FROM games g
            JOIN game_participants gp ON g.id = gp.game_id
            WHERE g.id IN (
                SELECT game_id 
                FROM game_participants 
                WHERE user_id = ?
            )
            AND g.status IN ('waiting', 'ready')
            GROUP BY g.id
        ''', (user_id,))
        game = c.fetchone()
        conn.close()
        return game
    except Exception as e:
        logger.error(f"Error getting user active game: {e}\n{traceback.format_exc()}")
        return None

async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the game_status command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Get user's active game
        game = get_user_active_game(user_id)
        if game is None:
            await update.message.reply_text("❌ Failed to check game status. Please try again later.")
            return
        
        if not game:
            await update.message.reply_text(
                "You're not in any active game.\n"
                "Use /join_game <amount> to join or create a game!"
            )
            return
        
        game_id, bet_amount, status, created_at, player_count = game
        
        # Get participants
        participants = get_game_participants(game_id)
        if participants is None:
            await update.message.reply_text("❌ Failed to get game participants. Please try again later.")
            return
        
        # Format status message
        status_text = (
            "🎮 *Current Game Status*\n\n"
            f"Game ID: `{game_id}`\n"
            f"Status: {status.title()}\n"
            f"Bet Amount: ETB {bet_amount:.2f}\n"
            f"Players: {player_count}/2\n"
            f"Created: {created_at}\n\n"
            "👥 *Participants:*\n"
        )
        
        for user_id, username in participants:
            status_text += f"• {username}\n"
            
        if status == 'waiting':
            status_text += "\nWaiting for more players to join..."
        elif status == 'ready':
            status_text += "\nGame is ready! Make your choice:\n/rock, /paper, or /scissors"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        logger.info(f"Game status displayed for user {user_id}, game {game_id}")

    except Exception as e:
        logger.error(f"Game status error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

def get_leaderboard(order_by='earnings', limit=10):
    """Get the leaderboard data."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        
        if order_by == 'wins':
            order_clause = 'games_won DESC, total_earnings DESC'
        else:  # earnings
            order_clause = 'total_earnings DESC, games_won DESC'
            
        c.execute(f'''
            SELECT username, games_won, total_games,
                   CASE 
                       WHEN total_games > 0 
                       THEN ROUND(CAST(games_won AS FLOAT) / total_games * 100, 1)
                       ELSE 0 
                   END as win_rate,
                   total_earnings
            FROM users
            WHERE total_games > 0
            ORDER BY {order_clause}
            LIMIT ?
        ''', (limit,))
        
        results = c.fetchall()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}\n{traceback.format_exc()}")
        return None

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the leaderboard command."""
    try:
        # Default to earnings, but allow sorting by wins
        sort_by = 'earnings'
        if context.args and context.args[0].lower() in ['wins', 'earnings']:
            sort_by = context.args[0].lower()

        # Get leaderboard data
        leaders = get_leaderboard(order_by=sort_by)
        if leaders is None:
            await update.message.reply_text("❌ Failed to retrieve leaderboard. Please try again later.")
            return
        
        if not leaders:
            await update.message.reply_text(
                "No players have completed any games yet!\n"
                "Use /join_game <amount> to start playing."
            )
            return
        
        # Create keyboard for sorting options
        keyboard = [
            ['💰 Sort by Earnings', '🏆 Sort by Wins'],
            ['🎮 Play', '❓ Help']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Format leaderboard message
        title = "💰 *Top Players by Earnings*" if sort_by == 'earnings' else "🏆 *Top Players by Wins*"
        leaderboard_text = f"{title}\n\n"
        
        for i, (username, wins, total, win_rate, earnings) in enumerate(leaders, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            leaderboard_text += (
                f"{medal} *{i}. {username}*\n"
                f"   Wins: {wins}/{total} ({win_rate}%)\n"
                f"   Earnings: ETB {earnings:.2f}\n"
                f"{'─' * 20}\n"
            )
            
        leaderboard_text += (
            "\nUse `/leaderboard wins` to sort by wins\n"
            "Use `/leaderboard earnings` to sort by earnings"
        )
        
        await update.message.reply_text(
            leaderboard_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Leaderboard displayed, sorted by {sort_by}")

    except Exception as e:
        logger.error(f"Leaderboard error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

def get_user_stats(user_id):
    """Get user's statistics."""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT username, balance, total_games, games_won,
                   CASE 
                       WHEN total_games > 0 
                       THEN ROUND(CAST(games_won AS FLOAT) / total_games * 100, 1)
                       ELSE 0 
                   END as win_rate,
                   total_earnings,
                   created_at
            FROM users
            WHERE user_id = ?
        ''', (user_id,))
        
        stats = c.fetchone()
        
        # Get recent transactions
        c.execute('''
            SELECT type, amount, created_at
            FROM transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        ''', (user_id,))
        recent_transactions = c.fetchall()
        
        # Get recent games
        c.execute('''
            SELECT g.bet_amount, g.status,
                   CASE WHEN g.winner_id = ? THEN 'Won' ELSE 'Lost' END as result,
                   g.created_at
            FROM games g
            JOIN game_participants gp ON g.id = gp.game_id
            WHERE gp.user_id = ? AND g.status = 'completed'
            ORDER BY g.created_at DESC
            LIMIT 5
        ''', (user_id, user_id))
        recent_games = c.fetchall()
        
        conn.close()
        return stats, recent_transactions, recent_games
    except Exception as e:
        logger.error(f"Error getting user stats: {e}\n{traceback.format_exc()}")
        return None

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the profile command."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return

        # Get user stats and history
        result = get_user_stats(user_id)
        if result is None:
            await update.message.reply_text("❌ Failed to retrieve your profile. Please try again later.")
            return
            
        stats, transactions, games = result
        username, balance, total_games, wins, win_rate, earnings, joined_date = stats
        
        # Format profile message
        profile_text = (
            f"👤 *{username}'s Profile*\n\n"
            f"💰 *Balance:* ETB {balance:.2f}\n"
            f"🎮 *Games Played:* {total_games}\n"
            f"🏆 *Games Won:* {wins}\n"
            f"📊 *Win Rate:* {win_rate}%\n"
            f"💵 *Total Earnings:* ETB {earnings:.2f}\n"
            f"📅 *Joined:* {joined_date}\n"
        )
        
        if games:
            profile_text += "\n🎲 *Recent Games:*\n"
            for bet, status, result, date in games:
                emoji = "✅" if result == "Won" else "❌"
                profile_text += f"{emoji} {result} ETB {bet:.2f} ({date})\n"
        
        if transactions:
            profile_text += "\n💳 *Recent Transactions:*\n"
            for type, amount, date in transactions:
                symbol = "+" if type in ["deposit", "win", "bonus"] else "-"
                profile_text += f"{symbol}ETB {abs(amount):.2f} - {type.title()} ({date})\n"
        
        # Create keyboard
        keyboard = [
            ['🎮 Play', '💰 Balance'],
            ['📊 Stats', '📋 History'],
            ['🏆 Leaderboard', '❓ Help']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Profile displayed for user {user_id}")

    except Exception as e:
        logger.error(f"Profile error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the about command."""
    try:
        about_text = (
            "🎮 *Rock Paper Scissors Bot*\n\n"
            "Welcome to our exciting Rock Paper Scissors game bot! Challenge other players "
            "and win ETB by playing the classic game.\n\n"
            "*Features:*\n"
            "• 👥 Player vs Player matches\n"
            "• 💰 Real-time balance tracking\n"
            "• 🎲 Betting system\n"
            "• 📊 Player statistics\n"
            "• 🏆 Global leaderboard\n"
            "• 📋 Transaction history\n\n"
            "*How to Play:*\n"
            "1. Create an account with /create_account\n"
            "2. Deposit funds using /deposit\n"
            "3. Join a game with /join_game\n"
            "4. Make your choice when the game starts!\n\n"
            "*Need help?*\n"
            "Use /help to see all available commands\n\n"
            "Good luck and have fun! 🎉"
        )
        
        # Create keyboard
        keyboard = [
            ['🎮 Play', '❓ Help'],
            ['💰 Balance', '👤 Profile']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            about_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"About info displayed for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"About command error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

def record_choice(game_id, user_id, choice):
    """Record a player's choice in the game."""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, None
            
        c = conn.cursor()
        
        try:
            conn.execute('BEGIN TRANSACTION')
            
            # Verify game is in playing state and not expired
            c.execute('''
                SELECT status, created_at 
                FROM games 
                WHERE id = ? AND status = 'playing'
                AND datetime(created_at, '+5 minutes') > datetime('now')
            ''', (game_id,))
            game = c.fetchone()
            
            if not game:
                # Check if game expired
                c.execute('''
                    SELECT status, created_at 
                    FROM games 
                    WHERE id = ? AND status = 'playing'
                ''', (game_id,))
                expired_game = c.fetchone()
                
                if expired_game:
                    # Game expired - refund players and mark as expired
                    c.execute('''
                        UPDATE games 
                        SET status = 'expired' 
                        WHERE id = ?
                    ''', (game_id,))
                    
                    # Refund players who made choices
                    c.execute('''
                        SELECT gp.user_id, g.bet_amount
                        FROM game_participants gp
                        JOIN games g ON g.id = gp.game_id
                        WHERE g.id = ?
                    ''', (game_id,))
                    
                    for player_id, bet_amount in c.fetchall():
                        c.execute('''
                            UPDATE users 
                            SET balance = balance + ?,
                                total_games = total_games + 1
                            WHERE user_id = ?
                        ''', (bet_amount, player_id))
                        
                        c.execute('''
                            INSERT INTO transactions (user_id, type, amount, balance_after)
                            SELECT ?, 'refund', ?, balance
                            FROM users WHERE user_id = ?
                        ''', (player_id, bet_amount, player_id))
                    
                    conn.commit()
                    return False, "game_expired"
                
                return False, "invalid_game"
            
            # Check if player is in this game
            c.execute('SELECT 1 FROM game_participants WHERE game_id = ? AND user_id = ?', 
                     (game_id, user_id))
            if not c.fetchone():
                conn.rollback()
                return False, "not_in_game"
            
            # Check if player already made a choice
            c.execute('SELECT choice FROM game_participants WHERE game_id = ? AND user_id = ?', 
                     (game_id, user_id))
            if c.fetchone()[0]:
                conn.rollback()
                return False, "already_chosen"
            
            # Record player's choice
            c.execute('UPDATE game_participants SET choice = ? WHERE game_id = ? AND user_id = ?',
                     (choice, game_id, user_id))
            
            # Check if all players have made their choices
            c.execute('''
                SELECT 
                    gp.user_id,
                    u.username,
                    gp.choice,
                    u.games_won,
                    u.total_games
                FROM game_participants gp
                JOIN users u ON u.user_id = gp.user_id
                WHERE gp.game_id = ?
                ORDER BY gp.joined_at
            ''', (game_id,))
            players = c.fetchall()
            
            all_chosen = all(p[2] for p in players)
            
            if all_chosen:
                # Determine winner
                choices = {p[0]: p[2] for p in players}
                usernames = {p[0]: p[1] for p in players}
                stats = {p[0]: (p[3], p[4]) for p in players}  # (wins, total_games)
                
                # Convert choices to a list to maintain order
                player_ids = list(choices.keys())
                player_choices = [choices[pid] for pid in player_ids]
                
                # Get bet amount and calculate prizes
                c.execute('SELECT bet_amount FROM games WHERE id = ?', (game_id,))
                bet_amount = c.fetchone()[0]
                
                # If all choices are the same, it's a draw
                if len(set(player_choices)) == 1:
                    winner_id = None
                    # Return bets in case of a draw
                    for player_id in player_ids:
                        c.execute('''
                            UPDATE users 
                            SET balance = balance + ?,
                                total_games = total_games + 1
                            WHERE user_id = ?
                        ''', (bet_amount, player_id))
                        
                        c.execute('''
                            INSERT INTO transactions (user_id, type, amount, balance_after)
                            SELECT ?, 'refund', ?, balance
                            FROM users WHERE user_id = ?
                        ''', (player_id, bet_amount, player_id))
                else:
                    # Calculate wins for each player
                    win_counts = {pid: 0 for pid in player_ids}
                    for i, player1_id in enumerate(player_ids):
                        for j, player2_id in enumerate(player_ids):
                            if i != j:
                                choice1 = choices[player1_id]
                                choice2 = choices[player2_id]
                                
                                if (
                                    (choice1 == 'rock' and choice2 == 'scissors') or
                                    (choice1 == 'paper' and choice2 == 'rock') or
                                    (choice1 == 'scissors' and choice2 == 'paper')
                                ):
                                    win_counts[player1_id] += 1
                    
                    # Find player(s) with most wins
                    max_wins = max(win_counts.values())
                    winners = [pid for pid, wins in win_counts.items() if wins == max_wins]
                    
                    if len(winners) == 1:
                        # Clear winner
                        winner_id = winners[0]
                        prize = bet_amount * 3
                        
                        # Update winner's stats and balance
                        wins, total = stats[winner_id]
                        win_rate = (wins + 1) / (total + 1) * 100
                        
                        c.execute('''
                            UPDATE users 
                            SET balance = balance + ?,
                                games_won = games_won + 1,
                                total_games = total_games + 1,
                                total_earnings = total_earnings + ?
                            WHERE user_id = ?
                        ''', (prize, prize - bet_amount, winner_id))
                        
                        # Update other players' stats
                        c.execute('''
                            UPDATE users 
                            SET total_games = total_games + 1
                            WHERE user_id IN (
                                SELECT user_id FROM game_participants 
                                WHERE game_id = ? AND user_id != ?
                            )
                        ''', (game_id, winner_id))
                        
                        # Record win transaction
                        c.execute('''
                            INSERT INTO transactions (user_id, type, amount, balance_after)
                            SELECT ?, 'win', ?, balance
                            FROM users WHERE user_id = ?
                        ''', (winner_id, prize, winner_id))
                    else:
                        # Multiple winners - split the pot
                        winner_id = None
                        split_prize = (bet_amount * 3) / len(winners)
                        
                        for pid in winners:
                            c.execute('''
                                UPDATE users 
                                SET balance = balance + ?,
                                    games_won = games_won + 1,
                                    total_games = total_games + 1,
                                    total_earnings = total_earnings + ?
                                WHERE user_id = ?
                            ''', (split_prize, split_prize - bet_amount, pid))
                            
                            c.execute('''
                                INSERT INTO transactions (user_id, type, amount, balance_after)
                                SELECT ?, 'win', ?, balance
                                FROM users WHERE user_id = ?
                            ''', (pid, split_prize, pid))
                        
                        # Update non-winners' stats
                        non_winners = set(player_ids) - set(winners)
                        for pid in non_winners:
                            c.execute('''
                                UPDATE users 
                                SET total_games = total_games + 1
                                WHERE user_id = ?
                            ''', (pid,))
                
                # Update game status
                c.execute('UPDATE games SET status = ?, winner_id = ? WHERE id = ?',
                         ('completed', winner_id, game_id))
            
            conn.commit()
            return True, (all_chosen, players, winner_id if all_chosen else None, bet_amount if all_chosen else None)
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error recording choice: {e}\n{traceback.format_exc()}")
        return False, "error"

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    """Handle a player's rock/paper/scissors choice."""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if user exists
        exists = user_exists(user_id)
        if exists is None:
            await update.message.reply_text("❌ System error. Please try again later.")
            return
        if not exists:
            await update.message.reply_text(
                "❌ You don't have an account!\n"
                "Use /create_account to create one."
            )
            return
        
        # Find user's active game
        conn = get_db_connection()
        if conn is None:
            await update.message.reply_text("❌ Database error. Please try again later.")
            return
            
        try:
            c = conn.cursor()
            c.execute('''
                SELECT g.id, g.bet_amount, g.status,
                       datetime(g.created_at, '+5 minutes') as expires_at,
                       datetime('now') as current_time
                FROM games g
                JOIN game_participants gp ON g.id = gp.game_id
                WHERE gp.user_id = ? AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            ''', (user_id,))
            game = c.fetchone()
            
            if not game:
                await update.message.reply_text("❌ You're not in an active game!")
                return
            
            game_id = game[0]
            expires_at = game[3]
            current_time = game[4]
            
            if expires_at < current_time:
                await update.message.reply_text(
                    "❌ Game has expired! (Time limit: 5 minutes)\n"
                    "Your bet has been refunded."
                )
                return
            
            # Record the choice
            success, result = record_choice(game_id, user_id, choice)
            
            if not success:
                if result == "invalid_game":
                    await update.message.reply_text("❌ This game is no longer active.")
                elif result == "not_in_game":
                    await update.message.reply_text("❌ You're not part of this game.")
                elif result == "already_chosen":
                    await update.message.reply_text("❌ You've already made your choice!")
                elif result == "game_expired":
                    await update.message.reply_text(
                        "❌ Game has expired! (Time limit: 5 minutes)\n"
                        "All bets have been refunded."
                    )
                else:
                    await update.message.reply_text("❌ Failed to record your choice. Please try again.")
                return
            
            all_chosen, players, winner_id, bet_amount = result
            
            # Send confirmation to the player
            choice_emojis = {'rock': '✊', 'paper': '✋', 'scissors': '✌️'}
            await update.message.reply_text(
                f"✅ You chose {choice} {choice_emojis[choice]}!\n"
                "Waiting for other players..."
            )
            
            if all_chosen:
                # Get all players' choices
                choices = []
                usernames = []
                for player in players:
                    pid, username, pchoice, wins, total = player
                    choices.append(pchoice)
                    usernames.append(username)
                
                try:
                    # Create battle animation
                    animation_data = create_battle_animation(choices)
                    result_image = create_battle_result_image(
                        choices,
                        winner=choices[0] if winner_id == players[0][0] else
                               choices[1] if winner_id == players[1][0] else
                               choices[2] if winner_id == players[2][0] else None
                    )
                    
                    # Format result message
                    result_message = "🎮 *Game Results!*\n\n"
                    for i, (pid, username, pchoice, wins, total) in enumerate(players):
                        win_rate = (wins / total * 100) if total > 0 else 0
                        result_message += (
                            f"• {username}: {pchoice} {choice_emojis[pchoice]}\n"
                            f"  Stats: {wins}/{total} ({win_rate:.1f}% wins)\n"
                        )
                    
                    if winner_id:
                        winner_name = next(p[1] for p in players if p[0] == winner_id)
                        result_message += (
                            f"\n🏆 Winner: {winner_name}!\n"
                            f"💰 Prize: ETB {bet_amount * 3:.2f}\n"
                            f"Use /join_game to play again!"
                        )
                    else:
                        # Check if it's a draw or split win
                        choices_set = set(p[2] for p in players)
                        if len(choices_set) == 1:
                            result_message += (
                                "\n🤝 It's a draw! All bets have been refunded.\n"
                                "Use /join_game to play again!"
                            )
                        else:
                            split_prize = (bet_amount * 3) / 2  # Split between two winners
                            winners = [p[1] for p in players if p[0] in winner_id]
                            result_message += (
                                f"\n👥 Split win between: {', '.join(winners)}!\n"
                                f"💰 Prize: ETB {split_prize:.2f} each\n"
                                f"Use /join_game to play again!"
                            )
                    
                    # Send results to all players
                    for player in players:
                        try:
                            # Send animation
                            await context.bot.send_animation(
                                chat_id=player[0],
                                animation=animation_data,
                                caption="🎮 Battle Animation"
                            )
                            # Send result image and message
                            await context.bot.send_photo(
                                chat_id=player[0],
                                photo=result_image,
                                caption=result_message,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Failed to send result to player {player[0]}: {e}")
                            
                except Exception as e:
                    logger.error(f"Animation error: {e}")
                    # Fallback to text-only result if animation fails
                    for player in players:
                        try:
                            await context.bot.send_message(
                                chat_id=player[0],
                                text=result_message,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Failed to send result to player {player[0]}: {e}")
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Choice handling error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def rock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the rock command."""
    await handle_choice(update, context, 'rock')

async def paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the paper command."""
    await handle_choice(update, context, 'paper')

async def scissors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the scissors command."""
    await handle_choice(update, context, 'scissors')

def main():
    """Start the bot."""
    # Get token from .env file
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("No token found in .env file!")
        return

    try:
        # Initialize database
        init_db()
        
        # Create application with custom timeouts
        app = Application.builder().token(token).read_timeout(30).write_timeout(30).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("about", about))
        app.add_handler(CommandHandler("create_account", create_account))
        app.add_handler(CommandHandler("delete_account", delete_account))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("deposit", deposit))
        app.add_handler(CommandHandler("withdraw", withdraw))
        app.add_handler(CommandHandler("history", history))
        app.add_handler(CommandHandler("join_game", join_game))
        app.add_handler(CommandHandler("game_status", game_status))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("profile", profile))
        app.add_handler(CommandHandler("rock", rock))
        app.add_handler(CommandHandler("paper", paper))
        app.add_handler(CommandHandler("scissors", scissors))
        
        # Add callback query handlers
        app.add_handler(CallbackQueryHandler(verify_deposit, pattern="^verify_"))
        
        # Add error handler
        app.add_error_handler(error_handler)
        
        logger.info("Starting bot...")
        # Run the bot until the user presses Ctrl-C
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == '__main__':
    main() 