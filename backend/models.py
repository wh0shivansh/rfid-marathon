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
    TimingState,
    TimingPoint,
    RaceStatus,
    AuditAction,
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
    # Age category qualifying times (in seconds)
    age_upto30_excellent: Optional[float] = Field(None, ge=0)
    age_upto30_good: Optional[float] = Field(None, ge=0)
    age_upto30_satisfactory: Optional[float] = Field(None, ge=0)
    age_upto40_excellent: Optional[float] = Field(None, ge=0)
    age_upto40_good: Optional[float] = Field(None, ge=0)
    age_upto40_satisfactory: Optional[float] = Field(None, ge=0)
    age_40to45_excellent: Optional[float] = Field(None, ge=0)
    age_40to45_good: Optional[float] = Field(None, ge=0)
    age_40to45_satisfactory: Optional[float] = Field(None, ge=0)


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
    # Age category qualifying times
    age_upto30_excellent: Optional[float] = None
    age_upto30_good: Optional[float] = None
    age_upto30_satisfactory: Optional[float] = None
    age_upto40_excellent: Optional[float] = None
    age_upto40_good: Optional[float] = None
    age_upto40_satisfactory: Optional[float] = None
    age_40to45_excellent: Optional[float] = None
    age_40to45_good: Optional[float] = None
    age_40to45_satisfactory: Optional[float] = None

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
# Timing Schemas
# ---------------------------------------------------------------------------

class TimingRecordRequest(BaseModel):
    """Record timing (start/end) request schema"""
    race_id: str
    rfid_tag: str = Field(..., min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH)
    timing_point: TimingPoint
    timestamp: str = Field(..., description="ISO 8601 timestamp of timing event")
    device_id: str = Field(..., min_length=1, max_length=100)

    @validator('rfid_tag')
    def validate_rfid_format(cls, v):
        if not validate_rfid_tag(v):
            raise ValueError('Invalid RFID tag format. Must be hexadecimal.')
        return v.upper()


class TimingRecordResponse(BaseModel):
    """Timing record response schema"""
    id: str
    race_id: str
    participant_id: str
    rfid_tag: str
    timing_point: TimingPoint
    recorded_at: str
    device_id: str
    synced: bool

    class Config:
        from_attributes = True


class SyncHandshakeRequest(BaseModel):
    """Sync handshake request to confirm successful storage"""
    timing_record_ids: List[str] = Field(..., min_length=1, max_length=100)


class SyncHandshakeResponse(BaseModel):
    """Sync handshake response"""
    confirmed_ids: List[str]
    failed_ids: List[str]
    timestamp: str


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
    status: str  # 'registered', 'started', 'finished', 'dnf'

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
    """5KM Race table"""
    __tablename__ = "races"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    distance_meters = Column(Integer, nullable=False)
    location = Column(String(200), nullable=False)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default=RaceStatus.CREATED.value, nullable=False)
    table_name = Column(String(128), nullable=False, unique=True)  # Maps to participants table for this race
    # Age category qualifying times (in minutes)
    age_upto30_excellent = Column(Float, nullable=True)
    age_upto30_good = Column(Float, nullable=True)
    age_upto30_satisfactory = Column(Float, nullable=True)
    age_upto40_excellent = Column(Float, nullable=True)
    age_upto40_good = Column(Float, nullable=True)
    age_upto40_satisfactory = Column(Float, nullable=True)
    age_40to45_excellent = Column(Float, nullable=True)
    age_40to45_good = Column(Float, nullable=True)
    age_40to45_satisfactory = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        CheckConstraint('distance_meters >= 10 AND distance_meters <= 100000', name='check_race_distance'),
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

    __table_args__ = (
        UniqueConstraint('race_id', 'rfid_tag', name='uq_participant_race_rfid'),
        CheckConstraint("age >= 5 AND age <= 120", name='check_participant_age'),
        CheckConstraint("gender IN ('M', 'F', 'O')", name='check_participant_gender'),
        Index('idx_participants_race_id', 'race_id'),
        Index('idx_participants_rfid_tag', 'rfid_tag'),
        {'extend_existing': True}  # Allow redefinition without creating during migrations
    )


# ---------------------------------------------------------------------------
# Timing Records Model (IMMUTABLE)
# ---------------------------------------------------------------------------

class TimingRecord(Base):
    """Timing records table - IMMUTABLE after creation"""
    __tablename__ = "timing_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    race_id = Column(UUID(as_uuid=False), ForeignKey('races.id', ondelete='CASCADE'), nullable=False, index=True)
    participant_id = Column(UUID(as_uuid=False), nullable=False, index=True)  # No FK - participant table is dynamic
    participant_table_name = Column(String(128), nullable=False)  # Track which table participant is in
    rfid_tag = Column(String(32), nullable=False, index=True)
    timing_point = Column(String(10), nullable=False)  # 'start' or 'end'
    recorded_at = Column(DateTime(timezone=True), nullable=False)  # Actual timing event timestamp
    device_id = Column(String(100), nullable=False)
    synced = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # DB insertion time

    __table_args__ = (
        UniqueConstraint('race_id', 'participant_id', 'timing_point', name='uq_timing_race_participant_point'),
        CheckConstraint("timing_point IN ('start', 'end')", name='check_timing_point'),
        Index('idx_timing_race_id', 'race_id'),
        Index('idx_timing_participant_id', 'participant_id'),
        Index('idx_timing_rfid_tag', 'rfid_tag'),
        Index('idx_timing_synced', 'synced'),
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
