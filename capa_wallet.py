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
from config import LOGGER

# Configuration for Capa Wallet API
CAPA_API_URL = os.environ.get("CAPA_API_URL", "https://api.capawallet.com/v1")
CAPA_API_KEY = os.environ.get("CAPA_API_KEY", "")
CAPA_SECRET_KEY = os.environ.get("CAPA_SECRET_KEY", "")

# Check if API keys are properly set
if not CAPA_API_KEY or not CAPA_SECRET_KEY:
    LOGGER.warning("Capa Wallet API keys not configured. Using mock payment system.")

class CapaWallet:
    """Capa Wallet Payment Gateway Integration"""
    
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
                "redirect_url": "https://rps-arena.replit.app/payment/success",
                "cancel_url": "https://rps-arena.replit.app/payment/cancel",
                "webhook_url": "https://rps-arena.replit.app/api/payment/webhook"
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
    def process_withdrawal(user_id, amount, wallet_address, description=None):
        """
        Process a withdrawal to a Capa Wallet address
        
        Args:
            user_id (int): Internal user ID
            amount (float): Amount to withdraw
            wallet_address (str): Capa Wallet address
            description (str, optional): Withdrawal description
            
        Returns:
            tuple: (success, data/message)
        """
        if not description:
            description = f"Withdrawal from RPS Arena - User {user_id}"
            
        if not CAPA_API_KEY or not CAPA_SECRET_KEY:
            # Mock withdrawal for testing
            withdrawal_id = f"mock_withdrawal_{int(time.time())}"
            return True, {
                "withdrawal_id": withdrawal_id,
                "status": "pending",
                "amount": amount,
                "created_at": int(time.time())
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {CAPA_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "amount": amount,
                "currency": "USD",
                "destination": wallet_address,
                "description": description,
                "metadata": {
                    "user_id": user_id
                }
            }
            
            response = requests.post(
                f"{CAPA_API_URL}/withdrawals",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, data
            else:
                LOGGER.error(f"Capa Wallet API error: {response.status_code} - {response.text}")
                return False, f"Withdrawal service error: {response.status_code}"
                
        except Exception as e:
            LOGGER.error(f"Error processing Capa Wallet withdrawal: {str(e)}")
            return False, f"Withdrawal service unavailable: {str(e)}"

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