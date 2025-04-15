import os
import subprocess
import importlib.util

def check_module(module_name):
    """Check if a module is available"""
    return importlib.util.find_spec(module_name) is not None

def setup():
    """Setup the project environment"""
    print("Setting up RPS Arena project...")
    
    # 1. Create requirements.txt if it doesn't exist
    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w') as f:
            f.write("""# Core dependencies
flask==3.0.0
flask-sqlalchemy==3.1.1
python-telegram-bot==13.15  # Using older version to avoid imghdr dependency
requests==2.31.0
sqlalchemy==2.0.23
werkzeug==3.0.1

# Additional dependencies
email-validator==2.1.0
psycopg2-binary==2.9.9
gunicorn==21.2.0
""")
        print("Created requirements.txt")
    
    # 2. Install dependencies
    print("Installing dependencies...")
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'])
    
    # 3. Run template updater
    print("Updating templates...")
    # Import and run the update_templates function
    from update_templates import update_templates
    update_templates()
    
    # 4. Fix imports in capa_wallet.py
    with open('capa_wallet.py', 'r', encoding='utf-8') as file:
        content = file.read()
    
    if "import config" not in content:
        # Add import at the top of the file
        lines = content.split('\n')
        import_line = "import config"
        if "from config import" in content:
            # Already importing from config, update it
            for i, line in enumerate(lines):
                if line.startswith("from config import"):
                    lines[i] = line + ", PAYMENT_SUCCESS_URL, PAYMENT_CANCEL_URL, PAYMENT_WEBHOOK_URL"
                    break
        else:
            # Add new import
            for i, line in enumerate(lines):
                if line.startswith("import"):
                    lines.insert(i+1, import_line)
                    break
            
        # Update the content
        content = '\n'.join(lines)
        
        # Replace hardcoded URLs
        content = content.replace(
            '"redirect_url": "https://your-name-rps.example.com/payment/success"',
            '"redirect_url": config.PAYMENT_SUCCESS_URL'
        )
        content = content.replace(
            '"cancel_url": "https://your-name-rps.example.com/payment/cancel"',
            '"cancel_url": config.PAYMENT_CANCEL_URL'
        )
        content = content.replace(
            '"webhook_url": "https://your-name-rps.example.com/api/payment/webhook"',
            '"webhook_url": config.PAYMENT_WEBHOOK_URL'
        )
        
        with open('capa_wallet.py', 'w', encoding='utf-8') as file:
            file.write(content)
        
        print("Updated capa_wallet.py")
    
    # 5. Fix imports in telegram_bot.py
    with open('telegram_bot.py', 'r', encoding='utf-8') as file:
        content = file.read()
    
    if "from config import BASE_URL" not in content:
        # Add import at the top of the file
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith("from config import"):
                lines[i] = line + ", BASE_URL"
                break
                
        # Update the content
        content = '\n'.join(lines)
        
        # Replace hardcoded URLs
        content = content.replace(
            'base_url = "https://your-name-rps.example.com"',
            'base_url = BASE_URL'
        )
        
        with open('telegram_bot.py', 'w', encoding='utf-8') as file:
            file.write(content)
        
        print("Updated telegram_bot.py")
    
    print("\nSetup completed successfully!")
    print("\nTo run the project:")
    print("1. Activate your virtual environment")
    print("2. Run 'python main.py'")
    print("\nNote: You can set the BASE_URL environment variable to change the base URL.")
    print("Example: export BASE_URL=https://your-domain.com")

if __name__ == "__main__":
    setup()
