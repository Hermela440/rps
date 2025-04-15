#!/usr/bin/env python3
"""
Add GIF animations to Telegram bot for Rock-Paper-Scissors game
"""

import os
import re

def update_telegram_bot():
    """Update telegram_bot.py to include GIF animations"""
    file_path = 'telegram_bot.py'
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add GIF URLs at the top of the file, after imports
    imports_end = content.find('# Commands dictionary for help message')
    if imports_end == -1:
        imports_end = content.find('COMMANDS = {')
    
    gif_urls = '''
# GIF URLs for game animations
ROCK_GIF = "https://media.giphy.com/media/3o7TKNjg8dxB5ysRnW/giphy.gif"
PAPER_GIF = "https://media.giphy.com/media/3o7527Rn1HxXWqgxuo/giphy.gif"
SCISSORS_GIF = "https://media.giphy.com/media/3o7TKRXwArnzrW52MM/giphy.gif"
ROCK_WINS_GIF = "https://media.giphy.com/media/3oxHQfvDdo6OrXwOPK/giphy.gif"
PAPER_WINS_GIF = "https://media.giphy.com/media/3o7TKH6gFrV1TCxfgs/giphy.gif"
SCISSORS_WINS_GIF = "https://media.giphy.com/media/3o7TKB3yoARvULNBmM/giphy.gif"
DRAW_GIF = "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif"

'''
    
    updated_content = content[:imports_end] + gif_urls + content[imports_end:]
    
    # Create a send_game_animation function
    button_callback_pos = updated_content.find('async def button_callback')
    if button_callback_pos == -1:
        print("Could not find button_callback function!")
        return
    
    send_animation_func = '''
async def send_game_animation(chat_id, game_id, context):
    """Send animated game results to a chat"""
    # Get game details
    game = Game.query.get(game_id)
    if not game or game.status != 'completed':
        return
    
    participants = GameParticipant.query.filter_by(game_id=game_id).all()
    if len(participants) < 2:
        return
    
    # Show participants making their choices
    choices_text = "🎮 *Game Results* 🎮\\n\\n"
    
    # Send loading message
    message = await context.bot.send_message(
        chat_id=chat_id,
        text="🎲 *Calculating Results* 🎲\\n\\nPreparing animation...",
        parse_mode='Markdown'
    )
    
    # Show each player's choice with animation
    for participant in participants:
        user = User.query.get(participant.user_id)
        username = user.username if user else "Unknown"
        
        if participant.choice == 'rock':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=ROCK_GIF,
                caption=f"{username} chose ROCK 🗿"
            )
        elif participant.choice == 'paper':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=PAPER_GIF,
                caption=f"{username} chose PAPER 📄"
            )
        elif participant.choice == 'scissors':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=SCISSORS_GIF,
                caption=f"{username} chose SCISSORS ✂️"
            )
    
    # Small delay for dramatic effect
    import asyncio
    await asyncio.sleep(1)
    
    # Show result animation
    result_text = "🏆 *Results* 🏆\\n\\n"
    
    if game.winner_id:
        winner = User.query.get(game.winner_id)
        winner_username = winner.username if winner else "Unknown"
        
        # Find winner's choice
        winner_choice = None
        for p in participants:
            if p.user_id == game.winner_id:
                winner_choice = p.choice
        
        if winner_choice == 'rock':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=ROCK_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with ROCK! 🎉\\n\\nRock crushes scissors!"
            )
        elif winner_choice == 'paper':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=PAPER_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with PAPER! 🎉\\n\\nPaper covers rock!"
            )
        elif winner_choice == 'scissors':
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=SCISSORS_WINS_GIF,
                caption=f"🎉 {winner_username} WINS with SCISSORS! 🎉\\n\\nScissors cut paper!"
            )
    else:
        # It's a draw
        await context.bot.send_animation(
            chat_id=chat_id,
            animation=DRAW_GIF,
            caption="It's a DRAW! No winner this time."
        )
    
    # Final result message
    pot_size = game.bet_amount * len(participants)
    if game.winner_id:
        winner = User.query.get(game.winner_id)
        platform_fee = pot_size * (PLATFORM_FEE_PERCENT / 100)
        winnings = pot_size - platform_fee
        
        result_text = f"Game #{game_id} Results:\\n"
        result_text += f"Winner: {winner.username}\\n"
        result_text += f"Pot: ${pot_size:.2f}\\n"
        result_text += f"Platform Fee: ${platform_fee:.2f}\\n"
        result_text += f"Winnings: ${winnings:.2f}"
    else:
        result_text = f"Game #{game_id} Results:\\n"
        result_text += "Result: Draw - Bets have been refunded."
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=result_text
    )

'''
    
    updated_content = updated_content[:button_callback_pos] + send_animation_func + updated_content[button_callback_pos:]
    
    # Update the button_callback function to use the animation for game results
    choice_pattern = r'(# Notify all participants about game results.*?)# Add link to web animation'
    choice_match = re.search(choice_pattern, updated_content, re.DOTALL)
    
    if choice_match:
        original_section = choice_match.group(1)
        animation_section = '''# Notify all participants about game results
                    for participant in game.participants:
                        user_obj = User.query.get(participant.user_id)
                        if user_obj.telegram_id:
                            try:
                                # Send animated results instead of text
                                await send_game_animation(user_obj.telegram_id, game.id, context)
                            except Exception as e:
                                LOGGER.error(f"Error sending game results to user {user_obj.telegram_id}: {e}")
                    
                    '''
        
        updated_content = updated_content.replace(original_section, animation_section)
    
    # Add a separate command to replay game animations
    replay_command = '''
@cooldown()
async def replay_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replay a game animation."""
    if not user_exists(update):
        await update.message.reply_text("You don't have an account yet. Use /create_account to get started.")
        return
    
    user = get_user_by_telegram_id(update.effective_user.id)
    update_user_activity(user.id)
    
    # Check if game ID is provided
    if not context.args or len(context.args) == 0:
        # Show recent games instead
        recent_games = db.session.query(Game).join(
            GameParticipant, Game.id == GameParticipant.game_id
        ).filter(
            GameParticipant.user_id == user.id,
            Game.status == 'completed'
        ).order_by(Game.completed_at.desc()).limit(5).all()
        
        if not recent_games:
            await update.message.reply_text("You haven't played any games yet. Use /join_game to start playing!")
            return
        
        # Create keyboard with recent games
        keyboard = []
        for game in recent_games:
            keyboard.append([InlineKeyboardButton(
                f"Game #{game.id} - {game.completed_at.strftime('%Y-%m-%d %H:%M')}",
                callback_data=f"replay_{game.id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Select a game to replay:",
            reply_markup=reply_markup
        )
        return
    
    # Get game ID from arguments
    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid game ID. Please provide a number.")
        return
    
    # Check if game exists and user participated
    game = Game.query.get(game_id)
    if not game or game.status != 'completed':
        await update.message.reply_text(f"Game #{game_id} not found or not completed.")
        return
    
    participant = GameParticipant.query.filter_by(
        game_id=game_id, user_id=user.id
    ).first()
    
    if not participant:
        await update.message.reply_text(f"You didn't participate in Game #{game_id}.")
        return
    
    # Send the animation
    await send_game_animation(update.message.chat_id, game_id, context)

'''
    
    # Add replay command right before main function
    main_pos = updated_content.find('async def main()')
    if main_pos != -1:
        updated_content = updated_content[:main_pos] + replay_command + updated_content[main_pos:]
    
    # Add replay button handling in button_callback
    replay_button_handler = '''    # Replay game animation
    elif data.startswith("replay_"):
        game_id = int(data.split("_")[1])
        await send_game_animation(update.callback_query.message.chat_id, game_id, context)
    
    '''
    
    # Find a good position to insert the replay handler
    withdraw_section = re.search(r'# Withdraw callbacks.*?elif data\.startswith\("admin_"\)', updated_content, re.DOTALL)
    if withdraw_section:
        insert_pos = withdraw_section.end()
        updated_content = updated_content[:insert_pos] + replay_button_handler + updated_content[insert_pos:]
    
    # Register the replay command in main()
    register_pattern = r'(application\.add_handler\(CommandHandler\("profile", profile\)\))'
    register_match = re.search(register_pattern, updated_content)
    
    if register_match:
        register_pos = register_match.end()
        replay_registration = '\n    application.add_handler(CommandHandler("replay", replay_game))'
        updated_content = updated_content[:register_pos] + replay_registration + updated_content[register_pos:]
    
    # Add to COMMANDS dictionary
    commands_pattern = r'(    "🎮 Game Commands": \{[^}]*\})'
    commands_match = re.search(commands_pattern, updated_content)
    
    if commands_match:
        original_commands = commands_match.group(1)
        updated_commands = original_commands.rstrip('}') + ',\n        "/replay": "Replay a game animation with GIFs"\n    }'
        updated_content = updated_content.replace(original_commands, updated_commands)
    
    # Write the updated file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print("✅ Added GIF animations to Telegram bot")
    print("  New commands:")
    print("  - /replay           - Replay recent games with animations")
    print("  - /replay [game_id] - Replay a specific game with animations")

def main():
    """Run the script"""
    print("Adding GIF Animations to Telegram Bot")
    print("====================================\n")
    
    update_telegram_bot()
    
    print("\nFeatures added:")
    print("1. Animated game results are now sent when a game completes")
    print("2. Players can replay game animations with the /replay command")
    print("3. Game results now show dramatic animations for each player's choice")
    print("\nRestart your bot to apply the changes!")

if __name__ == "__main__":
    main() 