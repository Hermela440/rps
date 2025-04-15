# RPS Arena Bot

A Telegram bot for playing Rock-Paper-Scissors with virtual betting.

## Setup Instructions

1. Install Python 3.7 or higher
2. Clone this repository
3. Run the setup script: 
```

## Features

- Play Rock-Paper-Scissors with 3 players
- Virtual wallet system with mock payments
- Betting on matches
- Leaderboard and statistics
- Admin dashboard

## Bot Commands

### Account Commands 🔐
- `/create_account` - Create your account (first step!)
- `/balance` - Check your wallet balance
- `/deposit` - Add funds to your wallet
- `/withdraw` - Withdraw funds
- `/delete_account` - Delete your account
- `/history` - View your game history
- `/whoami` - Debug command to see your account info

### Game Commands 🎮
- `/join_game` - Join a match with default bet ($10)
- `/join_game [amount]` - Join with custom bet amount
- `/game_status` - Check status of current game

### Stats Commands 📊
- `/leaderboard` - View top players
- `/profile` - View your stats

### Help Commands ℹ️
- `/help` - Show all available commands
- `/about` - Learn about the bot

## Admin Commands

Admin commands are only available to users whose Telegram ID is in the ADMIN_USERS list in config.py.

- `/admin_stats` - View system statistics
- `/admin_users` - View and manage users
- `/admin_games` - View recent games
- `/admin_withdrawals` - Manage withdrawal requests

## Admin Tool

The admin tool provides command-line utilities for managing the bot:

```
python admin_tool.py <command> [arguments]
```

Available commands:
- `list_users` - List all users
- `add_admin <telegram_id>` - Add user to admin list
- `remove_admin <telegram_id>` - Remove user from admin list
- `reset_cooldowns <telegram_id>` - Reset cooldowns for a user
- `clear_games` - Clear all waiting/active games
- `give_balance <telegram_id> <amount>` - Add balance to a user
- `create_user <telegram_id> <username>` - Manually create a user

## Troubleshooting

If you encounter issues with multiple users:

1. Check if all users have created accounts with `/create_account`
2. Use `/whoami` to verify account information
3. Reset cooldowns if needed: `python admin_tool.py reset_cooldowns <telegram_id>`
4. Ensure you have correct permissions in config.py
5. Clear stuck games: `python admin_tool.py clear_games`