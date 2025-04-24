import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)
from datetime import datetime
from config import (
    BOT_TOKEN,
    GAME_TIMEOUT,
    DEFAULT_BUY_IN,
    PRIZE_DISTRIBUTION,
    GAME_STATES
)
from models import User, Game, GameParticipant, Transaction, DailyStats
from payments import PaymentSystem
from app import db
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
LOGGER = logging.getLogger(__name__)

# Keyboard layouts
MAIN_KEYBOARD = [
    [InlineKeyboardButton("🎮 Play Game", callback_data="play"),
     InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
    [InlineKeyboardButton("📊 Stats", callback_data="stats"),
     InlineKeyboardButton("❓ Help", callback_data="help")]
]

WALLET_KEYBOARD = [
    [InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
     InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
    [InlineKeyboardButton("📜 History", callback_data="history"),
     InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
]

GAME_CHOICES = [
    [InlineKeyboardButton("✊ Rock", callback_data="choice_rock"),
     InlineKeyboardButton("✋ Paper", callback_data="choice_paper"),
     InlineKeyboardButton("✌️ Scissors", callback_data="choice_scissors")]
]

def start(update: Update, context: CallbackContext) -> None:
    """Start command handler"""
    try:
        reply_markup = InlineKeyboardMarkup(MAIN_KEYBOARD)
        update.message.reply_text(
            "Welcome to Rock Paper Scissors Bot! 🎮\n\n"
            "Here you can play Rock Paper Scissors with other players "
            "and win real money! 💰\n\n"
            "To get started:\n"
            "1. Create an account with /account create\n"
            "2. Deposit funds using /wallet\n"
            "3. Join a game with /play\n\n"
            "Use the buttons below to navigate:",
            reply_markup=reply_markup
        )
    except Exception as e:
        LOGGER.error(f"Error in start command: {e}")
        update.message.reply_text("An error occurred. Please try again.")

def account_command(update: Update, context: CallbackContext) -> None:
    """Handle account-related commands"""
    try:
        if not context.args:
            update.message.reply_text(
                "Please specify an account action:\n"
                "/account create - Create a new account\n"
                "/account info - View your account info\n"
                "/account delete - Delete your account"
            )
            return

        action = context.args[0].lower()
        user_id = update.effective_user.id

        if action == "create":
            # Check if user already has an account
            existing_user = User.query.filter_by(telegram_id=user_id).first()
            if existing_user:
                update.message.reply_text("You already have an account!")
                return

            # Create new user
            username = update.effective_user.username or f"player_{user_id}"
            new_user = User(
                telegram_id=user_id,
                username=username,
                balance=0.0,
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow()
            )
            db.session.add(new_user)
            db.session.commit()

            update.message.reply_text(
                f"Account created successfully! 🎉\n"
                f"Username: {username}\n"
                f"Balance: ETB 0.00\n\n"
                f"Use /wallet to add funds and start playing!"
            )

        elif action == "info":
            user = User.query.filter_by(telegram_id=user_id).first()
            if not user:
                update.message.reply_text("You don't have an account! Use /account create first.")
                return

            # Calculate stats
            win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0

            update.message.reply_text(
                f"👤 *Account Information*\n\n"
                f"Username: {user.username}\n"
                f"Balance: ETB {user.balance:.2f}\n"
                f"Games Played: {user.games_played}\n"
                f"Games Won: {user.games_won}\n"
                f"Win Rate: {win_rate:.1f}%\n"
                f"Total Winnings: ETB {user.total_winnings:.2f}\n"
                f"Account Created: {user.created_at.strftime('%Y-%m-%d')}\n",
                parse_mode=ParseMode.MARKDOWN
            )

        elif action == "delete":
            user = User.query.filter_by(telegram_id=user_id).first()
            if not user:
                update.message.reply_text("You don't have an account to delete!")
                return

            keyboard = [
                [InlineKeyboardButton("Yes, delete my account", callback_data="confirm_delete"),
                 InlineKeyboardButton("No, keep my account", callback_data="cancel_delete")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                "⚠️ *WARNING: Account Deletion*\n\n"
                "Are you sure you want to delete your account?\n"
                "This will:\n"
                "• Delete all your account data\n"
                "• Remove you from any active games\n"
                "• Forfeit any remaining balance\n\n"
                "This action cannot be undone!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        LOGGER.error(f"Error in account command: {e}")
        update.message.reply_text("An error occurred. Please try again.")

def wallet_command(update: Update, context: CallbackContext) -> None:
    """Handle wallet commands"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            update.message.reply_text("You need an account first! Use /account create")
            return

        reply_markup = InlineKeyboardMarkup(WALLET_KEYBOARD)
        update.message.reply_text(
            f"💰 *Your Wallet*\n\n"
            f"Current Balance: ETB {user.balance:.2f}\n\n"
            f"What would you like to do?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        LOGGER.error(f"Error in wallet command: {e}")
        update.message.reply_text("An error occurred. Please try again.")

def play_command(update: Update, context: CallbackContext) -> None:
    """Handle game creation/joining"""
    try:
        user = User.query.filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            update.message.reply_text("You need an account first! Use /account create")
            return

        # Check if user is already in a game
        active_game = GameParticipant.query.join(Game).filter(
            GameParticipant.user_id == user.id,
            Game.status.in_([GAME_STATES['WAITING'], GAME_STATES['IN_PROGRESS']])
        ).first()

        if active_game:
            update.message.reply_text(
                f"You're already in Game #{active_game.game_id}!\n"
                f"Use /game_status to check your game."
            )
            return

        # Parse bet amount if provided
        bet_amount = DEFAULT_BUY_IN
        if context.args:
            try:
                bet_amount = float(context.args[0])
                if bet_amount <= 0:
                    update.message.reply_text("Bet amount must be greater than 0!")
                    return
            except ValueError:
                update.message.reply_text("Invalid bet amount! Please provide a valid number.")
                return

        # Check user balance
        if user.balance < bet_amount:
            update.message.reply_text(
                f"Insufficient balance! You need ETB {bet_amount:.2f} to play.\n"
                f"Your balance: ETB {user.balance:.2f}"
            )
            return

        # Look for an existing game or create new one
        game = Game.query.filter_by(
            status=GAME_STATES['WAITING'],
            bet_amount=bet_amount
        ).first()

        if not game:
            game = Game(
                bet_amount=bet_amount,
                status=GAME_STATES['WAITING'],
                created_at=datetime.utcnow()
            )
            db.session.add(game)
            db.session.commit()

        # Join the game
        participant = GameParticipant(
            game_id=game.id,
            user_id=user.id,
            joined_at=datetime.utcnow()
        )
        db.session.add(participant)

        # Deduct bet amount
        user.balance -= bet_amount
        db.session.commit()

        # Get current player count
        player_count = GameParticipant.query.filter_by(game_id=game.id).count()

        update.message.reply_text(
            f"🎮 You've joined Game #{game.id}!\n\n"
            f"Bet Amount: ETB {bet_amount:.2f}\n"
            f"Players: {player_count}/3\n\n"
            f"Waiting for more players..."
        )

        # If game is full, start it
        if player_count >= 3:
            start_game(game.id, context)

    except Exception as e:
        LOGGER.error(f"Error in play command: {e}")
        update.message.reply_text("An error occurred. Please try again.")

def start_game(game_id: int, context: CallbackContext) -> None:
    """Start a game when it has enough players"""
    try:
        game = Game.query.get(game_id)
        if not game:
            return

        game.status = GAME_STATES['IN_PROGRESS']
        game.started_at = datetime.utcnow()
        db.session.commit()

        # Notify all players
        for participant in game.participants:
            try:
                reply_markup = InlineKeyboardMarkup(GAME_CHOICES)
                context.bot.send_message(
                    chat_id=participant.user.telegram_id,
                    text=(
                        f"🎮 Game #{game.id} is starting!\n\n"
                        f"Bet amount: ETB {game.bet_amount:.2f}\n"
                        f"Make your choice:"
                    ),
                    reply_markup=reply_markup
                )
            except Exception as e:
                LOGGER.error(f"Error notifying player {participant.user_id}: {e}")

    except Exception as e:
        LOGGER.error(f"Error starting game: {e}")

def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    query.answer()

    try:
        if query.data == "main_menu":
            reply_markup = InlineKeyboardMarkup(MAIN_KEYBOARD)
            query.edit_message_text(
                "Welcome to Rock Paper Scissors Bot! 🎮\n"
                "What would you like to do?",
                reply_markup=reply_markup
            )

        elif query.data == "wallet":
            user = User.query.filter_by(telegram_id=update.effective_user.id).first()
            if not user:
                query.edit_message_text("You need an account first! Use /account create")
                return

            reply_markup = InlineKeyboardMarkup(WALLET_KEYBOARD)
            query.edit_message_text(
                f"💰 *Your Wallet*\n\n"
                f"Current Balance: ETB {user.balance:.2f}\n\n"
                f"What would you like to do?",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif query.data.startswith("choice_"):
            choice = query.data.split("_")[1]
            handle_game_choice(update, context, choice)

    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}")
        query.edit_message_text("An error occurred. Please try again.")

def handle_game_choice(update: Update, context: CallbackContext, choice: str) -> None:
    """Handle a player's game choice"""
    query = update.callback_query
    user = User.query.filter_by(telegram_id=update.effective_user.id).first()

    try:
        # Find user's active game
        participant = GameParticipant.query.join(Game).filter(
            GameParticipant.user_id == user.id,
            Game.status == GAME_STATES['IN_PROGRESS']
        ).first()

        if not participant:
            query.edit_message_text("You're not in an active game!")
            return

        # Record the choice
        participant.choice = choice
        participant.choice_made_at = datetime.utcnow()
        db.session.commit()

        # Check if all players have made their choices
        game = participant.game
        all_participants = game.participants
        choices_made = sum(1 for p in all_participants if p.choice)

        if choices_made == len(all_participants):
            # Process game result
            process_game_result(game.id, context)
        else:
            query.edit_message_text(
                f"Choice recorded! ✅\n"
                f"Waiting for other players...\n"
                f"({choices_made}/{len(all_participants)} players ready)"
            )

    except Exception as e:
        LOGGER.error(f"Error handling game choice: {e}")
        query.edit_message_text("An error occurred. Please try again.")

def process_game_result(game_id: int, context: CallbackContext) -> None:
    """Process the game result and distribute prizes"""
    try:
        game = Game.query.get(game_id)
        if not game:
            return

        participants = game.participants
        choices = {p.user_id: p.choice for p in participants}
        
        # Calculate wins for each player
        wins = {p.user_id: 0 for p in participants}
        for p1 in participants:
            for p2 in participants:
                if p1.user_id != p2.user_id:
                    if beats(p1.choice, p2.choice):
                        wins[p1.user_id] += 1

        # Determine positions
        sorted_players = sorted(wins.items(), key=lambda x: x[1], reverse=True)
        positions = {}
        current_wins = None
        current_position = 0
        current_count = 0

        for player_id, win_count in sorted_players:
            if win_count != current_wins:
                current_position += current_count
                current_wins = win_count
                current_count = 1
            else:
                current_count += 1
            positions[player_id] = current_position

        # Calculate prize pool
        total_pot = game.bet_amount * len(participants)
        prizes = {
            1: total_pot * PRIZE_DISTRIBUTION['winner'],
            2: total_pot * PRIZE_DISTRIBUTION['second'],
            3: total_pot * PRIZE_DISTRIBUTION['third']
        }

        # Distribute prizes and update stats
        for participant in participants:
            position = positions[participant.user_id]
            participant.position = position
            
            if position in prizes:
                prize = prizes[position]
                participant.winnings = prize
                participant.user.balance += prize
                participant.user.total_winnings += prize
                
                if position == 1:
                    participant.user.games_won += 1
                    game.winner_id = participant.user_id
            
            participant.user.games_played += 1

        # Update game status
        game.status = GAME_STATES['COMPLETED']
        game.completed_at = datetime.utcnow()

        # Update daily stats
        today = datetime.utcnow().date()
        stats = DailyStats.get_or_create(today)
        stats.total_games += 1
        stats.total_volume += total_pot
        stats.house_earnings += total_pot * PRIZE_DISTRIBUTION['house']

        db.session.commit()

        # Send results to all players
        for participant in participants:
            try:
                result_text = generate_result_text(game, participant)
                context.bot.send_message(
                    chat_id=participant.user.telegram_id,
                    text=result_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Error sending result to player {participant.user_id}: {e}")

    except Exception as e:
        LOGGER.error(f"Error processing game result: {e}")
        db.session.rollback()

def generate_result_text(game: Game, participant: GameParticipant) -> str:
    """Generate result text for a player"""
    text = [
        f"🎮 *Game #{game.id} Results*\n",
        "\n*Player Choices:*"
    ]

    # Show all players' choices
    for p in game.participants:
        text.append(f"{p.user.username}: {get_choice_emoji(p.choice)}")

    text.append("\n*Final Positions:*")
    for p in sorted(game.participants, key=lambda x: x.position):
        prize_text = f" (ETB {p.winnings:.2f})" if p.winnings else ""
        text.append(f"{get_position_emoji(p.position)} {p.user.username}{prize_text}")

    # Add personal result
    text.append("\n*Your Result:*")
    if participant.position == 1:
        text.append(f"🎉 You WON ETB {participant.winnings:.2f}!")
    elif participant.winnings:
        text.append(f"👏 You came in {get_position_text(participant.position)} and won ETB {participant.winnings:.2f}!")
    else:
        text.append("Better luck next time!")

    text.append(f"\nNew Balance: ETB {participant.user.balance:.2f}")

    return "\n".join(text)

def get_choice_emoji(choice: str) -> str:
    """Get emoji for a choice"""
    return {
        'rock': '✊ Rock',
        'paper': '✋ Paper',
        'scissors': '✌️ Scissors'
    }.get(choice, '❓ Unknown')

def get_position_emoji(position: int) -> str:
    """Get emoji for a position"""
    return {
        1: '🥇',
        2: '🥈',
        3: '🥉'
    }.get(position, '🏅')

def get_position_text(position: int) -> str:
    """Get text for a position"""
    return {
        1: 'first',
        2: 'second',
        3: 'third'
    }.get(position, str(position) + 'th')

def beats(choice1: str, choice2: str) -> bool:
    """Determine if choice1 beats choice2"""
    return (
        (choice1 == 'rock' and choice2 == 'scissors') or
        (choice1 == 'paper' and choice2 == 'rock') or
        (choice1 == 'scissors' and choice2 == 'paper')
    )

def main() -> None:
    """Start the bot"""
    try:
        updater = Updater(BOT_TOKEN)
        dispatcher = updater.dispatcher

        # Add handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("account", account_command))
        dispatcher.add_handler(CommandHandler("wallet", wallet_command))
        dispatcher.add_handler(CommandHandler("play", play_command))
        dispatcher.add_handler(CallbackQueryHandler(button_callback))

        # Start the bot
        updater.start_polling()
        LOGGER.info("Bot started successfully!")
        updater.idle()

    except Exception as e:
        LOGGER.error(f"Error starting bot: {e}")

if __name__ == '__main__':
    main()
