"""
RFID Marathon Management System - FastAPI Application
Security Level: Military-grade
Last Updated: January 21, 2026

Main entrypoint for the backend API with:
- Strict authentication (JWT + replay protection)
- Encryption (Fernet at rest, RSA for responses)
- Idempotent migrations on startup
- Grace period management for RFID group locking
"""

import logging
import time
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo
from typing import Optional, Any, cast

from fastapi import FastAPI, Depends, HTTPException, status, Request, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.engine import Result, CursorResult

from constants import API_PREFIX, RaceStatus, ErrorMessages, FeatureFlags
from database.connection import (
    initialize_database,
    shutdown_database,
    get_db_session,
)
from database.migrations import run_migrations, verify_database_ready
from services.password_manager import get_password_manager
from services.jwt_manager import get_jwt_manager
from services.race_service import get_race_service
from services.rfid_service import get_rfid_service
from services.rsa_manager import get_rsa_manager
from services.fernet_manager import get_fernet_manager
from services.race_state_manager import get_race_state_manager
from middleware.auth_middleware import get_auth_middleware, get_current_user
from models import (
    LoginRequest,
    RaceCreateRequest,
    RaceUpdateRequest,
    ParticipantRegisterRequest,
    ParticipantLookupRequest,
    RFIDHitRequest,
    RaceStartRequest,
    RaceResponse,
    DashboardDataResponse,
    ParticipantResponse,
    RFIDHitResponse,
    RaceStartResponse,
)
from basefunctions import (
    create_success_response,
    create_error_response,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ApplicationError,
    get_current_timestamp_utc,
)

logger = logging.getLogger("rfid-marathon")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # logger.info("Initializing database and running migrations...")
    initialize_database()
    run_migrations()
    # logger.info("Startup complete")
    
    yield
    # logger.info("Shutting down services...")
    shutdown_database()
    # logger.info("Shutdown complete")


app = FastAPI(
    title="RFID Marathon Management System",
    version="1.0.0",
    description="Military-grade, audit-ready marathon timing backend",
    docs_url=f"{API_PREFIX}/docs",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Instantiate shared components
password_manager = get_password_manager()
jwt_manager = get_jwt_manager()
race_service = get_race_service()
rfid_service = get_rfid_service()
race_state_manager = get_race_state_manager()
rsa_manager = get_rsa_manager()
fernet_manager = get_fernet_manager()
auth_middleware = get_auth_middleware()


# ============================================================================
# BACKGROUND TASKS
# ============================================================================
# No background tasks - all state management is handled via status column
# and direct database updates in RFID hit handlers


# CORS configuration (restrict to desktop app origins; adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"] if FeatureFlags.ENFORCE_HTTPS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================================
# GLOBAL MIDDLEWARE (Error handling)
# ============================================================================

@app.middleware("http")
async def error_handling_pipeline(request: Request, call_next):
    """Global middleware for error handling."""
    # Request handling with error capture
    try:
        response = await call_next(request)
    except ApplicationError as exc:
        logger.error(f"Application error: {exc.message}")
        response = JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details
            )
        )
    except HTTPException as exc:
        response = JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                error_code="HTTP_EXCEPTION",
                message=str(exc.detail)
            )
        )
    except Exception as exc:  # Catch-all to avoid leaking errors
        logger.exception("Unhandled exception")
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                error_code="INTERNAL_SERVER_ERROR",
                message=ErrorMessages.INTERNAL_SERVER_ERROR
            )
        )
    return response


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================
# Handled via FastAPI lifespan in app initialization above.


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(AuthenticationError)
async def auth_error_handler(_request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=create_error_response("AUTHENTICATION_ERROR", exc.message)
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(_request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_error_response("VALIDATION_ERROR", exc.message, exc.details)
    )


@app.exception_handler(NotFoundError)
async def not_found_error_handler(_request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=create_error_response("NOT_FOUND", exc.message, exc.details)
    )


@app.exception_handler(ConflictError)
async def conflict_error_handler(_request: Request, exc: ConflictError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=create_error_response("CONFLICT", exc.message, exc.details)
    )


@app.exception_handler(ApplicationError)
async def application_error_handler(_request: Request, exc: ApplicationError):
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.error_code, exc.message, exc.details)
    )


# ============================================================================
# HEALTH ENDPOINT
# ============================================================================

@app.get("/health")
async def health():
    ready = verify_database_ready()
    return create_success_response({"status": "ok", "database_ready": ready})


@app.get(f"{API_PREFIX}/diagnostics/races")
async def get_race_diagnostics(db: Session = Depends(get_db_session), _user=Depends(get_current_user)):
    """
    Diagnostic endpoint to check all races and their current status.
    Shows participant counts and race status from database.
    """
    races = race_service.list_races(db=db)
    
    race_info = []
    for race in races:
        race_id = str(race.id)
        status = getattr(race, 'status', 'unknown')
        table_name_value = getattr(race, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"
        
        # Count participants by status
        try:
            registered_count = db.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}" WHERE status = :status'),
                {"status": "registered"}
            ).scalar() or 0
            grace_count = db.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}" WHERE status = :status'),
                {"status": "grace"}
            ).scalar() or 0
            running_count = db.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}" WHERE status = :status'),
                {"status": "running"}
            ).scalar() or 0
            completed_count = db.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}" WHERE status = :status'),
                {"status": "completed"}
            ).scalar() or 0
        except Exception as e:
            logger.debug(f"Could not query participant status for race {race_id}: {e}")
            registered_count = grace_count = running_count = completed_count = 0
        
        race_info.append({
            "id": race_id,
            "name": race.name,
            "status": status,
            "scheduled_date": race.scheduled_date.isoformat() if race.scheduled_date is not None else None,
            "participant_counts": {
                "registered": int(registered_count),
                "grace": int(grace_count),
                "running": int(running_count),
                "completed": int(completed_count)
            }
        })
    
    return create_success_response({
        "total_races": len(races),
        "races": race_info
    })


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post(f"{API_PREFIX}/auth/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db_session)):
    # Replay attack protection using timestamp + nonce in body
    jwt_manager.validate_replay_attack_protection(
        timestamp_str=payload.timestamp,
        nonce=payload.nonce,
        db=db
    )

    # Verify user
    from models import User
    # Log masked incoming info for diagnostics (do NOT log passwords)
    try:
        masked_nonce = (payload.nonce[:10] + "...") if payload.nonce else "(none)"
    except Exception:
        masked_nonce = "(invalid)"
    logger.debug(f"Login attempt received: username={payload.username!r}, timestamp={payload.timestamp!r}, nonce={masked_nonce}")

    # Try exact match first, then fallback to case-insensitive lookup
    user = db.query(User).filter_by(username=payload.username).first()
    if user is None:
        # Case-insensitive attempt
        try:
            user = db.query(User).filter(func.lower(User.username) == payload.username.lower()).first()
            # if user:
            #     logger.info(f"Case-insensitive username match: provided={payload.username!r}, matched={user.username!r}")
        except Exception:
            # Ignore DB errors here, will surface later
            logger.debug("Case-insensitive username lookup failed or not supported")
    if user is None:
        raise AuthenticationError(ErrorMessages.INVALID_CREDENTIALS)

    is_active = cast(bool, user.is_active)
    if not is_active:
        raise AuthenticationError(ErrorMessages.INVALID_CREDENTIALS)

    password_hash = cast(str, user.password_hash)
    if not password_manager.verify_password(payload.password, password_hash):
        raise AuthenticationError(ErrorMessages.INVALID_CREDENTIALS)

    # Optional: upgrade hash if cost factor increased
    if password_manager.needs_rehash(password_hash):
        setattr(user, "password_hash", password_manager.hash_password(payload.password))
        db.commit()

    access_token = jwt_manager.create_access_token(
        user_id=str(cast(str, user.id)),
        username=str(cast(str, user.username))
    )

    return create_success_response({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 60 * 15,
        "user_id": str(cast(str, user.id))
    })


# ============================================================================
# RACE ENDPOINTS
# ============================================================================

@app.post(f"{API_PREFIX}/race")
async def create_race(
    payload: RaceCreateRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    race = race_service.create_race(
        db=db,
        name=payload.name,
        distance_meters=payload.distance_meters,
        location=payload.location,
        scheduled_date_str=payload.scheduled_date,
        description=payload.description,
        created_by=_user["sub"],
        age_upto30_excellent=payload.age_upto30_excellent,
        age_upto30_good=payload.age_upto30_good,
        age_upto30_satisfactory=payload.age_upto30_satisfactory,
        age_upto40_excellent=payload.age_upto40_excellent,
        age_upto40_good=payload.age_upto40_good,
        age_upto40_satisfactory=payload.age_upto40_satisfactory,
        age_40to45_excellent=payload.age_40to45_excellent,
        age_40to45_good=payload.age_40to45_good,
        age_40to45_satisfactory=payload.age_40to45_satisfactory
    )
    race_response = RaceResponse.model_validate(race, from_attributes=True)
    return create_success_response(race_response.model_dump())


@app.get(f"{API_PREFIX}/race")
async def list_races(
    status_filter: Optional[RaceStatus] = None,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    races = race_service.list_races(db=db, status=status_filter)
    response = [RaceResponse.model_validate(r, from_attributes=True).model_dump() for r in races]
    return create_success_response(response)


@app.get(f"{API_PREFIX}/dashboard-data")
async def get_dashboard_data(
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """Get dashboard statistics including total participants, started/finished today counts, and per-race stats"""
    from datetime import datetime
    
    races = race_service.list_races(db=db)
    
    # Calculate metrics
    total_races = len(races)
    total_participants = 0
    race_stats = {}
    
    today_str = datetime.now().date().isoformat()
    started_today = 0
    finished_today = 0
    
    # Query each race's specific participant table directly
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    today_registrations = 0

    for race in races:
        # Each race has its own participant table stored in table_name
        table_name_value = getattr(race, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"
        
        try:
            # Count rows in the specific race's participant table
            participant_count_result = db.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\""))
            participant_count_value = participant_count_result.scalar() if participant_count_result else 0
            race_stats[str(race.id)] = int(participant_count_value or 0)
            total_participants += int(participant_count_value or 0)

            # Count registrations created today for today_registrations
            session_count = db.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM \"{table_name}\" 
                    WHERE registered_at >= :start_ts AND registered_at <= :end_ts
                    """
                ),
                {"start_ts": today_start, "end_ts": today_end}
            )
            session_count = session_count.scalar() if session_count else 0
            today_registrations += int(session_count or 0)
        except Exception as e:
            # Table might not exist yet, default to 0
            logger.debug(f"Could not query table {table_name}: {e}")
            race_stats[str(race.id)] = 0
        
        # Check if race is scheduled for today
        race_date = race.scheduled_date.date().isoformat() if race.scheduled_date is not None else None
        if race_date == today_str:
            # Count participants who started and finished today's races
            # Query from per-race participant table instead of deprecated TimingRecord
            try:
                started_count = db.execute(
                    text(f"SELECT COUNT(DISTINCT id) FROM \"{table_name}\" WHERE start_time IS NOT NULL"),
                ).scalar() or 0
                
                finished_count = db.execute(
                    text(f"SELECT COUNT(DISTINCT id) FROM \"{table_name}\" WHERE end_time IS NOT NULL"),
                ).scalar() or 0
                
                started_today += started_count
                finished_today += finished_count
            except Exception as e:
                logger.debug(f"Could not count timings for race {race.id}: {e}")
                # Table might not exist yet or have no timing data, default to 0
    
    dashboard_data = DashboardDataResponse(
        total_races=total_races,
        total_participants=total_participants,
        today_registrations=today_registrations,
        started_today=started_today,
        finished_today=finished_today,
        race_stats=race_stats
    )
    
    return create_success_response(dashboard_data.model_dump())


@app.get(f"{API_PREFIX}/race/{{race_id}}")
async def get_race(race_id: str, db: Session = Depends(get_db_session), user=Depends(get_current_user)):
    race = race_service.get_race(db=db, race_id=race_id)
    return create_success_response(RaceResponse.from_orm(race).dict())


@app.patch(f"{API_PREFIX}/race/{{race_id}}")
async def update_race(
    race_id: str,
    payload: RaceUpdateRequest,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    updates = payload.model_dump(exclude_unset=True)
    race = race_service.update_race(db=db, race_id=race_id, **updates)
    return create_success_response(RaceResponse.from_orm(race).dict())


@app.delete(f"{API_PREFIX}/race/{{race_id}}")
async def delete_race(
    race_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """Delete a race. Cannot delete active races."""
    race = race_service.get_race(db=db, race_id=race_id)
    
    # Avoid SQLAlchemy boolean expression in Python conditional by comparing to the enum value
    if getattr(race, "status", None) == RaceStatus.ACTIVE.value:
        raise ConflictError("Cannot delete an active race. End the race first.")
    
    # Delete the race (race_service should handle dropping participant table)
    race_service.delete_race(db=db, race_id=race_id)
    
    return create_success_response({"message": "Race deleted successfully"})


@app.post(f"{API_PREFIX}/race/{{race_id}}/start")
async def start_race(
    race_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """
    Start a race:
    1. Set status to 'active'
    2. Ensure no other race is active
    3. Set race start_time
    """
    from models import Race
    
    # Check if another race is already active
    active_race = db.query(Race).filter(Race.status == RaceStatus.ACTIVE).first()
    if active_race and str(active_race.id) != race_id:
        raise ConflictError(f"Another race '{active_race.name}' is already active. Only one race can be active at a time.")
    
    # Update race status to active
    race = race_service.update_race(
        db=db,
        race_id=race_id,
        status=RaceStatus.ACTIVE,
        start_time=get_current_timestamp_utc()
    )
    
    return create_success_response({
        "message": "Race started successfully",
        "race": RaceResponse.from_orm(race).dict()
    })


@app.post(f"{API_PREFIX}/race/{{race_id}}/end")
async def end_race(
    race_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """
    End a race:
    1. Set status to 'ended'
    2. Set race end_time
    """
    try:
        # End the race; this sets status to 'ended' (irreversible)
        race = race_service.update_race_status(db=db, race_id=race_id, new_status=RaceStatus.ENDED)
        race_response = RaceResponse.model_validate(race, from_attributes=True)
        return create_success_response(race_response.model_dump())
    except ValidationError as ve:
        raise ve
    except NotFoundError as ne:
        raise ne
    except Exception as exc:
        logger.exception(f"Failed to end race {race_id}: {exc}")
        raise exc


# ============================================================================
# PARTICIPANT ENDPOINTS
# ============================================================================

@app.post(f"{API_PREFIX}/participant/register")
async def register_participant(
    payload: ParticipantRegisterRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    # Ensure encryption key exists
    key_record = fernet_manager.get_or_create_active_key(db)

    participant = rfid_service.register_participant_with_rfid(
        db=db,
        race_id=payload.race_id,
        rfid_tag=payload.rfid_tag,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        category=payload.category,
        encryption_key_id=str(key_record.id)
    )

    # Re-encrypt name with RSA for frontend
    encrypted_name_rsa = rsa_manager.encrypt_with_public_key(
        fernet_manager.decrypt(str(participant.encrypted_name))
    )

    response = ParticipantResponse(
        id=str(participant.id),
        race_id=str(participant.race_id),
        rfid_tag=str(participant.rfid_tag),
        encrypted_name=encrypted_name_rsa,
        age=cast(Optional[int], participant.age),
        gender=cast(Optional[str], participant.gender),
        category=cast(Optional[str], participant.category),
        registered_at=participant.registered_at.isoformat()
    )

    return create_success_response(response.model_dump())


@app.post(f"{API_PREFIX}/participant/lookup")
async def lookup_participant(
    payload: ParticipantLookupRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    participant_data = rfid_service.lookup_participant_by_rfid(
        db=db,
        race_id=payload.race_id,
        rfid_tag=payload.rfid_tag,
        encrypt_response=True
    )
    return create_success_response(participant_data)



# ============================================================================
# PARTICIPANT LISTING ENDPOINTS
# ============================================================================

def _safe_table_name(race):
    table_name_value = getattr(race, "table_name", None)
    return table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"


def _fetch_participants_for_race(db: Session, race, fernet_mgr, rsa_mgr, include_timing: bool = False):
    participants = []
    table_name = _safe_table_name(race)
    
    # Build query with optional timing columns
    if include_timing:
        query = f'''
            SELECT id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at, encryption_key_id,
                   start_time, end_time, status
            FROM "{table_name}"
        '''
    else:
        query = f'''
            SELECT id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at, encryption_key_id 
            FROM "{table_name}"
        '''
    
    try:
        rows = db.execute(text(query)).fetchall()
    except Exception as exc:
        logger.debug(f"Could not query participants for race {race.id} table {table_name}: {exc}")
        return participants

    for row in rows:
        try:
            key = fernet_mgr.get_key_by_id(str(row.encryption_key_id))
        except Exception as exc:
            logger.debug(f"Could not fetch Fernet key for {row.encryption_key_id}: {exc}")
            key = None

        participant_data = {
            "id": str(row.id),
            "race_id": str(row.race_id),
            "rfid_tag": str(row.rfid_tag),
            "encrypted_name": str(row.encrypted_name),
            "encryption_key": key,
            "encryption_key_id": str(row.encryption_key_id) if getattr(row, "encryption_key_id", None) else None,
            "age": row.age,
            "gender": row.gender,
            "category": row.category,
            "registered_at": row.registered_at.isoformat() if row.registered_at else None,
        }
        
        # Add timing data if requested
        if include_timing:
            participant_data["start_time"] = row.start_time.isoformat() if getattr(row, "start_time", None) else None
            participant_data["end_time"] = row.end_time.isoformat() if getattr(row, "end_time", None) else None
            
            # Use status from database if available, otherwise calculate from timing data
            db_status = getattr(row, "status", None)
            if db_status:
                participant_data["status"] = db_status
            else:
                # Fallback: calculate status from timing data
                if row.end_time:
                    participant_data["status"] = "completed"
                elif row.start_time:
                    participant_data["status"] = "running"
                else:
                    participant_data["status"] = "registered"
        
        participants.append(participant_data)
    return participants


@app.get(f"{API_PREFIX}/participants")
async def list_participants(
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    races = race_service.list_races(db=db)
    all_participants = []
    for race in races:
        all_participants.extend(_fetch_participants_for_race(db, race, fernet_manager, rsa_manager))
    return create_success_response(all_participants)


@app.get(f"{API_PREFIX}/race/{{race_id}}/participants")
async def list_participants_by_race(
    race_id: str,
    include_timing: bool = False,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Get all participants for a specific race.
    
    Args:
        race_id: Race identifier
        include_timing: If True, includes start_time, end_time, and status fields
        
    Returns:
        List of participants with optional timing data
    """
    race = race_service.get_race(db=db, race_id=race_id)
    participants = _fetch_participants_for_race(db, race, fernet_manager, rsa_manager, include_timing=include_timing)
    return create_success_response(participants)


@app.patch(f"{API_PREFIX}/participant/{{participant_id}}")
async def update_participant(
    participant_id: str,
    payload: dict,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Update a participant in the per-race table.
    Only allowed if race status is 'created'.
    
    Args:
        participant_id: Participant ID
        payload: Updated fields (name, age, gender, category, rfid_tag)
        
    Returns:
        Updated participant data
        
    Raises:
        NotFoundError: If participant not found
        ConflictError: If race is not in 'created' status
        ValidationError: If validation fails
    """
    # Find participant - need to search all per-race tables
    races = race_service.list_races(db=db)
    participant_data = None
    target_race = None
    
    for race in races:
        table_name = getattr(race, "table_name", None)
        if not table_name:
            continue
            
        try:
            query = text(f'SELECT * FROM "{table_name}" WHERE id = :participant_id')
            result = db.execute(query, {"participant_id": participant_id}).fetchone()
            if result:
                participant_data = result
                target_race = race
                break
        except Exception:
            continue
    
    if not participant_data or not target_race:
        raise NotFoundError("Participant", participant_id)
    
    # Check race status - only allow updates if race is 'created'
    if getattr(target_race, "status", None) != "created":
        raise ConflictError(
            f"Cannot update participant. Race '{target_race.name}' is {getattr(target_race, 'status', 'unknown')}. "
            "Participants can only be modified when race status is 'created'."
        )
    
    # Build update query dynamically
    update_fields = []
    update_values = {"participant_id": participant_id}
    
    # Handle name encryption if provided
    if "name" in payload and payload["name"]:
        encrypted_name = fernet_manager.encrypt(payload["name"])
        update_fields.append("encrypted_name = :encrypted_name")
        update_values["encrypted_name"] = encrypted_name
    
    # Handle RFID tag update
    if "rfid_tag" in payload and payload["rfid_tag"]:
        rfid_tag = payload["rfid_tag"].upper()
        
        # Check for duplicate RFID in same race
        table_name = target_race.table_name
        check_sql = text(f"""
            SELECT COUNT(*) as count FROM "{table_name}"
            WHERE race_id = :race_id AND rfid_tag = :rfid_tag AND id != :participant_id
        """)
        result = db.execute(check_sql, {
            "race_id": str(target_race.id),
            "rfid_tag": rfid_tag,
            "participant_id": participant_id
        }).fetchone()
        
        if result and result[0] > 0:
            raise ConflictError(
                f"RFID tag {rfid_tag} is already assigned to another participant in this race"
            )
        
        update_fields.append("rfid_tag = :rfid_tag")
        update_values["rfid_tag"] = rfid_tag
    
    # Handle other fields
    if "age" in payload:
        update_fields.append("age = :age")
        update_values["age"] = payload["age"]
    
    if "gender" in payload and payload["gender"]:
        if payload["gender"] not in ["M", "F", "O"]:
            raise ValidationError("Gender must be M, F, or O")
        update_fields.append("gender = :gender")
        update_values["gender"] = payload["gender"]
    
    if "category" in payload:
        update_fields.append("category = :category")
        update_values["category"] = payload["category"]

    # If category not provided but age is, auto-calculate category using RFID service
    if ("category" not in payload or not payload.get("category")) and "age" in payload:
        try:
            calc_cat = rfid_service._calculate_category(payload.get("age"))
            if calc_cat:
                update_fields.append("category = :category")
                update_values["category"] = calc_cat
        except Exception:
            # If calculation fails, skip and let DB remain unchanged
            pass
    
    if not update_fields:
        raise ValidationError("No valid fields to update")
    
    # Execute update
    table_name = target_race.table_name
    update_sql = text(f"""
        UPDATE "{table_name}"
        SET {", ".join(update_fields)}
        WHERE id = :participant_id
        RETURNING id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at, encryption_key_id
    """)
    
    result = db.execute(update_sql, update_values).fetchone()
    if not result:
        raise ApplicationError("Failed to update participant", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    db.commit()
    
    # Return updated participant
    try:
        key = fernet_manager.get_key_by_id(str(result.encryption_key_id))
    except Exception:
        key = None
    
    return create_success_response({
        "id": str(result.id),
        "race_id": str(result.race_id),
        "rfid_tag": str(result.rfid_tag),
        "encrypted_name": str(result.encrypted_name),
        "encryption_key": key,
        "encryption_key_id": str(result.encryption_key_id) if result.encryption_key_id else None,
        "age": result.age,
        "gender": result.gender,
        "category": result.category,
        "registered_at": result.registered_at.isoformat() if result.registered_at else None
    })


@app.delete(f"{API_PREFIX}/participant/{{participant_id}}")
async def delete_participant(
    participant_id: str,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Delete a participant from the per-race table.
    Only allowed if race status is 'created'.
    
    Args:
        participant_id: Participant ID
        
    Returns:
        Success message
        
    Raises:
        NotFoundError: If participant not found
        ConflictError: If race is not in 'created' status
    """
    # Find participant - need to search all per-race tables
    races = race_service.list_races(db=db)
    participant_data = None
    target_race = None
    
    for race in races:
        table_name = getattr(race, "table_name", None)
        if not table_name:
            continue
            
        try:
            query = text(f'SELECT * FROM "{table_name}" WHERE id = :participant_id')
            result = db.execute(query, {"participant_id": participant_id}).fetchone()
            if result:
                participant_data = result
                target_race = race
                break
        except Exception:
            continue
    
    if not participant_data or not target_race:
        raise NotFoundError("Participant", participant_id)
    
    # Check race status - only allow deletion if race is 'created'
    if getattr(target_race, "status", None) != "created":
        raise ConflictError(
            f"Cannot delete participant. Race '{target_race.name}' is {getattr(target_race, 'status', 'unknown')}. "
            "Participants can only be deleted when race status is 'created'."
        )
    
    # Delete participant
    table_name = target_race.table_name
    delete_sql = text(f'DELETE FROM "{table_name}" WHERE id = :participant_id')
    db.execute(delete_sql, {"participant_id": participant_id})
    db.commit()
    
    return create_success_response({
        "message": "Participant deleted successfully",
        "participant_id": participant_id
    })


# ============================================================================
# RFID HUB ENDPOINTS 
# ============================================================================

@app.post(f"{API_PREFIX}/rfid/hit")
async def rfid_hit_unified(
    payload: RFIDHitRequest,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Unified RFID hit endpoint for both START and END line.
    Accepts requests from the RFID Listener service with timing_point metadata.
    
    Supports both:
    - Old format: Direct RFID tag submission (from separate proxies)
    - New format: With timing_point field (from unified listener)
    
    Request payload:
    {
        "rfid": "ABC123456" or "rfid_tag": "ABC123456",  // Either field
        "timing_point": "start" or "end",                  // From unified listener
        "antenna": 1,
        "read_count": 1,
        "signal_strength": -65,
        "first_seen": 1234567890,
        "last_seen": 1234567890,
        "bank_data": "...",
        "protocol": "EPC"
    }
    """
    try:
        # logger.info(f"[RFID_HIT] Raw payload: rfid={getattr(payload, 'rfid', 'N/A')}, rfid_tag={payload.rfid_tag}, reader_name={payload.reader_name}, timing_point={payload.timing_point}")
        
        # The validator already normalizes rfid_tag and derives timing_point
        rfid_tag = payload.rfid_tag
        if not rfid_tag:
            logger.error("[RFID_HIT] Missing RFID tag in payload")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFID tag is required"
            )
        timing_point = payload.timing_point or "start"
        hit_timestamp = payload.hit_timestamp  # Timestamp from proxy/listener
        
        
        # Route to appropriate handler based on timing_point
        if timing_point == "end":
            logger.info(f"[RFID_HIT] Routing to END handler")
            return await _handle_rfid_end(rfid_tag, db, hit_timestamp)
        else:
            # Default to start (including when timing_point is "start")
            logger.info(f"[RFID_HIT] Routing to START handler")
            return await _handle_rfid_start(rfid_tag, db, hit_timestamp)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RFID_HIT] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing RFID hit: {str(e)}"
        )


async def _handle_rfid_start(rfid_tag: str, db: Session, hit_timestamp: Optional[str] = None) -> dict:
    """
    Handle start line RFID hit.
    
    Logic:
    1. If race NOT active: Set status='grace', start_time=null, end_time=null
    2. If race IS active: 
       - Set status='running'
       - Set start_time to hit timestamp from proxy (RFID hit time)
       - BUT if RFID already exists with start_time, only update if gap > 5s and < 5min
    
    Args:
        rfid_tag: RFID tag ID
        db: Database session
        hit_timestamp: ISO timestamp from proxy/listener when RFID was detected
    
    Flow:
    1. Find the active race (status = 'active')
    2. Find the participant with this RFID
    3. Apply appropriate logic based on race status
    """
    # logger.info(f"[RFID_START] Processing start RFID: {rfid_tag}")
    
    try:
        # Use provided timestamp from proxy, or fallback to current time
        if hit_timestamp:
            try:
                current_time = parser.isoparse(hit_timestamp)
                # Ensure timezone-aware (add Asia/Kolkata if naive)
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                # logger.info(f"[RFID_START] Using proxy timestamp: {hit_timestamp}")
            except Exception as e:
                logger.warning(f"[RFID_START] Failed to parse hit_timestamp '{hit_timestamp}': {e}; using current time")
                current_time = get_current_timestamp_utc()
        else:
            current_time = get_current_timestamp_utc()
            # logger.debug(f"[RFID_START] No proxy timestamp provided; using backend time: {current_time}")
        
        # Find the active race
        query = text("""
            SELECT id, name, table_name, scheduled_date, status 
            FROM races 
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.ACTIVE.value}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_START] No active race found")
            response = RFIDHitResponse(
                success=False,
                message="No active race found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        race_id = str(getattr(race_row, "id"))
        race_name = getattr(race_row, "name")
        race_status = getattr(race_row, "status", "created")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"
        
        # logger.info(f"[RFID_START] Found race: {race_name} (id={race_id}, status={race_status}) - table: {table_name}")
        
        # Find the participant with this RFID in today's race table
        participant_row = db.execute(
            text(f'SELECT id, status, start_time FROM "{table_name}" WHERE rfid_tag = :rfid'),
            {"rfid": rfid_tag}
        ).fetchone()
        
        if not participant_row:
            logger.warning(f"[RFID_START] RFID {rfid_tag} not found in race {race_name}")
            response = RFIDHitResponse(
                success=False,
                message="Participant not registered for today's race",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        participant_id = str(getattr(participant_row, "id"))
        current_status = getattr(participant_row, "status", "registered")
        existing_start_time = getattr(participant_row, "start_time", None)
        
        # logger.info(f"[RFID_START] Found participant {participant_id} in {race_name} with status: {current_status}, existing_start_time: {existing_start_time}")

        # Precedence rule: completed > running > grace > registered
        # If participant is already completed, do NOT change status or start_time
        if current_status == "completed":
            # logger.info(f"[RFID_START] Participant {participant_id} already 'completed'; ignoring start hit (no changes)")
            response = RFIDHitResponse(
                success=True,
                message=f"Runner already completed in {race_name}; ignoring start hit",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        # CASE 1: Race is NOT started (idle status)
        if race_status != "started":
            # logger.info(f"[RFID_START] Race {race_name} is in {race_status} status (not started)")
            # Do not downgrade 'running' to 'grace'; only set grace for registered/grace
            if current_status in ("registered", "grace"):
                # logger.info(f"[RFID_START] Setting participant {participant_id} status='grace', start_time=null")
                db.execute(
                    text(f'UPDATE "{table_name}" SET status = :status, start_time = NULL, end_time = NULL WHERE id = :pid'),
                    {"status": "grace", "pid": participant_id}
                )
                db.commit()
                # logger.info(f"✓ Updated RFID {rfid_tag} to status 'grace' (race not started) in {race_name}")
                response = RFIDHitResponse(
                    success=True,
                    message=f"Runner marked at start line (grace) in {race_name}",
                    rfid_tag=rfid_tag
                )
                return create_success_response(response.model_dump())
            else:
                # current_status is 'running' (or any higher precedence), do nothing
                # logger.info(f"[RFID_START] Participant {participant_id} status '{current_status}' has precedence; no update while race not started")
                response = RFIDHitResponse(
                    success=True,
                    message=f"Race not started; keeping status '{current_status}'",
                    rfid_tag=rfid_tag
                )
                return create_success_response(response.model_dump())
        
        # CASE 2: Race IS started
        # logger.info(f"[RFID_START] Race {race_name} is in 'started' status")
        
        # Check if this RFID already has a start_time
        if existing_start_time:
            # Calculate time gap between recorded start_time and this RFID hit
            time_gap = (current_time - existing_start_time).total_seconds()
            # logger.info(f"[RFID_START] RFID already has start_time: {existing_start_time}, gap={time_gap}s")

            # if 5 < time_gap < 300:
            #     # Gap is within (5s, 5min): Update start_time and set status to running
            #     logger.info(f"[RFID_START] Time gap {time_gap}s in (5s, 5min); updating start_time to {current_time}")
            #     db.execute(
            #         text(f'UPDATE "{table_name}" SET status = :status, start_time = :ts WHERE id = :pid'),
            #         {"status": "running", "ts": current_time, "pid": participant_id}
            #     )
            #     db.commit()

            #     logger.info(f"✓ Updated RFID {rfid_tag} to status 'running' with new start_time in {race_name}")

            #     response = RFIDHitResponse(
            #         success=True,
            #         message=f"Runner start time updated (race started, 5s < gap < 5min) in {race_name}",
            #         rfid_tag=rfid_tag
            #     )
            #     return create_success_response(response.model_dump())
            # elif time_gap <= 5:
            #     # Gap too small: do not update start_time
            #     logger.info(f"[RFID_START] Time gap {time_gap}s <= 5s; NOT updating start_time")
            #     if current_status != "running":
            #         db.execute(
            #             text(f'UPDATE "{table_name}" SET status = :status WHERE id = :pid'),
            #             {"status": "running", "pid": participant_id}
            #         )
            #         db.commit()
            #         logger.info(f"[RFID_START] Updated status to 'running' (keeping existing start_time)")

            #     response = RFIDHitResponse(
            #         success=True,
            #         message=f"Runner already has valid start time (gap <= 5s, no update) in {race_name}",
            #         rfid_tag=rfid_tag
            #     )
            #     return create_success_response(response.model_dump())
            # else:
                # Gap too large (>= 5min): do not update start_time
            # logger.info(f"[RFID_START] Time gap {time_gap}s >= 300s; NOT updating start_time")
            if current_status != "running":
                db.execute(
                    text(f'UPDATE "{table_name}" SET status = :status WHERE id = :pid'),
                    {"status": "running", "pid": participant_id}
                )
                db.commit()
                # logger.info(f"[RFID_START] Updated status to 'running' (keeping existing start_time)")

            response = RFIDHitResponse(
                success=True,
                message=f"Runner outside update window (gap >= 5min, no update) in {race_name}",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        else:
            # No existing start_time: Set it to current time
            # logger.info(f"[RFID_START] RFID has no start_time, setting to {current_time}")
            
            db.execute(
                text(f'UPDATE "{table_name}" SET status = :status, start_time = :ts WHERE id = :pid'),
                {"status": "running", "ts": current_time, "pid": participant_id}
            )
            db.commit()
            
            # logger.info(f"✓ Updated RFID {rfid_tag} to status 'running' with start_time={current_time} in {race_name}")
            
            response = RFIDHitResponse(
                success=True,
                message=f"Runner marked running (race started, new start_time) in {race_name}",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
    except Exception as e:
        logger.error(f"[RFID_START] Error processing start RFID: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing start RFID: {str(e)}"
        )


async def _handle_rfid_end(rfid_tag: str, db: Session, hit_timestamp: Optional[str] = None) -> dict:
    """
    Handle end line RFID hit.
    
    Logic:
    - Only record end_time if runner status is 'running'
    - Find the race whose status is 'active'
    - Skip if runner is not in 'running' status
    
    Args:
        rfid_tag: RFID tag ID
        db: Database session
        hit_timestamp: ISO timestamp from proxy/listener when RFID was detected
    
    Flow:
    1. Find active race (status='active')
    2. Find the participant with this RFID
    3. Check if status is 'running'
    4. If yes: Update end_time and set status to 'completed'
    5. If no: Skip (return not ready message)
    """
    try:
        # logger.info(f"[RFID_END] Processing end RFID: {rfid_tag}")
        
        # Use provided timestamp from proxy, or fallback to current time
        if hit_timestamp:
            try:
                from zoneinfo import ZoneInfo
                current_time = parser.isoparse(hit_timestamp)
                # Ensure timezone-aware (add Asia/Kolkata if naive)
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                # logger.info(f"[RFID_END] Using proxy timestamp: {hit_timestamp}")
            except Exception as e:
                logger.warning(f"[RFID_END] Failed to parse hit_timestamp '{hit_timestamp}': {e}; using current time")
                current_time = get_current_timestamp_utc()
        else:
            current_time = get_current_timestamp_utc()
            logger.debug(f"[RFID_END] No proxy timestamp provided; using backend time: {current_time}")
        
        # Find the active race
        query = text("""
            SELECT id, name, table_name, scheduled_date, status 
            FROM races 
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.ACTIVE.value}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_END] No active race found")
            response = RFIDHitResponse(
                success=False,
                message="No active race found for today",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        race_id = str(getattr(race_row, "id"))
        race_name = getattr(race_row, "name")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"
        
        # logger.info(f"[RFID_END] Found active race: {race_name} (id={race_id}) - table: {table_name}")
        
        # Find the participant with this RFID
        participant_row = db.execute(
            text(f'SELECT id, status, start_time, end_time FROM "{table_name}" WHERE rfid_tag = :rfid'),
            {"rfid": rfid_tag}
        ).fetchone()
        
        if not participant_row:
            logger.warning(f"[RFID_END] RFID {rfid_tag} not found in race {race_name}")
            response = RFIDHitResponse(
                success=False,
                message="Participant not found in active race",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        participant_id = str(getattr(participant_row, "id"))
        participant_status = getattr(participant_row, "status", None)
        existing_end_time = getattr(participant_row, "end_time", None)
        
        # logger.info(f"[RFID_END] Found participant {participant_id} in {race_name} with status: {participant_status}, end_time: {existing_end_time}")
        
        # Check if status is 'running' (only then can we record end time)
        if participant_status != "running":
            logger.warning(f"[RFID_END] RFID {rfid_tag} status is '{participant_status}', not 'running' - skipping")
            response = RFIDHitResponse(
                success=False,
                message=f"Runner is not in 'running' status (current: {participant_status}), cannot record end time",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        # Check if end_time already exists
        if existing_end_time:
            logger.warning(f"[RFID_END] RFID {rfid_tag} already has end_time: {existing_end_time}")
            response = RFIDHitResponse(
                success=False,
                message="End time already recorded for this runner",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        # Record end time with timestamp from proxy and set status to 'completed'
        # logger.info(f"[RFID_END] Recording end time: {current_time} for participant {participant_id}")
        
        db.execute(
            text(f'UPDATE "{table_name}" SET end_time = :ts, status = :status WHERE id = :pid'),
            {"ts": current_time, "status": "completed", "pid": participant_id}
        )
        db.commit()
        
        # logger.info(f"✓ Recorded end time for RFID {rfid_tag} in race {race_name}, status set to 'completed'")
        
        response = RFIDHitResponse(
            success=True,
            message=f"End time recorded in {race_name}, status set to completed",
            rfid_tag=rfid_tag
        )
        return create_success_response(response.model_dump())
        
    except Exception as e:
        logger.error(f"[RFID_END] Error processing end RFID: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing end RFID: {str(e)}"
        )


@app.post(f"{API_PREFIX}/rfid/record-start")
async def record_rfid_start_from_listener(
    payload: RFIDHitRequest,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Accept RFID start hit from RFID Listener service (port 9090).
    
    Logic:
    1. If race NOT started: Set status='grace', start_time=null, end_time=null
    2. If race IS started: 
       - Set status='running'
       - Set start_time to current time (RFID hit time)
       - BUT if RFID already exists with start_time, only update if gap > 10 seconds
    """  
    rfid_tag_raw = payload.rfid_tag or getattr(payload, "rfid", None)
    if not rfid_tag_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFID tag is required"
        )
    rfid_tag = rfid_tag_raw.upper()
    
    try:
        # Get today's date
        today = datetime.utcnow().date()
        
        # Find today's race
        query = text("""
            SELECT id, name, table_name, scheduled_date, status 
            FROM races 
            WHERE DATE(scheduled_date) = :today
            ORDER BY created_at DESC
            LIMIT 1
        """)
        race_row = db.execute(query, {"today": today}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_START] No race scheduled for today")
            response = RFIDHitResponse(
                success=False,
                message="No race scheduled for today",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        race_name = getattr(race_row, "name")
        race_status = getattr(race_row, "status", "idle")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"
        
        # logger.info(f"[RFID_START] Found race: {race_name}, status={race_status}")
        
        # Find the participant with this RFID
        participant_row = db.execute(
            text(f'SELECT id, status, start_time FROM "{table_name}" WHERE rfid_tag = :rfid'),
            {"rfid": rfid_tag}
        ).fetchone()
        
        if not participant_row:
            logger.warning(f"[RFID_START] RFID {rfid_tag} not found in race {race_name}")
            response = RFIDHitResponse(
                success=False,
                message="Participant not found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        participant_id = str(getattr(participant_row, "id"))
        current_status = getattr(participant_row, "status", "registered")
        existing_start_time = getattr(participant_row, "start_time", None)
        
        current_time = get_current_timestamp_utc()
        
        # CASE 1: Race is NOT started
        if race_status != "started":
            # logger.info(f"[RFID_START] Race not started, setting status='grace'")
            
            db.execute(
                text(f'UPDATE "{table_name}" SET status = :status, start_time = NULL, end_time = NULL WHERE id = :pid'),
                {"status": "grace", "pid": participant_id}
            )
            db.commit()
            
            # logger.info(f"✓ Updated RFID {rfid_tag} to status 'grace'")
            
            response = RFIDHitResponse(
                success=True,
                message=f"Runner marked at start line (grace) in {race_name}",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        # CASE 2: Race IS started
        # logger.info(f"[RFID_START] Race started, checking start_time logic")
        
        if existing_start_time:
            time_gap = (current_time - existing_start_time).total_seconds()
            # logger.info(f"[RFID_START] Existing start_time: {existing_start_time}, gap={time_gap}s")
            
            if time_gap > 5:
                # logger.info(f"[RFID_START] Gap > 5s, updating start_time")
                db.execute(
                    text(f'UPDATE "{table_name}" SET status = :status, start_time = :ts WHERE id = :pid'),
                    {"status": "running", "ts": current_time, "pid": participant_id}
                )
                db.commit()
                
                # logger.info(f"✓ Updated RFID {rfid_tag} to status 'running' with new start_time")
                
                response = RFIDHitResponse(
                    success=True,
                    message=f"Runner start time updated (race started, gap > 5s) in {race_name}",
                    rfid_tag=rfid_tag
                )
                return create_success_response(response.model_dump())
            else:
                # logger.info(f"[RFID_START] Gap <= 5s, NOT updating start_time")
                
                if current_status != "running":
                    db.execute(
                        text(f'UPDATE "{table_name}" SET status = :status WHERE id = :pid'),
                        {"status": "running", "pid": participant_id}
                    )
                    db.commit()
                
                response = RFIDHitResponse(
                    success=True,
                    message=f"Runner already has valid start time (gap <= 5s) in {race_name}",
                    rfid_tag=rfid_tag
                )
                return create_success_response(response.model_dump())
        else:
            # logger.info(f"[RFID_START] No existing start_time, setting to {current_time}")
            
            db.execute(
                text(f'UPDATE "{table_name}" SET status = :status, start_time = :ts WHERE id = :pid'),
                {"status": "running", "ts": current_time, "pid": participant_id}
            )
            db.commit()
            
            # logger.info(f"✓ Updated RFID {rfid_tag} to status 'running' with start_time={current_time}")
            
            response = RFIDHitResponse(
                success=True,
                message=f"Runner marked running (race started, new start_time) in {race_name}",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
    except Exception as e:
        logger.error(f"[RFID_START] Error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing start RFID: {str(e)}"
        )


@app.post(f"{API_PREFIX}/rfid/record-end")
async def record_rfid_end_from_listener(
    payload: RFIDHitRequest,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Accept RFID end hit from RFID Listener service (port 9090).
    Immediately assigns endTIME to the runner.
    
    Flow:
    1. Listener receives end hit from end hub
    2. Listener forwards immediately to this endpoint
    3. Backend finds the race where this RFID has a startTIME
    4. Backend assigns endTIME with current server timestamp
    """
    
    rfid_tag_raw = payload.rfid_tag or getattr(payload, "rfid", None)
    if not rfid_tag_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFID tag is required"
        )
    rfid_tag = rfid_tag_raw.upper()
    
    try:
        # Record end time (timestamp is NOW - when request reached server) into per-race participant table
        # Search across races for candidate with started but not finished
        races = race_service.list_races(db=db)
        candidates = []
        for r in races:
            table_name_value = getattr(r, "table_name", None)
            table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{r.name}_participants"
            row = db.execute(
                text(f"SELECT id, start_time, end_time FROM \"{table_name}\" WHERE rfid_tag = :rfid"),
                {"rfid": rfid_tag}
            ).fetchone()
            if row:
                st = getattr(row, "start_time", None)
                et = getattr(row, "end_time", None)
                if st and not et:
                    candidates.append({
                        "race_id": str(getattr(r, "id")),
                        "table": table_name,
                        "pid": str(getattr(row, "id", row[0])),
                        "start_time": st
                    })
        if not candidates:
            response = RFIDHitResponse(
                success=False,
                message="No start time found for this RFID",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        target = max(candidates, key=lambda c: c["start_time"]) if len(candidates) > 1 else candidates[0]
        db.execute(
            text(f"UPDATE \"{target['table']}\" SET end_time = :ts WHERE id = :pid"),
            {"ts": get_current_timestamp_utc().isoformat(), "pid": target["pid"]}
        )
        db.commit()
        
        response = RFIDHitResponse(
            success=True,
            message="End time recorded",
            rfid_tag=rfid_tag
        )
        return create_success_response(response.model_dump())
        
    except ConflictError:
        # End time already exists
        response = RFIDHitResponse(
            success=False,
            message="End time already recorded",
            rfid_tag=rfid_tag
        )
        return create_success_response(response.model_dump())
    except Exception as e:
        logger.error(f"✗ Error processing end RFID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record end time"
        )


# ============================================================================
# RACE GROUP MANAGEMENT ENDPOINTS
# ============================================================================

@app.post(f"{API_PREFIX}/races/{{race_id}}/start-group")
async def start_race_group(
    race_id: str,
    payload: RaceStartRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Admin endpoint to start a race and all registered runners.
    
    Workflow:
    1. Set race status from 'created' to 'started'
    2. Find all participants with status='grace' in the per-race table
    3. Set start_time to current time and status remains 'grace'
    4. New RFIDs after this will have status set directly to 'running'
    """
    try:
        # Verify race exists
        race = race_service.get_race(db=db, race_id=race_id)
        table_name_value = getattr(race, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"
        
        current_timestamp = get_current_timestamp_utc()
        timestamp_iso = current_timestamp.isoformat()
        
        # Update all participants with status='grace' to set their start_time
        # These are participants who were scanned at start line before race started
        update_result = cast(CursorResult, db.execute(
            text(f'UPDATE "{table_name}" SET start_time = :ts WHERE status = :status AND start_time IS NULL'),
            {"ts": timestamp_iso, "status": "grace"}
        ))
        grace_count = update_result.rowcount if update_result.rowcount is not None else 0
        db.commit()
        
        # logger.info(f"✓ Updated {grace_count} grace status participants with start_time={timestamp_iso}")
        
        # Update race status from 'created' to 'started' AND race status from 'created' to 'started'
        db.execute(
            text('UPDATE races SET status = :status WHERE id = :race_id'),
            {"status": "started", "race_id": race_id}
        )
        db.commit()
        
        # logger.info(f"✓ Updated race {race_id} status to 'started'")
        
        response = RaceStartResponse(
            success=True,
            message=f"Race started, {grace_count} participants assigned start time",
            race_id=race_id,
            group_number=1,
            rfids_started=grace_count,
            start_time_assigned=timestamp_iso
        )
        
        return create_success_response(response.model_dump())
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"✗ Error starting race: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start race"
        )


# ============================================================================
# RACE GROUP QUERY ENDPOINTS
# ============================================================================

@app.get(f"{API_PREFIX}/races/{{race_id}}/groups")
async def get_race_groups(
    race_id: str,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Get all groups for a race.
    
    Returns:
        List of groups with their RFIDs and status
    """    
    race_state_manager = get_race_state_manager()
    
    try:
        groups = race_state_manager.get_all_groups(race_id)
        
        if not groups:
            return create_success_response([])
        
        return create_success_response(groups)
        
    except Exception as e:
        logger.error(f"✗ Error fetching races: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch races"
        )


@app.get(f"{API_PREFIX}/races/{{race_id}}/groups/{{group_number:int}}")
async def get_race_group(
    race_id: str,
    group_number: int,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Get details for a specific group.
    
    Returns:
        Group details including RFIDs, timestamps, and status
    """        
    try:
        groups = race_state_manager.get_all_groups(race_id)
        group = next((g for g in groups if g['group_number'] == group_number), None)
        
        if not group:
            raise NotFoundError(
                "Race",
                f"Race={race_id}, Group={group_number}"
            )
        
        return create_success_response(group)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_number} not found"
        )
    except Exception as e:
        logger.error(f"✗ Error fetching group details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch group details"
        )


# ============================================================================
# CRYPTOGRAPHY ENDPOINTS
# ============================================================================

@app.get(f"{API_PREFIX}/crypto/public-key")
async def get_public_key():
    """Expose RSA public key for frontend decryption."""
    pem = rsa_manager.export_public_key_pem()
    return create_success_response({"public_key_pem": pem})


# ============================================================================
# ERROR HANDLING FOR 404
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(_request: Request, _exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=create_error_response("NOT_FOUND", "Resource not found")
    )


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    return create_success_response({"message": "RFID Marathon Management System API"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)