"""
RFID Marathon Management System - Base Functions
Security Level: Military-grade
Last Updated: January 21, 2026

This module contains shared utility functions and helpers used across the backend.
All functions are pure, stateless, and reusable.
"""

import re
import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

from constants import (
    PATTERN_EMAIL,
    PATTERN_UUID,
    PATTERN_ALPHANUMERIC,
    RFID_TAG_PATTERN,
    TIMESTAMP_PRECISION,
    ErrorMessages,
)

# Configure logger
logger = logging.getLogger(__name__)


# ============================================================================
# TIMESTAMP UTILITIES
# ============================================================================

def get_current_timestamp_utc() -> datetime:
    """
    Get current UTC timestamp with microsecond precision.
    
    Returns:
        datetime: Current UTC timestamp
    """
    return datetime.now(timezone.utc)


def timestamp_to_iso8601(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string format.
    
    Args:
        dt: Datetime object to convert
        
    Returns:
        str: ISO 8601 formatted string
    """
    return dt.isoformat()


def iso8601_to_timestamp(iso_string: str) -> datetime:
    """
    Convert ISO 8601 string to datetime object.
    
    Args:
        iso_string: ISO 8601 formatted string
        
    Returns:
        datetime: Parsed datetime object
        
    Raises:
        ValueError: If string format is invalid
    """
    try:
        return datetime.fromisoformat(iso_string)
    except ValueError as e:
        logger.error(f"Invalid ISO 8601 format: {iso_string}")
        raise ValueError(f"Invalid timestamp format: {str(e)}")


def timestamp_difference_seconds(start: datetime, end: datetime) -> float:
    """
    Calculate difference between two timestamps in seconds.
    
    Args:
        start: Start timestamp
        end: End timestamp
        
    Returns:
        float: Difference in seconds
    """
    return (end - start).total_seconds()


def is_timestamp_within_window(
    timestamp: datetime, 
    window_seconds: int
) -> bool:
    """
    Check if timestamp is within acceptable window from current time.
    Used for replay attack detection.
    
    Args:
        timestamp: Timestamp to check
        window_seconds: Acceptable window in seconds
        
    Returns:
        bool: True if within window, False otherwise
    """
    current_time = get_current_timestamp_utc()
    difference = abs(timestamp_difference_seconds(timestamp, current_time))
    return difference <= window_seconds


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_email(email: str) -> bool:
    """
    Validate email format using regex pattern.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not email:
        return False
    return bool(re.match(PATTERN_EMAIL, email))


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID format.
    
    Args:
        uuid_string: UUID string to validate
        
    Returns:
        bool: True if valid UUID, False otherwise
    """
    if not uuid_string:
        return False
    return bool(re.match(PATTERN_UUID, uuid_string.lower()))


def validate_rfid_tag(rfid_tag: str) -> bool:
    """
    Validate RFID tag format (hexadecimal).
    
    Args:
        rfid_tag: RFID tag to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not rfid_tag:
        return False
    return bool(re.match(RFID_TAG_PATTERN, rfid_tag))


def validate_alphanumeric(value: str) -> bool:
    """
    Validate that string contains only alphanumeric characters.
    
    Args:
        value: String to validate
        
    Returns:
        bool: True if alphanumeric, False otherwise
    """
    if not value:
        return False
    return bool(re.match(PATTERN_ALPHANUMERIC, value))


def validate_string_length(
    value: str, 
    min_length: int, 
    max_length: int
) -> bool:
    """
    Validate string length is within bounds.
    
    Args:
        value: String to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        
    Returns:
        bool: True if within bounds, False otherwise
    """
    if not value:
        return False
    return min_length <= len(value) <= max_length


# ============================================================================
# CRYPTOGRAPHIC UTILITIES
# ============================================================================

def generate_secure_random_string(length: int = 32) -> str:
    """
    Generate cryptographically secure random string.
    Used for nonces, tokens, and IDs.
    
    Args:
        length: Length of random string
        
    Returns:
        str: Secure random hex string
    """
    return secrets.token_hex(length)


def generate_nonce() -> str:
    """
    Generate a unique nonce for replay attack protection.
    
    Returns:
        str: Unique nonce (64 character hex string)
    """
    return generate_secure_random_string(32)


def generate_uuid() -> str:
    """
    Generate a UUID4.
    
    Returns:
        str: UUID string
    """
    return str(uuid.uuid4())


def hash_data_sha256(data: str) -> str:
    """
    Create SHA-256 hash of data.
    
    Args:
        data: String data to hash
        
    Returns:
        str: Hexadecimal hash string
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_hash_sha256(data: str, hash_value: str) -> bool:
    """
    Verify data matches SHA-256 hash.
    
    Args:
        data: Original data
        hash_value: Expected hash
        
    Returns:
        bool: True if match, False otherwise
    """
    computed_hash = hash_data_sha256(data)
    return secrets.compare_digest(computed_hash, hash_value)


# ============================================================================
# ERROR HANDLING UTILITIES
# ============================================================================

class ApplicationError(Exception):
    """Base exception for application errors"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ApplicationError):
    """Exception for validation failures"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class AuthenticationError(ApplicationError):
    """Exception for authentication failures"""
    
    def __init__(self, message: str = ErrorMessages.INVALID_CREDENTIALS):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationError(ApplicationError):
    """Exception for authorization failures"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )


class NotFoundError(ApplicationError):
    """Exception for resource not found"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": identifier}
        )


class ConflictError(ApplicationError):
    """Exception for resource conflicts"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details
        )


class DatabaseError(ApplicationError):
    """Exception for database errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class EncryptionError(ApplicationError):
    """Exception for encryption/decryption errors"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="ENCRYPTION_ERROR",
            status_code=500
        )


class RateLimitError(ApplicationError):
    """Exception for rate limiting"""
    
    def __init__(self):
        super().__init__(
            message=ErrorMessages.RATE_LIMIT_EXCEEDED,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )


class ReplayAttackError(ApplicationError):
    """Exception for detected replay attacks"""
    
    def __init__(self):
        super().__init__(
            message=ErrorMessages.REPLAY_ATTACK_DETECTED,
            error_code="REPLAY_ATTACK_DETECTED",
            status_code=401
        )


# ============================================================================
# DATA SANITIZATION
# ============================================================================

def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input by removing control characters and trimming.
    
    Args:
        value: String to sanitize
        max_length: Optional maximum length
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
    
    # Remove control characters
    sanitized = "".join(char for char in value if char.isprintable())
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Enforce max length
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def sanitize_dict(
    data: Dict[str, Any], 
    allowed_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Sanitize dictionary by removing disallowed keys and sanitizing values.
    
    Args:
        data: Dictionary to sanitize
        allowed_keys: Optional list of allowed keys
        
    Returns:
        Dict: Sanitized dictionary
    """
    if not data:
        return {}
    
    sanitized = {}
    
    for key, value in data.items():
        # Skip disallowed keys
        if allowed_keys and key not in allowed_keys:
            continue
        
        # Sanitize string values
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        else:
            sanitized[key] = value
    
    return sanitized


# ============================================================================
# FILE UTILITIES
# ============================================================================

def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        directory_path: Path to directory
    """
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def read_file_content(file_path: str) -> str:
    """
    Read entire file content as string.
    
    Args:
        file_path: Path to file
        
    Returns:
        str: File content
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise


def write_file_content(file_path: str, content: str) -> None:
    """
    Write content to file.
    
    Args:
        file_path: Path to file
        content: Content to write
    """
    ensure_directory_exists(str(Path(file_path).parent))
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging (e.g., tokens, passwords).
    
    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to keep visible
        
    Returns:
        str: Masked string
    """
    if not data or len(data) <= visible_chars:
        return "***"
    
    return f"{data[:visible_chars]}{'*' * (len(data) - visible_chars)}"


def log_security_event(
    event_type: str, 
    details: Dict[str, Any], 
    level: str = "WARNING"
) -> None:
    """
    Log security-related events with structured format.
    
    Args:
        event_type: Type of security event
        details: Event details
        level: Log level (INFO, WARNING, ERROR, CRITICAL)
    """
    log_message = f"SECURITY_EVENT: {event_type}"
    
    # Remove sensitive data from details
    safe_details = {
        k: mask_sensitive_data(str(v)) if 'password' in k.lower() or 'token' in k.lower() else v
        for k, v in details.items()
    }
    
    if level == "INFO":
        logger.info(log_message, extra=safe_details)
    elif level == "WARNING":
        logger.warning(log_message, extra=safe_details)
    elif level == "ERROR":
        logger.error(log_message, extra=safe_details)
    elif level == "CRITICAL":
        logger.critical(log_message, extra=safe_details)


# ============================================================================
# RESPONSE FORMATTING
# ============================================================================

def create_success_response(
    data: Any, 
    message: str = "Success"
) -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Dict: Standardized response
    """
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": timestamp_to_iso8601(get_current_timestamp_utc())
    }


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        error_code: Error code identifier
        message: Error message
        details: Optional error details
        
    Returns:
        Dict: Standardized error response
    """
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "details": details or {},
        "timestamp": timestamp_to_iso8601(get_current_timestamp_utc())
    }


# ============================================================================
# ENVIRONMENT UTILITIES
# ============================================================================

def get_env_variable(
    var_name: str, 
    required: bool = True,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Get environment variable with validation.
    
    Args:
        var_name: Environment variable name
        required: Whether variable is required
        default: Default value if not found
        
    Returns:
        Optional[str]: Environment variable value
        
    Raises:
        ValueError: If required variable is missing
    """
    import os, dotenv
    dotenv.load_dotenv()  # Load from .env file if present
    
    value = os.getenv(var_name, default)
    
    if required and not value:
        error_msg = f"Required environment variable missing: {var_name}"
        logger.critical(error_msg)
        raise ValueError(error_msg)
    
    return value


def validate_required_env_vars(required_vars: List[str]) -> None:
    """
    Validate that all required environment variables are present.
    Fail-fast approach for configuration validation.
    
    Args:
        required_vars: List of required environment variable names
        
    Raises:
        ValueError: If any required variable is missing
    """
    missing_vars = []
    
    for var_name in required_vars:
        try:
            get_env_variable(var_name, required=True)
        except ValueError:
            missing_vars.append(var_name)
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.critical(error_msg)
        raise ValueError(error_msg)


# ============================================================================
# TIMING UTILITIES
# ============================================================================

def calculate_race_duration(
    start_time: datetime, 
    end_time: datetime
) -> Dict[str, Union[float, str]]:
    """
    Calculate race duration with formatted output.
    
    Args:
        start_time: Race start timestamp
        end_time: Race end timestamp
        
    Returns:
        Dict: Duration in various formats
    """
    duration_seconds = timestamp_difference_seconds(start_time, end_time)
    
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = duration_seconds % 60
    
    return {
        "total_seconds": round(duration_seconds, TIMESTAMP_PRECISION),
        "formatted": f"{hours:02d}:{minutes:02d}:{seconds:06.3f}",
        "hours": hours,
        "minutes": minutes,
        "seconds": round(seconds, TIMESTAMP_PRECISION)
    }


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration (HH:MM:SS.mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
