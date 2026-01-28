"""
RFID Marathon Management System - Global Constants
Security Level: Military-grade
Last Updated: January 21, 2026

This module contains all system-wide constants used across the backend.
No magic values allowed - everything must be defined here.
"""

from enum import Enum
from typing import Final
import os
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# SECURITY CONSTANTS
# ============================================================================

# JWT Configuration
JWT_ALGORITHM: Final[str] = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 15
JWT_REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7

# Replay Attack Protection
REPLAY_ATTACK_WINDOW_SECONDS: Final[int] = 60  # Requests older than 60s rejected
NONCE_CACHE_SIZE: Final[int] = 10000  # Track last 10k nonces
NONCE_CLEANUP_INTERVAL_SECONDS: Final[int] = 300  # Clean every 5 minutes

# Password Security
PASSWORD_MIN_LENGTH: Final[int] = 12
PASSWORD_BCRYPT_ROUNDS: Final[int] = 12  # Cost factor for bcrypt

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE: Final[int] = 60
RATE_LIMIT_BURST: Final[int] = 10

# Encryption
RSA_KEY_SIZE: Final[int] = 4096  # Bits for RSA key generation
FERNET_KEY_ROTATION_DAYS: Final[int] = 90  # Rotate encryption keys every 90 days
ENCRYPTION_ALGORITHM: Final[str] = "Fernet"  # Symmetric encryption for DB

# RFID Hub Authentication
RFID_HUB_KEY_ENCRYPTION_ALGORITHM: Final[str] = "Fernet"  # Encrypt hub secrets with Fernet
RFID_START_HUB_PORT: Final[int] = 9090  # Dedicated listener port
RFID_END_HUB_PORT: Final[int] = 9090   # Same listener port, validates different keys

# ============================================================================
# DATABASE CONSTANTS
# ============================================================================

# Connection Pool
DB_POOL_SIZE: Final[int] = 20
DB_MAX_OVERFLOW: Final[int] = 10
DB_POOL_TIMEOUT_SECONDS: Final[int] = 30
DB_POOL_RECYCLE_SECONDS: Final[int] = 3600  # Recycle connections every hour

# SSL Configuration
DB_SSL_MODE: Final[str] = "require"  # Enforce SSL for all connections
DB_SSL_MIN_PROTOCOL_VERSION: Final[str] = "TLSv1.2"

# Query Timeouts
DB_QUERY_TIMEOUT_SECONDS: Final[int] = 30
DB_CONNECTION_TIMEOUT_SECONDS: Final[int] = 10

# ============================================================================
# TABLE NAMES
# ============================================================================

TABLE_USERS: Final[str] = "users"
TABLE_RACES: Final[str] = "races"
TABLE_RFID_MAPPING: Final[str] = "rfid_mapping"
TABLE_AUDIT_LOG: Final[str] = "audit_log"
TABLE_NONCE_CACHE: Final[str] = "nonce_cache"
TABLE_ENCRYPTION_KEYS: Final[str] = "encryption_keys"

# ============================================================================
# API CONSTANTS
# ============================================================================

# HTTP Headers
HEADER_AUTHORIZATION: Final[str] = "Authorization"
HEADER_TIMESTAMP: Final[str] = "X-Timestamp"
HEADER_NONCE: Final[str] = "X-Nonce"
HEADER_REQUEST_ID: Final[str] = "X-Request-ID"

# API Versioning
API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

# Response Codes
HTTP_SUCCESS: Final[int] = 200
HTTP_CREATED: Final[int] = 201
HTTP_BAD_REQUEST: Final[int] = 400
HTTP_UNAUTHORIZED: Final[int] = 401
HTTP_FORBIDDEN: Final[int] = 403
HTTP_NOT_FOUND: Final[int] = 404
HTTP_CONFLICT: Final[int] = 409
HTTP_TOO_MANY_REQUESTS: Final[int] = 429
HTTP_INTERNAL_ERROR: Final[int] = 500

# ============================================================================
# RFID LISTENER CONSTANTS
# ============================================================================

# RFID Listener Service (Port 9090)
RFID_LISTENER_PORT: Final[int] = 9090
RFID_LISTENER_HOST: Final[str] = "0.0.0.0"

# Grace period for late arrivals (seconds) - candidates can still be added during this window
RFID_GRACE_PERIOD_SECONDS: Final[int] = int(os.getenv("RFID_GRACE_PERIOD_SECONDS", 120)) # Default 2 minutes

# Minimum read count to be considered a valid candidate
RFID_MIN_READ_COUNT_TO_LOCK: Final[int] = int(os.getenv("RFID_MIN_READ_COUNT_TO_LOCK", 3))

# No-hit timeout to lock remaining unlocked candidates (seconds)
RFID_NO_HIT_TIMEOUT_SECONDS: Final[int] = int(os.getenv("RFID_NO_HIT_TIMEOUT_SECONDS", 20))

# Reader name mapping (configure which readers are start/end)
# By default: readers with "start" or "Reader 1" in name are start readers
#             readers with "end" or "Reader 2" in name are end readers
RFID_START_READER_NAMES: Final[list] = ["Reader 1", "start", "Start"] + os.getenv("RFID_START_READER_NAMES", "").split(",")
RFID_END_READER_NAMES: Final[list] = ["Reader 2", "end", "End"] + os.getenv("RFID_END_READER_NAMES", "").split(",")

# ============================================================================
# RACE STATE CONSTANTS (BACKEND ONLY)
# ============================================================================

# Race state persistence - BACKEND ONLY, NOT used by listener (9090)
# The listener is now stateless and forwards all RFID hits directly to backend
# Backend manages all race state (groups, grace periods, locking) via this file
RACE_STATE_FILE: Final[str] = "race_state.json"  # Relative to backend root
RACE_STATE_DEDUPLICATION: Final[bool] = True  # Prevent duplicate RFIDs in same group

# ============================================================================
# TIMING CONSTANTS
# ============================================================================

# Timestamp precision (milliseconds)
TIMESTAMP_PRECISION: Final[int] = 3

# ============================================================================
# RACE CONSTANTS
# ============================================================================

class RaceStatus(str, Enum):
    """Enumeration of race statuses"""
    CREATED = "created"           # Race created, not started
    ACTIVE = "active"             # Race is currently active (only one can be active at a time)
    STARTED = "started"           # Race started by admin, participants are running (deprecated, use ACTIVE)
    ENDED = "ended"               # Race ended, all participants finished
    COMPLETED = "completed"       # Race completed, all participants finished
    
# Race distance limits (meters)
RACE_MIN_DISTANCE_METERS: Final[int] = 10
RACE_MAX_DISTANCE_METERS: Final[int] = 100000  # 100km max

# ============================================================================
# PARTICIPANT CONSTANTS
# ============================================================================

# Name validation
PARTICIPANT_NAME_MIN_LENGTH: Final[int] = 2
PARTICIPANT_NAME_MAX_LENGTH: Final[int] = 100

# RFID tag validation
RFID_TAG_MIN_LENGTH: Final[int] = 8
RFID_TAG_MAX_LENGTH: Final[int] = 32
RFID_TAG_PATTERN: Final[str] = r"^[A-Fa-f0-9]+$"  # Hexadecimal only

# ============================================================================
# AUDIT LOG CONSTANTS
# ============================================================================

class AuditAction(str, Enum):
    """Enumeration of auditable actions"""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    TOKEN_REFRESH = "token_refresh"
    LOGOUT = "logout"
    
    # Race Management
    RACE_CREATE = "race_create"
    RACE_UPDATE = "race_update"
    RACE_DELETE = "race_delete"
    RACE_START = "race_start"
    RACE_COMPLETE = "race_complete"
    
    # Participant Management
    PARTICIPANT_REGISTER = "participant_register"
    PARTICIPANT_LOOKUP = "participant_lookup"
    
    # Timing Operations
    TIMING_START_RECORD = "timing_start_record"
    TIMING_END_RECORD = "timing_end_record"
    TIMING_SYNC_CONFIRM = "timing_sync_confirm"
    
    # Security Events
    REPLAY_ATTACK_DETECTED = "replay_attack_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    ENCRYPTION_ERROR = "encryption_error"
    
    # System Events
    DB_CONNECTION_ERROR = "db_connection_error"
    MIGRATION_EXECUTED = "migration_executed"

# Audit retention (days)
AUDIT_LOG_RETENTION_DAYS: Final[int] = 365  # Keep logs for 1 year

# ============================================================================
# ERROR MESSAGES
# ============================================================================

class ErrorMessages:
    """Centralized error messages for consistency"""
    
    # Authentication Errors
    INVALID_CREDENTIALS = "Invalid username or password"
    TOKEN_EXPIRED = "Access token has expired"
    TOKEN_INVALID = "Invalid or malformed token"
    MISSING_AUTH_HEADER = "Authorization header is required"
    
    # Replay Attack Errors
    REPLAY_ATTACK_DETECTED = "Request timestamp outside acceptable window or nonce reused"
    MISSING_TIMESTAMP = "X-Timestamp header is required"
    MISSING_NONCE = "X-Nonce header is required"
    
    # Database Errors
    DB_CONNECTION_FAILED = "Failed to connect to database"
    DB_QUERY_TIMEOUT = "Database query timed out"
    DB_CONSTRAINT_VIOLATION = "Database constraint violated"
    
    # Race Errors
    RACE_NOT_FOUND = "Race not found"
    RACE_ALREADY_STARTED = "Race has already started"
    RACE_NOT_STARTED = "Race has not started yet"
    
    # Participant Errors
    PARTICIPANT_NOT_FOUND = "Participant not found"
    RFID_ALREADY_REGISTERED = "RFID tag already registered for this race"
    INVALID_RFID_FORMAT = "Invalid RFID tag format"
    
    # Timing Errors
    TIMING_ALREADY_RECORDED = "Timing record already exists and is immutable"
    INVALID_TIMING_POINT = "Invalid timing point (must be 'start' or 'end')"
    START_TIME_MISSING = "Start time must be recorded before end time"
    
    # Encryption Errors
    ENCRYPTION_FAILED = "Failed to encrypt data"
    DECRYPTION_FAILED = "Failed to decrypt data"
    KEY_NOT_FOUND = "Encryption key not found"
    
    # Validation Errors
    INVALID_INPUT = "Invalid input data"
    MISSING_REQUIRED_FIELD = "Required field is missing"
    FIELD_TOO_SHORT = "Field value is too short"
    FIELD_TOO_LONG = "Field value is too long"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "Too many requests. Please slow down."
    
    # Generic Errors
    INTERNAL_SERVER_ERROR = "An internal server error occurred"
    SERVICE_UNAVAILABLE = "Service temporarily unavailable"

# ============================================================================
# ENVIRONMENT VARIABLE NAMES
# ============================================================================

class EnvVars:
    """Environment variable names - used for configuration loading"""
    
    # Database
    DB_HOST = "DB_HOST"
    DB_PORT = "DB_PORT"
    DB_NAME = "DB_NAME"
    DB_USER = "DB_USER"
    DB_PASSWORD = "DB_PASSWORD"
    
    # Security
    JWT_SECRET_KEY = "JWT_SECRET_KEY"
    FERNET_MASTER_KEY = "FERNET_MASTER_KEY"
    RSA_PRIVATE_KEY_PATH = "RSA_PRIVATE_KEY_PATH"
    RSA_PUBLIC_KEY_PATH = "RSA_PUBLIC_KEY_PATH"
    
    # RFID Hub Secrets (plaintext)
    RFID_START_HUB_SECRET = "RFID_START_HUB_SECRET"
    RFID_END_HUB_SECRET = "RFID_END_HUB_SECRET"
    
    # Server
    SERVER_HOST = "SERVER_HOST"
    SERVER_PORT = "SERVER_PORT"
    SERVER_ENV = "SERVER_ENV"  # development, production
    
    # SSL/TLS
    SSL_CERT_PATH = "SSL_CERT_PATH"
    SSL_KEY_PATH = "SSL_KEY_PATH"
    
    # Logging
    LOG_LEVEL = "LOG_LEVEL"
    LOG_FILE_PATH = "LOG_FILE_PATH"

# ============================================================================
# VALIDATION PATTERNS
# ============================================================================

# Regex patterns for validation
PATTERN_EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
PATTERN_UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
PATTERN_ALPHANUMERIC = r"^[a-zA-Z0-9]+$"

# ============================================================================
# SYSTEM METADATA
# ============================================================================

SYSTEM_NAME: Final[str] = "RFID Marathon Management System"
SYSTEM_VERSION: Final[str] = "1.0.0"
SYSTEM_ENV: Final[str] = "production"  # Default to production for safety
SECURITY_LEVEL: Final[str] = "military-grade"

# ============================================================================
# FEATURE FLAGS
# ============================================================================

class FeatureFlags:
    """Feature flags for gradual rollout or emergency disable"""
    
    ENABLE_RATE_LIMITING: Final[bool] = True
    ENABLE_AUDIT_LOGGING: Final[bool] = True
    ENABLE_REPLAY_PROTECTION: Final[bool] = True
    ENABLE_ENCRYPTION: Final[bool] = True
    ENFORCE_HTTPS: Final[bool] = True
    ALLOW_TIMING_UPDATES: Final[bool] = False  # Immutable by default
