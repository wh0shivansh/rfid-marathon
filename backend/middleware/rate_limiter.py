"""
RFID Marathon Management System - Rate Limiter Middleware
Security Level: Military-grade
Last Updated: January 21, 2026

This middleware implements rate limiting to prevent DOS attacks.
"""

import logging
import time
from typing import Dict
from collections import deque
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status

from constants import RATE_LIMIT_REQUESTS_PER_MINUTE, RATE_LIMIT_BURST
from basefunctions import RateLimitError, log_security_event

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with per-IP tracking.
    """
    
    def __init__(
        self,
        requests_per_minute: int = RATE_LIMIT_REQUESTS_PER_MINUTE,
        burst: int = RATE_LIMIT_BURST
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            burst: Maximum burst size
        """
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.request_history: Dict[str, deque] = {}
        self.window_seconds = 60
        
        logger.info(
            f"✓ Rate limiter initialized "
            f"({requests_per_minute} req/min, burst={burst})"
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request
            
        Returns:
            str: Client IP address
        """
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Use first IP in chain
            return forwarded_for.split(",")[0].strip()
        
        # Use direct IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _cleanup_old_requests(self, ip: str) -> None:
        """
        Remove requests older than the window.
        
        Args:
            ip: Client IP address
        """
        if ip not in self.request_history:
            return
        
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        # Remove old requests
        while (
            self.request_history[ip] and
            self.request_history[ip][0] < cutoff_time
        ):
            self.request_history[ip].popleft()
        
        # Remove IP if no recent requests
        if not self.request_history[ip]:
            del self.request_history[ip]
    
    def is_allowed(self, request: Request) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            request: FastAPI request
            
        Returns:
            bool: True if allowed, False if rate limited
        """
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Cleanup old requests first (may remove stale keys)
        self._cleanup_old_requests(ip)

        # Initialize history for new IP (after cleanup)
        if ip not in self.request_history:
            self.request_history[ip] = deque()
        
        # Check rate limit
        request_count = len(self.request_history[ip])
        
        if request_count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            log_security_event(
                "RATE_LIMIT_EXCEEDED",
                {
                    "ip": ip,
                    "request_count": request_count,
                    "limit": self.requests_per_minute
                },
                level="WARNING"
            )
            return False
        
        # Check burst limit
        if request_count >= self.burst:
            # Check if requests are too close together
            recent_window = 5  # seconds
            recent_cutoff = current_time - recent_window
            recent_count = sum(1 for t in self.request_history[ip] if t > recent_cutoff)
            
            if recent_count >= self.burst:
                logger.warning(f"Burst limit exceeded for IP: {ip}")
                return False
        
        # Record this request
        self.request_history[ip].append(current_time)
        
        return True
    
    async def __call__(self, request: Request) -> None:
        """
        Middleware call method for FastAPI.
        
        Args:
            request: FastAPI request
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.is_allowed(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": "60"}
            )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance.
    
    Returns:
        RateLimiter: Singleton instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    
    return _rate_limiter
