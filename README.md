# Rock Paper Scissors Game Bot

A Telegram bot for playing Rock Paper Scissors with betting functionality. Players can create rooms, join games, and win prizes.

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- A Telegram bot token (get from [@BotFather](https://t.me/BotFather))

## Installation Steps

1. Clone the repository:
```bash
git clone <repository-url>
cd rps
```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv venv37
.\venv37\Scripts\activate

# Linux/Mac
python3 -m venv venv37
source venv37/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"

# Windows Command Prompt
set TELEGRAM_BOT_TOKEN=your_bot_token_here

# Linux/Mac
export TELEGRAM_BOT_TOKEN=your_bot_token_here
```

## Running the Bot

1. Start the bot:
```bash
python run_bot.py
```

2. Open Telegram and search for your bot username
3. Start a chat with the bot by clicking "Start" or sending `/start`

## How to Play

1. **Create Account**
   - Send `/start` to create your account
   - Use `/deposit` to add funds to your wallet

2. **Create a Room**
   - Use `/create_room <amount>` to create a new game room
   - Example: `/create_room 100` creates a room with 100 ETB bet

3. **Join a Game**
   - Use `/join_game <room_code> <bet_amount>` to join a room
   - Example: `/join_game ABC12 100` joins room ABC12 with 100 ETB bet

4. **Game Flow**
   - Wait for 3 players to join
   - When full, the game starts automatically
   - Choose your move (Rock 🪨, Paper 📄, or Scissors ✂️)
   - Winner takes 95% of the pot

5. **Other Commands**
   - `/balance` - Check your wallet balance
   - `/game_status` - Check current game status
   - `/leave_room` - Leave current room
   - `/history` - View your game history
   - `/leaderboard` - See top players
   - `/help` - Show all commands

## Betting Rules

- Minimum bet: 10 ETB
- Maximum bet: 1000 ETB
- Winner takes 95% of the pot
- House fee: 5%

## Game Rules

1. Three players required to start
2. Each player makes one move
3. Rock beats Scissors
4. Scissors beats Paper
5. Paper beats Rock
6. If all players choose the same move, it's a draw
7. In case of a draw, the pot is split between winners

## Troubleshooting

If you encounter any issues:

1. Check if the bot is running
2. Verify your Telegram bot token is correct
3. Ensure you have sufficient balance
4. Make sure you're not already in a room
5. Check if the room code is correct

## Support

For support or bug reports, please contact the bot administrator.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
