import requests
import os
from dotenv import load_dotenv

def test_bot_token():
    load_dotenv()
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        print("Error: BOT_TOKEN not found in .env file")
        return
    
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data.get('ok'):
            print("✅ Token is valid!")
            print(f"Bot details:")
            print(f"Username: @{data['result']['username']}")
            print(f"Bot ID: {data['result']['id']}")
            print(f"Bot Name: {data['result']['first_name']}")
        else:
            print("❌ Token is invalid!")
            print(f"Error: {data.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error occurred while testing token: {str(e)}")

if __name__ == "__main__":
    test_bot_token() 