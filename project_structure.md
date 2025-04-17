# Rock Paper Scissors Bot - Project Structure

```
rps_bot/
├── app/
│   ├── __init__.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── admin.py
│   │   │   ├── game.py
│   │   │   └── stats.py
│   │   ├── keyboards.py
│   │   └── messages.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logger.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── game.py
│   │   └── transaction.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── game.py
│   │   ├── payment.py
│   │   └── simulation.py
│   └── utils/
│       ├── __init__.py
│       ├── decorators.py
│       └── helpers.py
├── static/
│   ├── images/
│   └── animations/
├── templates/
├── tests/
│   ├── __init__.py
│   ├── test_bot.py
│   └── test_game.py
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── run.py
```

## Directory Structure Explanation

### `/app`
Main application package containing all the bot's code.

- `/bot`: Telegram bot-specific code
  - `/handlers`: Command handlers organized by feature
  - `keyboards.py`: Keyboard layouts and buttons
  - `messages.py`: Message templates and text

- `/core`: Core application components
  - `config.py`: Configuration settings
  - `database.py`: Database connection and setup
  - `logger.py`: Logging configuration

- `/models`: Database models
  - `user.py`: User model
  - `game.py`: Game and participant models
  - `transaction.py`: Transaction model

- `/services`: Business logic
  - `admin.py`: Admin functionality
  - `game.py`: Game logic
  - `payment.py`: Payment processing
  - `simulation.py`: RPS simulation

- `/utils`: Utility functions and helpers
  - `decorators.py`: Custom decorators
  - `helpers.py`: Helper functions

### `/static`
Static files like images and animations.

### `/templates`
HTML templates for web interface (if needed).

### `/tests`
Unit tests and test configurations.

### Root Files
- `.env.example`: Example environment variables
- `.gitignore`: Git ignore rules
- `README.md`: Project documentation
- `requirements.txt`: Python dependencies
- `run.py`: Application entry point 