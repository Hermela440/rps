"""Chapa payment integration"""
import requests
import logging
from typing import Dict, Tuple, Optional
from config import (
    CHAPA_SECRET_KEY,
    CHAPA_API_URL,
    CURRENCY,
    PAYMENT_CALLBACK_URL,
    PAYMENT_SUCCESS_URL,
    TEST_MODE
)

logger = logging.getLogger(__name__)

class ChapaPayment:
    """Chapa payment integration class"""
    
    def __init__(self, secret_key: str = CHAPA_SECRET_KEY):
        self.secret_key = secret_key
        self.base_url = CHAPA_API_URL
        self.headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }
        logger.info(f"Initialized Chapa payment with {'test' if TEST_MODE else 'live'} mode")

    def initialize_payment(
        self,
        amount: float,
        email: str,
        tx_ref: str,
        first_name: str = "User",
        last_name: str = "Customer"
    ) -> Tuple[bool, str, Optional[str]]:
        """Initialize a payment transaction with Chapa"""
        try:
            payload = {
                "amount": str(amount),
                "currency": CURRENCY,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "tx_ref": tx_ref,
                "callback_url": PAYMENT_CALLBACK_URL,
                "return_url": PAYMENT_SUCCESS_URL,
                "customization": {
                    "title": "RPS Game Deposit",
                    "description": f"Deposit {amount} {CURRENCY} to your game wallet"
                }
            }
            
            logger.info(f"Initializing payment for {amount} {CURRENCY}")
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    checkout_url = data["data"]["checkout_url"]
                    logger.info(f"Payment initialized successfully. Checkout URL: {checkout_url}")
                    return True, "Payment initialized", checkout_url
                else:
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"Chapa API error: {error_msg}")
                    return False, f"Payment initialization failed: {error_msg}", None
            
            logger.error(f"Chapa API error: {response.status_code} - {response.text}")
            return False, f"Failed to initialize payment: {response.text}", None

        except Exception as e:
            logger.error(f"Error initializing payment: {str(e)}")
            return False, f"Error: {str(e)}", None

    def verify_payment(self, tx_ref: str) -> Tuple[bool, str, Dict]:
        """Verify a payment transaction"""
        try:
            logger.info(f"Verifying payment for tx_ref: {tx_ref}")
            response = requests.get(
                f"{self.base_url}/transaction/verify/{tx_ref}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    logger.info(f"Payment verified successfully for tx_ref: {tx_ref}")
                    return True, "Payment verified", data["data"]
                else:
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"Payment verification failed: {error_msg}")
                    return False, f"Payment verification failed: {error_msg}", {}
            
            logger.error(f"Chapa API error: {response.status_code} - {response.text}")
            return False, f"Payment verification failed: {response.text}", {}

        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return False, f"Error: {str(e)}", {} 