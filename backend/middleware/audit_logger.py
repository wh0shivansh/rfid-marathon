"""
RFID Marathon Management System - Audit Logger Middleware
Security Level: Military-grade
Last Updated: January 21, 2026

This middleware logs all API requests to immutable audit log.
"""

import logging
from typing import Optional, Any

from fastapi import Request, Response
from sqlalchemy.orm import Session

from models import AuditLog, AuditAction
from basefunctions import get_current_timestamp_utc
from database.connection import get_database_manager

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logging middleware for all API requests.
    """
    
    def __init__(self):
        self.db_manager = get_database_manager()
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request
            
        Returns:
            str: Client IP address
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_id_from_request(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request state (set by auth middleware).
        
        Args:
            request: FastAPI request
            
        Returns:
            Optional[str]: User ID if authenticated, None otherwise
        """
        # Check if user info was set by auth middleware
        if hasattr(request.state, "user"):
            return request.state.user.get("sub")
        
        return None
    
    def _map_route_to_action(self, method: str, path: str) -> str:
        """
        Map HTTP method and path to audit action.
        
        Args:
            method: HTTP method
            path: Request path
            
        Returns:
            str: Audit action
        """
        # Map common routes to audit actions
        route_mapping = {
            ("POST", "/auth/login"): AuditAction.LOGIN_SUCCESS.value,
            ("POST", "/participant/register"): AuditAction.PARTICIPANT_REGISTER.value,
            ("POST", "/participant/lookup"): AuditAction.PARTICIPANT_LOOKUP.value,
            ("POST", "/timing/start"): AuditAction.TIMING_START_RECORD.value,
            ("POST", "/timing/end"): AuditAction.TIMING_END_RECORD.value,
            ("POST", "/sync/handshake"): AuditAction.TIMING_SYNC_CONFIRM.value,
            ("POST", "/race"): AuditAction.RACE_CREATE.value,
        }
        
        key = (method, path)
        return route_mapping.get(key, f"{method}_{path}")
    
    async def log_request(
        self,
        request: Request,
        response: Response,
        processing_time: float
    ) -> None:
        """
        Log API request to audit table.
        
        Args:
            request: FastAPI request
            response: FastAPI response
            processing_time: Request processing time in seconds
        """
        try:
            ip_address = self._get_client_ip(request)
            user_id = self._get_user_id_from_request(request)
            action = self._map_route_to_action(request.method, request.url.path)
            
            # Determine success based on status code
            success = 200 <= response.status_code < 400
            
            # Create audit log entry
            with self.db_manager.session_scope() as db:
                audit_entry = AuditLog(
                    action=action,
                    user_id=user_id,
                    ip_address=ip_address,
                    timestamp=get_current_timestamp_utc(),
                    request_path=str(request.url.path),
                    request_method=request.method,
                    status_code=response.status_code,
                    details={
                        "processing_time_ms": round(processing_time * 1000, 2),
                        "user_agent": request.headers.get("User-Agent", "unknown")
                    },
                    success=success
                )
                
                db.add(audit_entry)
            
            logger.debug(
                f"Audit logged: {action} - {ip_address} - "
                f"{response.status_code} ({processing_time*1000:.2f}ms)"
            )
            
        except Exception as e:
            # Don't fail request if audit logging fails
            logger.error(f"Failed to write audit log: {e}")
    
    async def log_security_event(
        self,
        action: str,
        request: Request,
        success: bool,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Log security-specific event.
        
        Args:
            action: Security action
            request: FastAPI request
            success: Whether event was successful
            details: Additional details
        """
        try:
            ip_address = self._get_client_ip(request)
            user_id = self._get_user_id_from_request(request)
            
            with self.db_manager.session_scope() as db:
                audit_entry = AuditLog(
                    action=action,
                    user_id=user_id,
                    ip_address=ip_address,
                    timestamp=get_current_timestamp_utc(),
                    request_path=str(request.url.path) if request else None,
                    request_method=request.method if request else None,
                    status_code=401 if not success else 200,
                    details=details or {},
                    success=success
                )
                
                db.add(audit_entry)
            
            logger.info(f"Security event logged: {action}")
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """
    Get global audit logger instance.
    
    Returns:
        AuditLogger: Singleton instance
    """
    global _audit_logger
    
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    
    return _audit_logger
