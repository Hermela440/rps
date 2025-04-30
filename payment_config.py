"""Payment gateway configuration"""
from datetime import datetime, timezone
import uuid

# Chapa Configuration
CHAPA_SECRET_KEY = "CHAPUBK_TEST-HwMGYAL6nBm8KBYdMvJGUE6F4vkGxHdv"  # Test mode key
CHAPA_PUBLIC_KEY = "CHAPUBK_TEST-HwMGYAL6nBm8KBYdMvJGUE6F4vkGxHdv"   # Test mode key
CHAPA_API_URL = "https://api.chapa.co/v1"
CHAPA_WEBHOOK_SECRET = "MY_WEBHOOK_SECRET_TEST"  # Test webhook secret

# Payment Configuration
CURRENCY = "ETB"
PAYMENT_DESCRIPTION = "Rock Paper Scissors Game Payment"
PAYMENT_TITLE = "RPS Game"

# URLs
BASE_URL = "http://localhost:5000"  # Test environment URL
PAYMENT_SUCCESS_URL = f"{BASE_URL}/payment/success"
PAYMENT_CALLBACK_URL = f"{BASE_URL}/payment/callback"

def generate_transaction_ref():
    """Generate a unique transaction reference"""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    return f"RPS-{timestamp}-{unique_id}" 