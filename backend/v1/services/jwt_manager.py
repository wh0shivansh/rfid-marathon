"""
RFID Marathon Management System - JWT Manager
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles JWT token generation and validation with:
- Timestamp-based replay attack detection
- Nonce tracking
- Short-lived access tokens
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from sqlalchemy.orm import Session

from constants import (
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    REPLAY_ATTACK_WINDOW_SECONDS,
    EnvVars,
)
from basefunctions import (
    get_env_variable,
    get_current_timestamp_utc,
    iso8601_to_timestamp,
    is_timestamp_within_window,
    generate_nonce,
    AuthenticationError,
    ReplayAttackError,
    log_security_event,
)
from models import NonceCache

logger = logging.getLogger(__name__)


class JWTManager:
    """
    Manages JWT token creation and validation with replay attack protection.
    """
    
    def __init__(self):
        """Initialize JWT manager with secret key from environment"""
        secret = get_env_variable(EnvVars.JWT_SECRET_KEY, required=True)
        if secret is None:
            raise AuthenticationError("JWT secret key is not set")
        self.secret_key: str = secret
        self.algorithm = JWT_ALGORITHM
        logger.info(f"✓ JWT manager initialized (algorithm: {self.algorithm})")
    
    def create_access_token(
        self, 
        user_id: str, 
        username: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User ID to embed in token
            username: Username to embed in token
            additional_claims: Optional additional claims
            
        Returns:
            str: JWT token
        """
        now = get_current_timestamp_utc()
        expiry = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": user_id,  # Subject (user ID)
            "username": username,
            "iat": int(now.timestamp()),  # Issued at
            "exp": int(expiry.timestamp()),  # Expiration
            "type": "access"
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm) # type: ignore
            logger.debug(f"Created access token for user: {username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise AuthenticationError("Failed to create access token")
    
    def create_refresh_token(self, user_id: str, username: str) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User ID to embed in token
            username: Username to embed in token
            
        Returns:
            str: JWT refresh token
        """
        now = get_current_timestamp_utc()
        expiry = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": user_id,
            "username": username,
            "iat": int(now.timestamp()),
            "exp": int(expiry.timestamp()),
            "type": "refresh"
        }
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm) # type: ignore
            logger.debug(f"Created refresh token for user: {username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise AuthenticationError("Failed to create refresh token")
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Dict: Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode( # type: ignore
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            logger.debug(f"Token decoded successfully for user: {payload.get('username')}")
            return payload
            
        except jwt.ExpiredSignatureError: # type: ignore
            logger.warning("Token has expired")
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e: # type: ignore
            logger.warning(f"Invalid token: {e}")
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"Token decoding failed: {e}")
            raise AuthenticationError("Token decoding failed")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and return payload.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dict: Token payload if valid
            
        Raises:
            AuthenticationError: If token is invalid
        """
        payload = self.decode_token(token)
        
        # Additional validation can be added here
        # e.g., check if user still exists, check permissions, etc.
        
        return payload
    
    def extract_user_id(self, token: str) -> str:
        """
        Extract user ID from JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            str: User ID
            
        Raises:
            AuthenticationError: If token is invalid
        """
        payload = self.decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Token does not contain user ID")
        
        return user_id
    
    def validate_replay_attack_protection(
        self,
        timestamp_str: str,
        nonce: str,
        db: Session
    ) -> None:
        """
        Validate timestamp and nonce to prevent replay attacks.
        
        Args:
            timestamp_str: ISO 8601 timestamp from request header
            nonce: Unique nonce from request header
            db: Database session for nonce tracking
            
        Raises:
            ReplayAttackError: If replay attack is detected
        """
        # Validate timestamp format
        try:
            request_timestamp = iso8601_to_timestamp(timestamp_str)
        except ValueError:
            logger.warning(f"Invalid timestamp format: {timestamp_str}")
            raise ReplayAttackError()
        
        # Check if timestamp is within acceptable window
        if not is_timestamp_within_window(request_timestamp, REPLAY_ATTACK_WINDOW_SECONDS):
            logger.warning(f"Request timestamp outside acceptable window: {timestamp_str}")
            log_security_event(
                "REPLAY_ATTACK_TIMESTAMP",
                {
                    "timestamp": timestamp_str,
                    "window_seconds": REPLAY_ATTACK_WINDOW_SECONDS
                },
                level="WARNING"
            )
            raise ReplayAttackError()
        
        # Check if nonce has been used before
        existing_nonce = db.query(NonceCache).filter_by(nonce=nonce).first()
        
        if existing_nonce:
            logger.warning(f"Nonce reuse detected: {nonce[:10]}...")
            log_security_event(
                "REPLAY_ATTACK_NONCE",
                {"nonce": nonce[:10] + "..."},
                level="WARNING"
            )
            raise ReplayAttackError()
        
        # Store nonce in cache
        current_time = get_current_timestamp_utc()
        expiry_time = current_time + timedelta(seconds=REPLAY_ATTACK_WINDOW_SECONDS)
        
        nonce_entry = NonceCache(
            nonce=nonce,
            timestamp=request_timestamp,
            expires_at=expiry_time
        )
        
        db.add(nonce_entry)
        db.commit()
        
        logger.debug("Replay attack validation passed")
    
    def cleanup_expired_nonces(self, db: Session) -> int:
        """
        Clean up expired nonces from cache.
        Should be called periodically.
        
        Args:
            db: Database session
            
        Returns:
            int: Number of nonces cleaned up
        """
        current_time = get_current_timestamp_utc()
        
        deleted_count = db.query(NonceCache).filter(
            NonceCache.expires_at < current_time
        ).delete()
        
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired nonces")
        
        return deleted_count


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_jwt_manager = None


def get_jwt_manager() -> JWTManager:
    """
    Get global JWT manager instance.
    
    Returns:
        JWTManager: Singleton instance
    """
    global _jwt_manager
    
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    
    return _jwt_manager
