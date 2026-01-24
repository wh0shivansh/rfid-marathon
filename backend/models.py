"""
RFID Marathon Management System - Data Models
Security Level: Military-grade
Last Updated: January 21, 2026

This module contains all Pydantic schemas and SQLAlchemy database models.
Strict validation and type safety enforced.
"""

from datetime import datetime
from typing import Optional, List, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, EmailStr, field_serializer
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Float, 
    Text, ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from constants import (
    PARTICIPANT_NAME_MIN_LENGTH,
    PARTICIPANT_NAME_MAX_LENGTH,
    RFID_TAG_MIN_LENGTH,
    RFID_TAG_MAX_LENGTH,
    RaceStatus,
)
from basefunctions import validate_rfid_tag, generate_uuid

# SQLAlchemy Base
Base = declarative_base()


# ============================================================================
# PYDANTIC SCHEMAS (API REQUEST/RESPONSE)
# ============================================================================

# ---------------------------------------------------------------------------
# Authentication Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Login request schema"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12, max_length=128)
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    nonce: str = Field(..., min_length=32, max_length=128)


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    user_id: str


class TokenRefreshRequest(BaseModel):
    """Token refresh request schema"""
    refresh_token: str
    timestamp: str
    nonce: str


# ---------------------------------------------------------------------------
# Race Schemas
# ---------------------------------------------------------------------------

class RaceCreateRequest(BaseModel):
    """Create race request schema"""
    name: str = Field(..., min_length=3, max_length=200)
    distance_meters: int = Field(..., ge=10, le=100000)
    location: str = Field(..., min_length=3, max_length=200)
    scheduled_date: str = Field(..., description="ISO 8601 date")
    description: Optional[str] = Field(None, max_length=1000)
    # Age category qualifying times (in seconds) - defaults are in minutes converted to seconds
    age_upto30_excellent: float = Field(1500, ge=0)  # 25 min = 1500 sec
    age_upto30_good: float = Field(1578, ge=0)  # 26.30 min = 1578 sec
    age_upto30_satisfactory: float = Field(1620, ge=0)  # 27 min = 1620 sec
    age_upto40_excellent: float = Field(1698, ge=0)  # 28.30 min = 1698 sec
    age_upto40_good: float = Field(1800, ge=0)  # 30 min = 1800 sec
    age_upto40_satisfactory: float = Field(1860, ge=0)  # 31 min = 1860 sec
    age_40to45_excellent: float = Field(1878, ge=0)  # 31.30 min = 1878 sec
    age_40to45_good: float = Field(1980, ge=0)  # 33 min = 1980 sec
    age_40to45_satisfactory: float = Field(2100, ge=0)  # 35 min = 2100 sec


class RaceUpdateRequest(BaseModel):
    """Update race request schema"""
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    distance_meters: Optional[int] = Field(None, ge=10, le=100000)
    location: Optional[str] = Field(None, min_length=3, max_length=200)
    scheduled_date: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[RaceStatus] = None


class RaceResponse(BaseModel):
    """Race response schema"""
    id: str
    name: str
    distance_meters: int
    location: str
    scheduled_date: datetime
    description: Optional[str]
    status: RaceStatus
    created_at: datetime
    updated_at: datetime
    table_name: str
    participant_count: int = 0
    # Age category qualifying times (in seconds)
    age_upto30_excellent: float = 1500
    age_upto30_good: float = 1578
    age_upto30_satisfactory: float = 1620
    age_upto40_excellent: float = 1698
    age_upto40_good: float = 1800
    age_upto40_satisfactory: float = 1860
    age_40to45_excellent: float = 1878
    age_40to45_good: float = 1980
    age_40to45_satisfactory: float = 2100

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class DashboardDataResponse(BaseModel):
    """Dashboard statistics response schema"""
    total_races: int = Field(..., description="Total number of races")
    total_participants: int = Field(..., description="Total participants across all races")
    today_registrations: int = Field(..., description="Participants registered today")
    started_today: int = Field(..., description="Participants who started races scheduled for today")
    finished_today: int = Field(..., description="Participants who finished races scheduled for today")
    race_stats: dict = Field(default_factory=dict, description="Participant count per race ID")

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Participant Schemas
# ---------------------------------------------------------------------------

class ParticipantRegisterRequest(BaseModel):
    """Register participant request schema"""
    race_id: str
    rfid_tag: str = Field(..., min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH)
    name: str = Field(..., min_length=PARTICIPANT_NAME_MIN_LENGTH, max_length=PARTICIPANT_NAME_MAX_LENGTH)
    age: Optional[int] = Field(None, ge=5, le=120)
    gender: Optional[str] = Field(None, pattern="^(M|F|O)$")
    category: Optional[str] = Field(None, max_length=50)

    @validator('rfid_tag')
    def validate_rfid_format(cls, v):
        if not validate_rfid_tag(v):
            raise ValueError('Invalid RFID tag format. Must be hexadecimal.')
        return v.upper()


class ParticipantLookupRequest(BaseModel):
    """Lookup participant by RFID tag request schema"""
    race_id: str
    rfid_tag: str = Field(..., min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH)

    @validator('rfid_tag')
    def validate_rfid_format(cls, v):
        if not validate_rfid_tag(v):
            raise ValueError('Invalid RFID tag format. Must be hexadecimal.')
        return v.upper()


class ParticipantResponse(BaseModel):
    """Participant response schema (encrypted name)"""
    id: str
    race_id: str
    rfid_tag: str
    encrypted_name: str  # RSA encrypted, base64 encoded
    encryption_key: Optional[str] = None
    age: Optional[int]
    gender: Optional[str]
    category: Optional[str]
    registered_at: str

    class Config:
        from_attributes = True

# ---------------------------------------------------------------------------
# RFID Hub Schemas
# ---------------------------------------------------------------------------

class RFIDHitRequest(BaseModel):
    """
    Unified RFID hit request for both START and END line hubs.
    
    Supports legacy format (rfid_tag only) and new format with reader_name/timing_point.
    """
    rfid: Optional[str] = Field(None, min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH, description="RFID tag (alternative to rfid_tag)")
    rfid_tag: Optional[str] = Field(None, min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH, description="RFID tag identifier")
    reader_name: Optional[str] = Field(None, description="Reader identifier: 'Reader 1' (start) or 'Reader 2' (end)")
    timing_point: Optional[str] = Field(None, description="'start' or 'end' - Derived from reader_name if not explicitly set")
    hit_timestamp: Optional[str] = Field(None, description="ISO timestamp when RFID was detected by proxy/listener (for accurate timing)")
    encrypted_key: Optional[str] = Field(None, min_length=1, description="Encrypted hub secret (legacy)")
    antenna: Optional[int] = Field(None, description="Antenna number")
    read_count: Optional[int] = Field(None, description="Number of reads")
    signal_strength: Optional[int] = Field(None, description="RSSI signal strength")
    first_seen: Optional[int] = Field(None, description="First detection timestamp")
    last_seen: Optional[int] = Field(None, description="Last detection timestamp")
    bank_data: Optional[str] = Field(None, description="Bank data")
    protocol: Optional[str] = Field(None, description="Protocol used")
    
    @validator('rfid_tag', pre=True, always=True)
    def normalize_rfid(cls, v, values):
        """
        Normalize RFID field - accept both 'rfid' and 'rfid_tag', ensure uppercase.
        If rfid_tag is not provided, use rfid field.
        """
        # Use rfid_tag if provided, otherwise fall back to rfid field
        rfid_value = v or values.get('rfid')
        if not rfid_value:
            raise ValueError('Either rfid or rfid_tag must be provided')
        
        rfid_upper = str(rfid_value).upper()
        
        if not validate_rfid_tag(rfid_upper):
            raise ValueError('Invalid RFID tag format. Must be hexadecimal.')
        
        return rfid_upper
    
    @validator('timing_point', pre=True, always=True)
    def derive_timing_point(cls, v, values):
        """Derive timing_point from reader_name if not explicitly provided"""
        if v:
            return str(v).lower()
        
        reader_name = str(values.get('reader_name', '')).lower() if values.get('reader_name') else ''
        if 'reader 2' in reader_name or 'reader2' in reader_name or reader_name == 'end':
            return 'end'
        elif 'reader 1' in reader_name or 'reader1' in reader_name or reader_name == 'start':
            return 'start'
        
        return 'start'  # Default to start


class RFIDHitResponse(BaseModel):
    """Response to RFID hit"""
    success: bool
    message: str
    rfid_tag: Optional[str] = None


class RaceGroupStartRequest(BaseModel):
    """Request to start a race group (assign start times)"""
    race_id: str = Field(..., description="Race identifier")
    group_number: int = Field(..., ge=1, description="Group number to start")


class RaceGroupStartResponse(BaseModel):
    """Response when group is started"""
    success: bool
    message: str
    race_id: str
    group_number: int
    rfids_started: int = 0
    start_time_assigned: Optional[str] = None


# ---------------------------------------------------------------------------
# Results Schemas
# ---------------------------------------------------------------------------

class ParticipantResultResponse(BaseModel):
    """Individual participant result schema"""
    participant_id: str
    rfid_tag: str
    encrypted_name: str  # RSA encrypted
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    duration_formatted: Optional[str]
    status: str  # 'registered', 'grace', 'started', 'finished', 'dnf'

    class Config:
        from_attributes = True


class RaceResultsResponse(BaseModel):
    """Complete race results schema"""
    race_id: str
    race_name: str
    results: List[ParticipantResultResponse]
    total_participants: int
    started_count: int
    finished_count: int


# ============================================================================
# SQLALCHEMY DATABASE MODELS
# ============================================================================

# ---------------------------------------------------------------------------
# User Model
# ---------------------------------------------------------------------------

class User(Base):
    """User table for authentication"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)  # bcrypt hash
    email = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_users_username', 'username'),
    )


# ---------------------------------------------------------------------------
# Race Model
# ---------------------------------------------------------------------------

class Race(Base):
    """Different Race table"""
    __tablename__ = "races"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    distance_meters = Column(Integer, nullable=False)
    location = Column(String(200), nullable=False)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default=RaceStatus.CREATED.value, nullable=False)
    table_name = Column(String(128), nullable=False, unique=True)  # Maps to participants table for this race
    # Age category qualifying times (in seconds) - defaults match standard race times
    age_upto30_excellent = Column(Float, nullable=False, default=1500)  # 25 min
    age_upto30_good = Column(Float, nullable=False, default=1578)  # 26.30 min
    age_upto30_satisfactory = Column(Float, nullable=False, default=1620)  # 27 min
    age_upto40_excellent = Column(Float, nullable=False, default=1698)  # 28.30 min
    age_upto40_good = Column(Float, nullable=False, default=1800)  # 30 min
    age_upto40_satisfactory = Column(Float, nullable=False, default=1860)  # 31 min
    age_40to45_excellent = Column(Float, nullable=False, default=1878)  # 31.30 min
    age_40to45_good = Column(Float, nullable=False, default=1980)  # 33 min
    age_40to45_satisfactory = Column(Float, nullable=False, default=2100)  # 35 min
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        CheckConstraint('distance_meters >= 10 AND distance_meters <= 100000', name='check_race_distance'),
        CheckConstraint("status IN ('created', 'started')", name='check_race_status'),
        Index('idx_races_status', 'status'),
        Index('idx_races_scheduled_date', 'scheduled_date'),
    )


# ---------------------------------------------------------------------------
# Participant Model (Template - NOT created in migrations)
# ---------------------------------------------------------------------------

class Participant(Base):
    """
    Participant table template - per-race tables created dynamically.
    This model is NOT created during migrations but serves as a template
    for dynamically created per-race participant tables.
    """
    __tablename__ = "FiveKmRaceParticipants"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    race_id = Column(UUID(as_uuid=False), ForeignKey('races.id', ondelete='CASCADE'), nullable=False, index=True)
    rfid_tag = Column(String(32), nullable=False, index=True)  # PLAINTEXT (requirement)
    encrypted_name = Column(Text, nullable=False)  # Fernet encrypted
    age = Column(Integer, nullable=True)
    gender = Column(String(1), nullable=True)
    category = Column(String(50), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    encryption_key_id = Column(UUID(as_uuid=False), ForeignKey('encryption_keys.id'), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)  # When participant started
    end_time = Column(DateTime(timezone=True), nullable=True)  # When participant finished
    status = Column(String(20), default='registered', nullable=False)  # registered, grace, running, completed

    __table_args__ = (
        UniqueConstraint('race_id', 'rfid_tag', name='uq_participant_race_rfid'),
        CheckConstraint("age >= 5 AND age <= 120", name='check_participant_age'),
        CheckConstraint("gender IN ('M', 'F', 'O')", name='check_participant_gender'),
        CheckConstraint("status IN ('registered', 'grace', 'running', 'completed')", name='check_participant_status'),
        Index('idx_participants_race_id', 'race_id'),
        Index('idx_participants_rfid_tag', 'rfid_tag'),
        Index('idx_participants_status', 'status'),
        {'extend_existing': True}  # Allow redefinition without creating during migrations
    )


# ---------------------------------------------------------------------------
# Audit Log Model (IMMUTABLE)
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Immutable audit log for all system actions"""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    action = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=True)
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    request_path = Column(String(500), nullable=True)
    request_method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)
    details = Column(JSONB, nullable=True)  # Additional context
    success = Column(Boolean, nullable=False)

    __table_args__ = (
        Index('idx_audit_action', 'action'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_ip_address', 'ip_address'),
    )


# ---------------------------------------------------------------------------
# Nonce Cache Model (for replay attack prevention)
# ---------------------------------------------------------------------------

class NonceCache(Base):
    """Nonce cache for replay attack detection"""
    __tablename__ = "nonce_cache"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    nonce = Column(String(128), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_nonce_cache_nonce', 'nonce'),
        Index('idx_nonce_cache_expires', 'expires_at'),
    )


# ---------------------------------------------------------------------------
# Encryption Keys Model (for key rotation)
# ---------------------------------------------------------------------------

class EncryptionKey(Base):
    """Encryption keys table for Fernet key rotation"""
    __tablename__ = "encryption_keys"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    key_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 hash of key
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_encryption_keys_active', 'is_active'),
    )


# ============================================================================
# RESPONSE WRAPPERS
# ============================================================================

class StandardResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    message: str
    data: Optional[dict] = None
    timestamp: str

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Standard error response wrapper"""
    success: bool = False
    error_code: str
    message: str
    details: Optional[dict] = None
    timestamp: str

    class Config:
        from_attributes = True
