"""
RFID Marathon Management System - Authentication Middleware
Security Level: Military-grade
Last Updated: January 21, 2026

This middleware handles JWT token validation for protected routes.
"""

import logging
from typing import Optional

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from constants import HEADER_AUTHORIZATION, HEADER_TIMESTAMP, HEADER_NONCE
from basefunctions import AuthenticationError, ReplayAttackError
from services.jwt_manager import get_jwt_manager
from database.connection import get_database_manager

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer()


class AuthMiddleware:
    """
    Authentication middleware for FastAPI.
    """
    
    def __init__(self):
        self.jwt_manager = get_jwt_manager()
        self.db_manager = get_database_manager()
    
    async def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials
    ) -> dict:
        """
        Validate JWT token from Authorization header.
        
        Args:
            request: FastAPI request
            credentials: Authorization credentials
            
        Returns:
            dict: Decoded token payload
            
        Raises:
            HTTPException: If authentication fails
        """
        token = credentials.credentials
        
        try:
            # Validate and decode token
            payload = self.jwt_manager.validate_token(token)
            
            logger.debug(f"Authenticated user: {payload.get('username')}")
            return payload
            
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=e.message,
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def validate_replay_protection(
        self,
        request: Request,
        db: Session
    ) -> None:
        """
        Validate replay attack protection headers.
        
        Args:
            request: FastAPI request
            db: Database session
            
        Raises:
            HTTPException: If replay attack is detected
        """
        timestamp = request.headers.get(HEADER_TIMESTAMP)
        nonce = request.headers.get(HEADER_NONCE)
        
        if not timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Timestamp header is required"
            )
        
        if not nonce:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Nonce header is required"
            )
        
        try:
            self.jwt_manager.validate_replay_attack_protection(
                timestamp,
                nonce,
                db
            )
            
        except ReplayAttackError as e:
            logger.warning(f"Replay attack detected: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=e.message
            )


# ============================================================================
# DEPENDENCY FUNCTIONS FOR FASTAPI
# ============================================================================

_auth_middleware = None


def get_auth_middleware() -> AuthMiddleware:
    """
    Get global auth middleware instance.
    
    Returns:
        AuthMiddleware: Singleton instance
    """
    global _auth_middleware
    
    if _auth_middleware is None:
        _auth_middleware = AuthMiddleware()
    
    return _auth_middleware


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        dict: User payload from token
        
    Example:
        @app.get("/protected")
        async def protected_route(user = Depends(get_current_user)):
            return {"user_id": user["sub"]}
    """
    auth_middleware = get_auth_middleware()
    
    # Create a fake request object (not ideal, but works for token validation)
    # In production, this would be integrated into FastAPI middleware
    from fastapi import Request
    request = Request(scope={"type": "http", "headers": []})
    
    return await auth_middleware(request, credentials)
