"""
Capa Wallet Integration for RPS Arena
This module handles integration with Capa Wallet payment system
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from config import (
    CAPA_API_URL,
    CAPA_API_KEY,
    CAPA_SECRET_KEY,
    CURRENCY,
    PAYMENT_CALLBACK_URL,
    PAYMENT_SUCCESS_URL
)
from typing import Dict, Tuple, Optional

# Configuration for Capa Wallet API
LOGGER = logging.getLogger(__name__)

# Check if API keys are properly set
if not CAPA_API_KEY or not CAPA_SECRET_KEY:
    LOGGER.warning("Capa Wallet API keys not configured. Using mock payment system.")

class CapaWallet:
    """Capa Wallet integration class"""
    
    def __init__(self, api_key: str = CAPA_API_KEY, secret_key: str = CAPA_SECRET_KEY):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = CAPA_API_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Secret-Key": secret_key,
            "Content-Type": "application/json"
        }

    def create_wallet(self, user_id: str, email: str) -> Tuple[bool, str, Optional[Dict]]:
        """Create a new Capa wallet for a user"""
        try:
            payload = {
                "user_id": user_id,
                "email": email,
                "currency": CURRENCY
            }
            
            response = requests.post(
                f"{self.base_url}/wallets/create",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "Wallet created successfully", data["data"]
            
            return False, "Failed to create wallet", None

        except Exception as e:
            LOGGER.error(f"Error creating wallet: {str(e)}")
            return False, f"Error: {str(e)}", None

    def get_wallet_balance(self, wallet_id: str) -> Tuple[bool, str, Optional[float]]:
        """Get wallet balance"""
        try:
            response = requests.get(
                f"{self.base_url}/wallets/{wallet_id}/balance",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "Balance retrieved successfully", float(data["data"]["balance"])
            
            return False, "Failed to get wallet balance", None

        except Exception as e:
            LOGGER.error(f"Error getting wallet balance: {str(e)}")
            return False, f"Error: {str(e)}", None

    def initialize_deposit(
        self,
        wallet_id: str,
        amount: float,
        tx_ref: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Initialize a deposit transaction"""
        try:
            payload = {
                "wallet_id": wallet_id,
                "amount": str(amount),
                "currency": CURRENCY,
                "tx_ref": tx_ref,
                "callback_url": PAYMENT_CALLBACK_URL,
                "return_url": PAYMENT_SUCCESS_URL
            }
            
            response = requests.post(
                f"{self.base_url}/deposits/initialize",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "Deposit initialized", data["data"]["checkout_url"]
            
            return False, "Failed to initialize deposit", None

        except Exception as e:
            LOGGER.error(f"Error initializing deposit: {str(e)}")
            return False, f"Error: {str(e)}", None

    def process_withdrawal(
        self,
        wallet_id: str,
        amount: float,
        bank_details: Dict[str, str]
    ) -> Tuple[bool, str, Optional[str]]:
        """Process a withdrawal request"""
        try:
            payload = {
                "wallet_id": wallet_id,
                "amount": str(amount),
                "currency": CURRENCY,
                "bank_name": bank_details.get("bank_name"),
                "account_number": bank_details.get("account_number"),
                "account_name": bank_details.get("account_name"),
                "bank_branch": bank_details.get("bank_branch")
            }
            
            response = requests.post(
                f"{self.base_url}/withdrawals/process",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "Withdrawal processed", data["data"]["reference"]
            
            return False, "Failed to process withdrawal", None

        except Exception as e:
            LOGGER.error(f"Error processing withdrawal: {str(e)}")
            return False, f"Error: {str(e)}", None

    def verify_transaction(self, tx_ref: str) -> Tuple[bool, str, Optional[Dict]]:
        """Verify a transaction status"""
        try:
            response = requests.get(
                f"{self.base_url}/transactions/verify/{tx_ref}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "Transaction verified", data["data"]
            
            return False, "Transaction verification failed", None

        except Exception as e:
            LOGGER.error(f"Error verifying transaction: {str(e)}")
            return False, f"Error: {str(e)}", None

    def get_transaction_history(
        self,
        wallet_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[bool, str, Optional[list]]:
        """Get wallet transaction history"""
        try:
            params = {
                "wallet_id": wallet_id,
                "limit": limit,
                "offset": offset
            }
            
            response = requests.get(
                f"{self.base_url}/transactions/history",
                params=params,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, "History retrieved", data["data"]["transactions"]
            
            return False, "Failed to get transaction history", None

        except Exception as e:
            LOGGER.error(f"Error getting transaction history: {str(e)}")
            return False, f"Error: {str(e)}", None

    @staticmethod
    def generate_payment_link(amount, user_id, description=None):
        """
        Generate a payment link for user to deposit funds
        
        Args:
            amount (float): Amount to deposit
            user_id (int): Internal user ID
            description (str, optional): Payment description
            
        Returns:
            tuple: (success, data/message)
        """
        if not description:
            description = f"Deposit to RPS Arena - User {user_id}"
            
        if not CAPA_API_KEY or not CAPA_SECRET_KEY:
            # Mock response for testing
            payment_id = f"mock_payment_{int(time.time())}"
            payment_url = f"https://pay.capawallet.com/{payment_id}"
            return True, {
                "payment_id": payment_id,
                "payment_url": payment_url,
                "amount": amount,
                "expires_at": int(time.time()) + 3600,  # Expires in 1 hour
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {CAPA_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "amount": amount,
                "currency": "USD",
                "description": description,
                "metadata": {
                    "user_id": user_id
                },
                "redirect_url": config.PAYMENT_SUCCESS_URL,
                "cancel_url": config.PAYMENT_CANCEL_URL,
                "webhook_url": config.PAYMENT_WEBHOOK_URL
            }
            
            response = requests.post(
                f"{CAPA_API_URL}/payments",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, data
            else:
                LOGGER.error(f"Capa Wallet API error: {response.status_code} - {response.text}")
                return False, f"Payment service error: {response.status_code}"
                
        except Exception as e:
            LOGGER.error(f"Error creating Capa Wallet payment: {str(e)}")
            return False, f"Payment service unavailable: {str(e)}"
    
    @staticmethod
    def verify_payment(payment_id):
        """
        Verify a payment status
        
        Args:
            payment_id (str): Payment ID to verify
            
        Returns:
            tuple: (success, is_paid, data/message)
        """
        if not CAPA_API_KEY or not CAPA_SECRET_KEY:
            # Mock verification for testing
            is_mock = payment_id.startswith("mock_payment_")
            if is_mock:
                return True, True, {
                    "id": payment_id,
                    "status": "completed",
                    "amount": 100.0,
                    "payment_time": int(time.time())
                }
            return False, False, "Invalid payment ID"
        
        try:
            headers = {
                "Authorization": f"Bearer {CAPA_API_KEY}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{CAPA_API_URL}/payments/{payment_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                is_paid = data.get("status") == "completed"
                return True, is_paid, data
            else:
                LOGGER.error(f"Capa Wallet API error: {response.status_code} - {response.text}")
                return False, False, f"Payment verification failed: {response.status_code}"
                
        except Exception as e:
            LOGGER.error(f"Error verifying Capa Wallet payment: {str(e)}")
            return False, False, f"Payment verification unavailable: {str(e)}"
    
    @staticmethod
    def verify_webhook_signature(payload, signature_header):
        """
        Verify the webhook signature from Capa Wallet
        
        Args:
            payload (str): Raw request body
            signature_header (str): Signature header from request
            
        Returns:
            bool: True if signature is valid
        """
        if not CAPA_API_KEY or not CAPA_SECRET_KEY:
            # Mock verification for testing
            return True
            
        try:
            # This is a simplified example. In production, you would implement
            # proper HMAC signature verification based on Capa Wallet's specifications
            # The exact implementation depends on how Capa Wallet signs webhooks
            
            return True  # Placeholder for actual implementation
            
        except Exception as e:
            LOGGER.error(f"Error verifying webhook signature: {str(e)}")
            return False