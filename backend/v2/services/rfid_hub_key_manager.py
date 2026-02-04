"""
RFID Marathon Management System - RFID Hub Key Manager
Security Level: Military-grade
Last Updated: January 22, 2026

This module manages encryption/decryption of RFID hub authentication keys.
Hub secrets are stored as plaintext in environment variables and encrypted
for transmission/validation using Fernet.
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from constants import EnvVars, RFID_HUB_KEY_ENCRYPTION_ALGORITHM
from basefunctions import (
    get_env_variable,
    EncryptionError,
)
from services.fernet_manager import get_fernet_manager

logger = logging.getLogger(__name__)


class RFIDHubKeyManager:
    """
    Manages RFID hub authentication key encryption and validation.
    - Reads plaintext hub secrets from environment
    - Encrypts them for hub configuration
    - Validates encrypted keys sent by hubs
    """
    
    def __init__(self):
        """Initialize with Fernet manager for key encryption"""
        self.fernet_manager = get_fernet_manager()
        self._encrypted_keys_cache = {}
    
    def _load_hub_secret(self, hub_type: str) -> str:
        """
        Load plaintext hub secret from environment.
        
        Args:
            hub_type: 'start' or 'end'
            
        Returns:
            str: Plaintext hub secret
            
        Raises:
            EncryptionError: If secret not configured
        """
        if hub_type == "start":
            env_var = EnvVars.RFID_START_HUB_SECRET
            hub_name = "Start Hub"
        elif hub_type == "end":
            env_var = EnvVars.RFID_END_HUB_SECRET
            hub_name = "End Hub"
        else:
            raise ValueError(f"Invalid hub type: {hub_type}")
        
        secret = get_env_variable(env_var, required=True)
        if not secret:
            raise EncryptionError(f"{hub_name} secret not configured in environment")
        
        return secret
    
    def get_encrypted_key_for_hub(self, hub_type: str) -> str:
        """
        Get encrypted key for hub configuration.
        This key should be configured on the RFID hub.
        
        Args:
            hub_type: 'start' or 'end'
            
        Returns:
            str: Encrypted key ready for hub configuration
        """
        # Return cached value if available
        if hub_type in self._encrypted_keys_cache:
            return self._encrypted_keys_cache[hub_type]
        
        try:
            plaintext_secret = self._load_hub_secret(hub_type)
            encrypted_key = self.fernet_manager.encrypt(plaintext_secret)
            self._encrypted_keys_cache[hub_type] = encrypted_key
            
            logger.info(f"✓ Generated encrypted key for {hub_type} hub - {encrypted_key}")
            return encrypted_key
            
        except Exception as e:
            logger.error(f"✗ Failed to generate encrypted key for {hub_type} hub: {e}")
            raise EncryptionError(f"Failed to encrypt hub key: {str(e)}")
    
    def validate_hub_key(self, hub_type: str, received_encrypted_key: str) -> bool:
        """
        Validate an encrypted key received from RFID hub.
        
        Args:
            hub_type: 'start' or 'end'
            received_encrypted_key: Encrypted key sent by hub
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        try:
            # Get expected encrypted key
            expected_encrypted_key = self.get_encrypted_key_for_hub(hub_type)
            
            # Compare encrypted keys directly (most secure approach)
            # Both must encrypt the same plaintext, so encrypted values should match
            is_valid = received_encrypted_key == expected_encrypted_key
            
            if is_valid:
                logger.debug(f"✓ Valid encrypted key from {hub_type} hub")
            else:
                logger.warning(f"✗ Invalid encrypted key from {hub_type} hub")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"✗ Error validating hub key: {e}")
            return False
    
    def decrypt_and_validate_hub_key(self, hub_type: str, received_encrypted_key: str) -> bool:
        """
        Alternative validation: decrypt received key and compare plaintext.
        More flexible if encrypted values differ between runs (e.g., with timestamps).
        
        Args:
            hub_type: 'start' or 'end'
            received_encrypted_key: Encrypted key sent by hub
            
        Returns:
            bool: True if decrypted plaintext matches stored secret
        """
        try:
            # Decrypt received key
            received_secret = self.fernet_manager.decrypt(received_encrypted_key)
            
            # Get expected plaintext secret
            expected_secret = self._load_hub_secret(hub_type)
            
            # Compare plaintext values
            is_valid = received_secret == expected_secret
            
            if is_valid:
                logger.debug(f"✓ Valid decrypted key from {hub_type} hub")
            else:
                logger.warning(f"✗ Invalid decrypted key from {hub_type} hub")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"✗ Error validating decrypted hub key: {e}")
            return False


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_rfid_hub_key_manager_instance: Optional[RFIDHubKeyManager] = None


def get_rfid_hub_key_manager() -> RFIDHubKeyManager:
    """
    Get or create singleton instance of RFIDHubKeyManager.
    
    Returns:
        RFIDHubKeyManager: Singleton instance
    """
    global _rfid_hub_key_manager_instance
    
    if _rfid_hub_key_manager_instance is None:
        _rfid_hub_key_manager_instance = RFIDHubKeyManager()
    
    return _rfid_hub_key_manager_instance
