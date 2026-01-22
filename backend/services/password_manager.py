"""
RFID Marathon Management System - Password Manager
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles secure password hashing and verification using bcrypt.
"""

import logging
import bcrypt

from constants import PASSWORD_BCRYPT_ROUNDS, PASSWORD_MIN_LENGTH
from basefunctions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)


class PasswordManager:
    """
    Manages password hashing and verification using bcrypt.
    """
    
    def __init__(self):
        """Initialize password manager"""
        self.cost_factor = PASSWORD_BCRYPT_ROUNDS
        logger.info(f"✓ Password manager initialized (bcrypt rounds: {self.cost_factor})")
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plaintext password
            
        Returns:
            str: Bcrypt hash (includes salt)
            
        Raises:
            ValidationError: If password doesn't meet requirements
        """
        # Validate password
        self.validate_password_strength(password)
        
        try:
            # Generate salt and hash
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt(rounds=self.cost_factor)
            hashed = bcrypt.hashpw(password_bytes, salt)
            
            # Return as string
            hashed_str = hashed.decode('utf-8')
            
            logger.debug("Password hashed successfully")
            return hashed_str
            
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise ValidationError(f"Password hashing failed: {str(e)}")
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify password against bcrypt hash.
        Uses constant-time comparison to prevent timing attacks.
        
        Args:
            password: Plaintext password to verify
            password_hash: Bcrypt hash to compare against
            
        Returns:
            bool: True if password matches, False otherwise
        """
        try:
            password_bytes = password.encode('utf-8')
            hash_bytes = password_hash.encode('utf-8')
            
            result = bcrypt.checkpw(password_bytes, hash_bytes)
            
            if result:
                logger.debug("Password verification successful")
            else:
                logger.debug("Password verification failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def validate_password_strength(self, password: str) -> None:
        """
        Validate password meets security requirements.
        
        Args:
            password: Password to validate
            
        Raises:
            ValidationError: If password doesn't meet requirements
        """
        if not password:
            raise ValidationError("Password is required")
        
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValidationError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
            )
        
        # Check for complexity requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Password must contain uppercase, lowercase, and numbers"
            )
        
        logger.debug("Password meets strength requirements")
    
    def needs_rehash(self, password_hash: str) -> bool:
        """
        Check if password hash needs to be rehashed with current cost factor.
        Used for upgrading hashes when cost factor increases.
        
        Args:
            password_hash: Bcrypt hash to check
            
        Returns:
            bool: True if rehash needed, False otherwise
        """
        try:
            hash_bytes = password_hash.encode('utf-8')
            
            # Extract cost factor from hash
            # Bcrypt hash format: $2b$<cost>$<salt+hash>
            parts = password_hash.split('$')
            if len(parts) >= 3:
                current_cost = int(parts[2])
                return current_cost < self.cost_factor
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking hash cost: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_password_manager = None


def get_password_manager() -> PasswordManager:
    """
    Get global password manager instance.
    
    Returns:
        PasswordManager: Singleton instance
    """
    global _password_manager
    
    if _password_manager is None:
        _password_manager = PasswordManager()
    
    return _password_manager
