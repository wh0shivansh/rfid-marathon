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

from pydantic import BaseModel, Field, validator
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
    RaceCategory,
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

_QUALIFYING_DEFAULTS = {
    "bpet_age_upto30": [1500.0, 1578.0, 1620.0],
    "bpet_age_upto40": [1698.0, 1800.0, 1860.0],
    "bpet_age_40_45": [1878.0, 1980.0, 2100.0],
    "cpt_age_upto35": [840.0, 900.0, 960.0, 1050.0],
    "cpt_age_35_45": [960.0, 1020.0, 1080.0, 1200.0],
    "cpt_age_45_50": [1020.0, 1080.0, 1140.0, 1230.0],
    "cpt_age_50_55": [1680.0, 1800.0, 1920.0, 2040.0],
    "cpt_age_55_60": [1920.0, 2040.0, 2160.0, 2280.0],
    "ppt_age_upto30": [540.0, 570.0, 600.0],
    "ppt_age_30_40": [630.0, 660.0, 690.0],
    "ppt_age_40_45": [690.0, 720.0, 750.0],
    "ppt_age_45_50": [780.0, 840.0, 900.0],
}

_QUALIFYING_LIST_LENGTHS = {
    "bpet_age_upto30": 3,
    "bpet_age_upto40": 3,
    "bpet_age_40_45": 3,
    "cpt_age_upto35": 4,
    "cpt_age_35_45": 4,
    "cpt_age_45_50": 4,
    "cpt_age_50_55": 4,
    "cpt_age_55_60": 4,
    "ppt_age_upto30": 3,
    "ppt_age_30_40": 3,
    "ppt_age_40_45": 3,
    "ppt_age_45_50": 3,
}


def _validate_qualifying_list(value: Optional[List[float]], field_name: str) -> List[float]:
    if value is None:
        return _QUALIFYING_DEFAULTS[field_name].copy()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    expected = _QUALIFYING_LIST_LENGTHS[field_name]
    if len(value) != expected:
        raise ValueError(f"{field_name} must have {expected} values")
    try:
        normalized = [float(v) for v in value]
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must contain numeric values")
    if any(v < 0 for v in normalized):
        raise ValueError(f"{field_name} values must be >= 0")
    return normalized

class RaceCreateRequest(BaseModel):
    """Create race request schema"""
    name: str = Field(..., min_length=3, max_length=200)
    distance_meters: int = Field(..., ge=10, le=100000)
    location: str = Field(..., min_length=3, max_length=200)
    scheduled_date: str = Field(..., description="ISO 8601 date")
    description: Optional[str] = Field(None, max_length=1000)
    copy_from_race_id: Optional[str] = Field(None, description="Optional race ID to copy participants from")
    race_category: RaceCategory = Field(RaceCategory.BPET)
    # Qualifying times (seconds) stored as per-age lists
    bpet_age_upto30: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_upto30"].copy())
    bpet_age_upto40: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_upto40"].copy())
    bpet_age_40_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_40_45"].copy())
    cpt_age_upto35: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_upto35"].copy())
    cpt_age_35_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_35_45"].copy())
    cpt_age_45_50: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_45_50"].copy())
    cpt_age_50_55: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_50_55"].copy())
    cpt_age_55_60: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_55_60"].copy())
    ppt_age_upto30: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_upto30"].copy())
    ppt_age_30_40: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_30_40"].copy())
    ppt_age_40_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_40_45"].copy())
    ppt_age_45_50: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_45_50"].copy())

    @validator(*_QUALIFYING_LIST_LENGTHS.keys(), pre=True)
    def validate_qualifying_lists(cls, v, values, **kwargs):
        field = kwargs.get("field")
        field_name = getattr(field, "name", None)
        if not field_name:
            return v
        return _validate_qualifying_list(v, field_name)


class RaceUpdateRequest(BaseModel):
    """Update race request schema"""
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    distance_meters: Optional[int] = Field(None, ge=10, le=100000)
    location: Optional[str] = Field(None, min_length=3, max_length=200)
    scheduled_date: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[RaceStatus] = None
    race_category: Optional[RaceCategory] = None
    bpet_age_upto30: Optional[List[float]] = None
    bpet_age_upto40: Optional[List[float]] = None
    bpet_age_40_45: Optional[List[float]] = None
    cpt_age_upto35: Optional[List[float]] = None
    cpt_age_35_45: Optional[List[float]] = None
    cpt_age_45_50: Optional[List[float]] = None
    cpt_age_50_55: Optional[List[float]] = None
    cpt_age_55_60: Optional[List[float]] = None
    ppt_age_upto30: Optional[List[float]] = None
    ppt_age_30_40: Optional[List[float]] = None
    ppt_age_40_45: Optional[List[float]] = None
    ppt_age_45_50: Optional[List[float]] = None

    @validator(*_QUALIFYING_LIST_LENGTHS.keys(), pre=True)
    def validate_update_qualifying_lists(cls, v, values, **kwargs):
        if v is None:
            return None
        field = kwargs.get("field")
        field_name = getattr(field, "name", None)
        if not field_name:
            return v
        return _validate_qualifying_list(v, field_name)


class RaceResponse(BaseModel):
    """Race response schema"""
    id: str
    name: str
    distance_meters: int
    location: str
    scheduled_date: datetime
    description: Optional[str]
    status: RaceStatus
    race_category: RaceCategory
    created_at: datetime
    updated_at: datetime
    table_name: str
    participant_count: int = 0
    # Qualifying times (seconds)
    bpet_age_upto30: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_upto30"].copy())
    bpet_age_upto40: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_upto40"].copy())
    bpet_age_40_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["bpet_age_40_45"].copy())
    cpt_age_upto35: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_upto35"].copy())
    cpt_age_35_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_35_45"].copy())
    cpt_age_45_50: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_45_50"].copy())
    cpt_age_50_55: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_50_55"].copy())
    cpt_age_55_60: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["cpt_age_55_60"].copy())
    ppt_age_upto30: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_upto30"].copy())
    ppt_age_30_40: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_30_40"].copy())
    ppt_age_40_45: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_40_45"].copy())
    ppt_age_45_50: List[float] = Field(default_factory=lambda: _QUALIFYING_DEFAULTS["ppt_age_45_50"].copy())
    bpet_start_time: Optional[List[str]] = None
    cpt_start_time: Optional[List[str]] = None
    ppt_start_time: Optional[List[str]] = None
    end_time: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True
        ser_json_by_alias = True
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
    age: int = Field(..., ge=10, le=100)
    gender: str = Field(..., pattern="^(M|F|O)$")
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
    age: int
    gender: str
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
    reader_name: Optional[str] = Field(None, description="Reader identifier: 'Reader 1' (start), 'Reader 2' (mid), or 'Reader 3' (end)")
    timing_point: Optional[str] = Field(None, description="'start', 'mid', or 'end' - Derived from reader_name if not explicitly set")
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
        if 'reader 3' in reader_name or 'reader3' in reader_name or reader_name == 'end':
            return 'end'
        elif 'reader 2' in reader_name or 'reader2' in reader_name or reader_name == 'mid':
            return 'mid'
        elif 'reader 1' in reader_name or 'reader1' in reader_name or reader_name == 'start':
            return 'start'
        
        return 'start'  # Default to start


class RFIDBulkEntry(BaseModel):
    """Single RFID bulk entry"""
    rfid: str = Field(..., min_length=RFID_TAG_MIN_LENGTH, max_length=RFID_TAG_MAX_LENGTH)
    reader_id: int = Field(..., ge=1, le=3)
    timestamp: str = Field(..., description="ISO timestamp when tag was detected")

    @validator('rfid')
    def validate_bulk_rfid_format(cls, v):
        if not validate_rfid_tag(v):
            raise ValueError('Invalid RFID tag format. Must be hexadecimal.')
        return v.upper()

    class Config:
        extra = "ignore"


class RFIDBulkRequest(BaseModel):
    """Bulk RFID upload payload"""
    entries: List[RFIDBulkEntry]

    @validator('entries')
    def check_entries_not_empty(cls, v):
        if not isinstance(v, list) or len(v) < 1:
            raise ValueError('entries must contain at least one item')
        return v

    class Config:
        extra = "ignore"


class RFIDHitResponse(BaseModel):
    """Response to RFID hit"""
    success: bool
    message: str
    rfid_tag: Optional[str] = None


class RaceStartRequest(BaseModel):
    """Request to start a race (assign start times)"""
    race_id: str = Field(..., description="Race identifier")
    group_number: int = Field(..., ge=1, description="Group number to start")


class RaceStartTimesRequest(BaseModel):
    """Request to set per-age start times for a race"""
    start_times: List[str] = Field(..., description="ISO 8601 timestamps in age-group order")


class RaceStartResponse(BaseModel):
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
    mid_time: Optional[str]
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
    race_category = Column(String(50), nullable=False, default=RaceCategory.BPET.value)  # e.g., 'BPET', 'CPT', 'PPT'

    # Qualifying times (seconds) stored as JSONB lists per age group
    bpet_age_upto30 = Column(JSONB, nullable=False, default=lambda: [1500.0, 1578.0, 1620.0])
    bpet_age_upto40 = Column(JSONB, nullable=False, default=lambda: [1698.0, 1800.0, 1860.0])
    bpet_age_40_45 = Column(JSONB, nullable=False, default=lambda: [1878.0, 1980.0, 2100.0])
    cpt_age_upto35 = Column(JSONB, nullable=False, default=lambda: [840.0, 900.0, 960.0, 1050.0])
    cpt_age_35_45 = Column(JSONB, nullable=False, default=lambda: [960.0, 1020.0, 1080.0, 1200.0])
    cpt_age_45_50 = Column(JSONB, nullable=False, default=lambda: [1020.0, 1080.0, 1140.0, 1230.0])
    cpt_age_50_55 = Column(JSONB, nullable=False, default=lambda: [1680.0, 1800.0, 1920.0, 2040.0])
    cpt_age_55_60 = Column(JSONB, nullable=False, default=lambda: [1920.0, 2040.0, 2160.0, 2280.0])
    ppt_age_upto30 = Column(JSONB, nullable=False, default=lambda: [540.0, 570.0, 600.0])
    ppt_age_30_40 = Column(JSONB, nullable=False, default=lambda: [630.0, 660.0, 690.0])
    ppt_age_40_45 = Column(JSONB, nullable=False, default=lambda: [690.0, 720.0, 750.0])
    ppt_age_45_50 = Column(JSONB, nullable=False, default=lambda: [780.0, 840.0, 900.0])

    # Per-age start times stored as ordered lists (ISO strings)
    bpet_start_time = Column(JSONB, nullable=True)
    cpt_start_time = Column(JSONB, nullable=True)
    ppt_start_time = Column(JSONB, nullable=True)


    end_time = Column(DateTime(timezone=True), nullable=True)  # When race was ended
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        CheckConstraint('distance_meters >= 10 AND distance_meters <= 100000', name='check_race_distance'),
        CheckConstraint("status IN ('created', 'started', 'completed')", name='check_race_status'),
        CheckConstraint("race_category IN ('BPET', 'CPT', 'PPT')", name='check_race_category'),
        CheckConstraint("jsonb_typeof(bpet_age_upto30) = 'array' AND jsonb_array_length(bpet_age_upto30) = 3", name='check_bpet_age_upto30_len'),
        CheckConstraint("jsonb_typeof(bpet_age_upto40) = 'array' AND jsonb_array_length(bpet_age_upto40) = 3", name='check_bpet_age_upto40_len'),
        CheckConstraint("jsonb_typeof(bpet_age_40_45) = 'array' AND jsonb_array_length(bpet_age_40_45) = 3", name='check_bpet_age_40_45_len'),
        CheckConstraint("jsonb_typeof(cpt_age_upto35) = 'array' AND jsonb_array_length(cpt_age_upto35) = 4", name='check_cpt_age_upto35_len'),
        CheckConstraint("jsonb_typeof(cpt_age_35_45) = 'array' AND jsonb_array_length(cpt_age_35_45) = 4", name='check_cpt_age_35_45_len'),
        CheckConstraint("jsonb_typeof(cpt_age_45_50) = 'array' AND jsonb_array_length(cpt_age_45_50) = 4", name='check_cpt_age_45_50_len'),
        CheckConstraint("jsonb_typeof(cpt_age_50_55) = 'array' AND jsonb_array_length(cpt_age_50_55) = 4", name='check_cpt_age_50_55_len'),
        CheckConstraint("jsonb_typeof(cpt_age_55_60) = 'array' AND jsonb_array_length(cpt_age_55_60) = 4", name='check_cpt_age_55_60_len'),
        CheckConstraint("jsonb_typeof(ppt_age_upto30) = 'array' AND jsonb_array_length(ppt_age_upto30) = 3", name='check_ppt_age_upto30_len'),
        CheckConstraint("jsonb_typeof(ppt_age_30_40) = 'array' AND jsonb_array_length(ppt_age_30_40) = 3", name='check_ppt_age_30_40_len'),
        CheckConstraint("jsonb_typeof(ppt_age_40_45) = 'array' AND jsonb_array_length(ppt_age_40_45) = 3", name='check_ppt_age_40_45_len'),
        CheckConstraint("jsonb_typeof(ppt_age_45_50) = 'array' AND jsonb_array_length(ppt_age_45_50) = 3", name='check_ppt_age_45_50_len'),
        CheckConstraint("bpet_start_time IS NULL OR (jsonb_typeof(bpet_start_time) = 'array' AND jsonb_array_length(bpet_start_time) = 3)", name='check_bpet_start_time_len'),
        CheckConstraint("cpt_start_time IS NULL OR (jsonb_typeof(cpt_start_time) = 'array' AND jsonb_array_length(cpt_start_time) = 5)", name='check_cpt_start_time_len'),
        CheckConstraint("ppt_start_time IS NULL OR (jsonb_typeof(ppt_start_time) = 'array' AND jsonb_array_length(ppt_start_time) = 4)", name='check_ppt_start_time_len'),
        Index('idx_races_status', 'status'),
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
    __tablename__ = "PerRaceTable"

    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    race_id = Column(UUID(as_uuid=False), ForeignKey('races.id', ondelete='CASCADE'), nullable=False, index=True)
    rfid_tag = Column(String(32), nullable=False, index=True)  # PLAINTEXT (requirement)
    s_no = Column(Integer, nullable=True)
    army_number = Column(String(64), nullable=False)
    rank = Column(String(64), nullable=False)
    remarks = Column(Text, nullable=True)
    encrypted_name = Column(Text, nullable=False)  # Fernet encrypted
    age = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)
    category = Column(String(50), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    encryption_key_id = Column(UUID(as_uuid=False), ForeignKey('encryption_keys.id'), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)  # When participant started
    mid_time = Column(DateTime(timezone=True), nullable=True)  # Mid-point verification
    end_time = Column(DateTime(timezone=True), nullable=True)  # When participant finished
    status = Column(String(20), default='registered', nullable=False)  # registered, grace, running, completed, fail

    __table_args__ = (
        UniqueConstraint('race_id', 'rfid_tag', name='uq_participant_race_rfid'),
        CheckConstraint("age >= 5 AND age <= 120", name='check_participant_age'),
        CheckConstraint("gender IN ('M', 'F', 'O')", name='check_participant_gender'),
        CheckConstraint("status IN ('registered', 'grace', 'running', 'completed', 'fail')", name='check_participant_status'),
        Index('idx_participants_race_id', 'race_id'),
        Index('idx_participants_rfid_tag', 'rfid_tag'),
        Index('idx_participants_status', 'status'),
        {'extend_existing': True}  # Allow redefinition without creating during migrations
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
