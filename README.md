# Rock Paper Scissors Telegram Bot

A Telegram bot for playing Rock Paper Scissors with real money integration using Chapa Wallet.

## Features

- 🎮 Play Rock Paper Scissors with real players
- 💰 Integrated payment system with Chapa Wallet
- 🏆 Competitive gameplay with prizes
- 📊 Player statistics and leaderboards
- 💳 Secure deposit and withdrawal system

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/rps-telegram-bot.git
cd rps-telegram-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```env
BOT_TOKEN=your_telegram_bot_token
CHAPA_SECRET_KEY=your_chapa_secret_key
CHAPA_PUBLIC_KEY=your_chapa_public_key
ADMIN_USERS=comma_separated_telegram_ids
DATABASE_URL=sqlite:///rps_game.db
```

4. Initialize the database:
```bash
python
>>> from app import db
>>> db.create_all()
>>> exit()
```

5. Run the bot:
```bash
python run_bot.py
```

## Game Rules

1. Each game requires 3 players
2. Players make their choice (Rock, Paper, or Scissors)
3. Winners are determined by standard Rock Paper Scissors rules
4. Prize distribution:
   - 1st place: 60% of pot
   - 2nd place: 20% of pot
   - 3rd place: 10% of pot
   - House fee: 10% of pot

## Commands

- `/start` - Start the bot
- `/account create` - Create a new account
- `/account info` - View your account info
- `/account delete` - Delete your account
- `/wallet` - Manage your wallet
- `/play [amount]` - Join or create a game
- `/help` - Show help message

## Payment System

### Deposits
1. Use `/wallet` command
2. Select "Deposit"
3. Enter amount (min: 10 ETB)
4. Complete payment through Chapa

### Withdrawals
1. Use `/wallet` command
2. Select "Withdraw"
3. Enter amount (min: 50 ETB)
4. Provide Chapa wallet address
5. Wait for admin approval

## Development

The project structure:
```
├── app.py              # Flask application
├── config.py           # Configuration settings
├── models.py           # Database models
├── payments.py         # Payment system integration
├── run_bot.py         # Main bot code
├── requirements.txt    # Dependencies
└── README.md          # Documentation
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, contact @YourUsername on Telegram or open an issue on GitHub.
