"""
RFID Marathon Management System - Fernet Encryption Manager
Security Level: Military-grade
Last Updated: January 21, 2026

This module manages Fernet symmetric encryption for database storage.
Participant names are encrypted at rest using Fernet.
"""

import logging
import base64
from typing import Optional
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from constants import FERNET_KEY_ROTATION_DAYS, EnvVars
from basefunctions import (
    get_env_variable,
    hash_data_sha256,
    get_current_timestamp_utc,
    EncryptionError,
)
from models import EncryptionKey

logger = logging.getLogger(__name__)


class FernetManager:
    """
    Manages Fernet encryption/decryption with key rotation support.
    """
    
    def __init__(self):
        """Initialize Fernet manager with master key from environment"""
        master_key = get_env_variable(EnvVars.FERNET_MASTER_KEY, required=True)
        
        # Validate master key format
        try:
            # Master key must be 32 bytes, base64-encoded (44 characters)
            if master_key is None or len(master_key) != 44:
                raise ValueError("Fernet master key must be 44 characters (base64-encoded 32 bytes)")
            self.master_key = master_key.encode('utf-8')
            self.fernet = Fernet(self.master_key)
            logger.info("✓ Fernet encryption initialized")
        except Exception as e:
            logger.critical(f"✗ Invalid Fernet master key: {e}")
            raise EncryptionError("Invalid encryption key format")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string using Fernet.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            str: Base64-encoded encrypted string
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")
        
        try:
            plaintext_bytes = plaintext.encode('utf-8')
            encrypted_bytes = self.fernet.encrypt(plaintext_bytes)
            encrypted_str = encrypted_bytes.decode('utf-8')
            
            logger.debug(f"Encrypted data (length: {len(plaintext)} -> {len(encrypted_str)})")
            return encrypted_str
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt Fernet-encrypted string.
        
        Args:
            encrypted_text: Base64-encoded encrypted string
            
        Returns:
            str: Decrypted plaintext
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not encrypted_text:
            raise EncryptionError("Cannot decrypt empty string")
        
        try:
            encrypted_bytes = encrypted_text.encode('utf-8')
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            plaintext = decrypted_bytes.decode('utf-8')
            
            logger.debug(f"Decrypted data (length: {len(encrypted_text)} -> {len(plaintext)})")
            return plaintext
            
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or corrupted data")
            raise EncryptionError("Decryption failed: Invalid or corrupted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Decryption failed: {str(e)}")
    
    def get_or_create_active_key(self, db: Session) -> EncryptionKey:
        """
        Get active encryption key from database or create new one.
        
        Args:
            db: Database session
            
        Returns:
            EncryptionKey: Active encryption key record
        """
        # Get current active key
        active_key = db.query(EncryptionKey).filter_by(is_active=True).first()
        
        if active_key:
            # Check if key needs rotation
            key_age_days = (get_current_timestamp_utc() - active_key.created_at).days
            
            if key_age_days >= FERNET_KEY_ROTATION_DAYS:
                logger.warning(f"Encryption key is {key_age_days} days old, rotation recommended")
            
            return active_key
        
        # Create new key if none exists
        key_hash = hash_data_sha256(self.master_key.decode('utf-8'))
        
        new_key = EncryptionKey(
            key_hash=key_hash,
            is_active=True,
            created_at=get_current_timestamp_utc()
        )
        
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        
        logger.info("✓ Created new encryption key record")
        return new_key
    
    def rotate_key(self, db: Session) -> EncryptionKey:
        """
        Rotate encryption key (for future implementation).
        Currently not implemented as it requires re-encrypting all data.
        
        Args:
            db: Database session
            
        Returns:
            EncryptionKey: New encryption key record
        """
        logger.warning("Key rotation requested but not yet implemented")
        
        # Mark current key as rotated
        current_key = db.query(EncryptionKey).filter_by(is_active=True).first()
        if current_key:
            current_key.is_active = False  # type: ignore[assignment]
            current_key.rotated_at = get_current_timestamp_utc()  # type: ignore[assignment]
        
        # Create new key
        key_hash = hash_data_sha256(self.master_key.decode('utf-8'))
        
        new_key = EncryptionKey(
            key_hash=key_hash,
            is_active=True,
            created_at=get_current_timestamp_utc()
        )
        
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        
        logger.info("✓ Encryption key rotated")
        return new_key

    def get_key_by_id(self, key_id: Optional[str]) -> str:
        """
        Return the active Fernet key (base64 url-safe, 32 bytes -> 44 chars).
        """
        # For now we use the master key; rotation can map by id later.
        key = self.master_key
        return key.decode("utf-8") if isinstance(key, (bytes, bytearray)) else str(key)

    def get_active_key_value(self) -> str:
        """Convenience: current active key as string."""
        key = self.master_key
        return key.decode("utf-8") if isinstance(key, (bytes, bytearray)) else str(key)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_fernet_manager = None


def get_fernet_manager() -> FernetManager:
    """
    Get global Fernet manager instance.
    
    Returns:
        FernetManager: Singleton instance
    """
    global _fernet_manager
    
    if _fernet_manager is None:
        _fernet_manager = FernetManager()
    
    return _fernet_manager
