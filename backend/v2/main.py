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
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, tzinfo
from io import BytesIO
from dateutil import parser
from zoneinfo import ZoneInfo
from pathlib import Path
from multiprocessing import freeze_support
from typing import Optional, Any, cast

import pandas as pd
from docx import Document

from fastapi import FastAPI, Depends, HTTPException, status, Request, Body, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.engine import CursorResult

from constants import API_PREFIX, RaceStatus, RACE_STATUS_TRANSITIONS, ErrorMessages, FeatureFlags, BULK_HEADERS, RFID_PREFIX
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
from middleware.auth_middleware import get_current_user
from models import (
    LoginRequest,
    RaceCreateRequest,
    RaceUpdateRequest,
    ParticipantRegisterRequest,
    ParticipantLookupRequest,
    RFIDHitRequest,
    RFIDBulkRequest,
    RaceStartTimesRequest,
    RaceResponse,
    DashboardDataResponse,
    ParticipantResponse,
    RFIDHitResponse,
)
from basefunctions import (
    create_success_response,
    create_error_response,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ApplicationError,
    get_current_timestamp_IST,
    validate_rfid_tag,
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
    version="2.0.0-alpha",
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
rsa_manager = get_rsa_manager()
fernet_manager = get_fernet_manager()


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


@app.get(f"{API_PREFIX}/diagnostics/transitions")
async def get_transition_diagnostics(_user=Depends(get_current_user)):
    """Get race status transition map for debugging"""
    return create_success_response({
        "transitions": RACE_STATUS_TRANSITIONS,
        "statuses": {
            "CREATED": RaceStatus.CREATED.value,
            "STARTED": RaceStatus.STARTED.value,
            "COMPLETED": RaceStatus.COMPLETED.value
        }
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
        copy_from_race_id=payload.copy_from_race_id,
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
    response = [RaceResponse.model_validate(r, from_attributes=True).model_dump(by_alias=True) for r in races]
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

    if getattr(race, "status", None) != RaceStatus.CREATED.value:
        raise ConflictError("Start times can only be updated before the race starts")
    return create_success_response(RaceResponse.from_orm(race).dict(by_alias=True))


@app.patch(f"{API_PREFIX}/race/{{race_id}}")
async def update_race(
    race_id: str,
    payload: RaceUpdateRequest,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    updates = payload.model_dump(exclude_unset=True)
    race = race_service.update_race(db=db, race_id=race_id, **updates)
    return create_success_response(RaceResponse.from_orm(race).dict(by_alias=True))


@app.delete(f"{API_PREFIX}/race/{{race_id}}")
async def delete_race(
    race_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """Delete a race. Cannot delete started races."""
    race = race_service.get_race(db=db, race_id=race_id)
    
    # Avoid SQLAlchemy boolean expression in Python conditional by comparing to the enum value
    if getattr(race, "status", None) == RaceStatus.STARTED.value:
        raise ConflictError("Cannot delete a started race. End the race first.")
    
    # Delete the race (race_service should handle dropping participant table)
    race_service.delete_race(db=db, race_id=race_id)
    
    return create_success_response({"message": "Race deleted successfully"})


@app.post(f"{API_PREFIX}/race/{{race_id}}/start-times")
async def update_race_start_times(
    race_id: str,
    payload: RaceStartTimesRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """Set per-age start times for a race."""
    race = race_service.get_race(db=db, race_id=race_id)

    try:
        up30_time = parser.isoparse(payload.up30start_time)
        upto40_time = parser.isoparse(payload.upto40start_time)
        start_40_45_time = parser.isoparse(payload.start_time_40_45)
    except Exception as exc:
        raise ValidationError(f"Invalid start time format: {exc}")

    race = race_service.update_race(
        db=db,
        race_id=race_id,
        up30start_time=up30_time,
        upto40start_time=upto40_time,
        start_time_40_45=start_40_45_time,
    )

    return create_success_response({
        "message": "Race start times updated",
        "race": RaceResponse.from_orm(race).dict(by_alias=True)
    })


@app.post(f"{API_PREFIX}/race/{{race_id}}/start")
async def start_race(
    race_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """
    Start a race:
    1. Set status to 'started'
    2. Ensure no other race is started
    3. Assign per-age start_time values from races table
    """
    from models import Race

    # Prevent multiple started races at the same time
    existing_race = db.query(Race).filter(Race.status == RaceStatus.STARTED).first()
    if existing_race and str(existing_race.id) != race_id:
        raise ConflictError(f"Another race '{existing_race.name}' is already started. Only one race can be started at a time.")

    race = race_service.get_race(db=db, race_id=race_id)
    table_name_value = getattr(race, "table_name", None)
    table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"

    up30_time = cast(Optional[datetime], race.up30start_time)
    upto40_time = cast(Optional[datetime], race.upto40start_time)
    start_40_45_time = cast(Optional[datetime], race.start_time_40_45)

    if not up30_time or not upto40_time or not start_40_45_time:
        raise ValidationError("Race start times are not configured for all age groups")

    # Promote race to STARTED
    race = race_service.update_race_status(db=db, race_id=race_id, new_status=RaceStatus.STARTED)

    assigned_count = 0
    try:
        update_result = cast(CursorResult, db.execute(
            text(
                f"""
                UPDATE "{table_name}"
                SET start_time = CASE
                    WHEN age < 30 THEN :up30
                    WHEN age >= 30 AND age < 40 THEN :upto40
                    WHEN age >= 40 AND age <= 45 THEN :start_40_45
                    ELSE NULL
                END
                """
            ),
            {
                "up30": up30_time,
                "upto40": upto40_time,
                "start_40_45": start_40_45_time,
            }
        ))
        assigned_count = update_result.rowcount if update_result.rowcount is not None else 0
        db.commit()
    except Exception:
        db.rollback()

    start_time_assigned = min(
        cast(datetime, up30_time),
        cast(datetime, upto40_time),
        cast(datetime, start_40_45_time),
    ).isoformat()

    return create_success_response({
        "message": f"Race activated successfully, {assigned_count} participants assigned start time",
        "race": RaceResponse.from_orm(race).dict(by_alias=True),
        "rfids_started": assigned_count,
        "start_time_assigned": start_time_assigned
    })


@app.post(f"{API_PREFIX}/race/{{race_id}}/end")
async def end_race(
    race_id: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """
    End a race:
    1. Set status to 'completed'
    2. Set race end_time
    """
    try:
        # Use start_time from frontend if provided, otherwise use backend time
        end_time_str = payload.get('end_time')
        if end_time_str:
            try:
                # Parse ISO timestamp from frontend
                current_timestamp = parser.isoparse(end_time_str)
            except Exception as e:
                logger.warning(f"Failed to parse end_time from frontend: {e}, using backend time")
                current_timestamp = get_current_timestamp_IST()
        else:
            current_timestamp = get_current_timestamp_IST()
        
        timestamp_iso = current_timestamp.isoformat()
        
        # Update race status and set end_time
        race = race_service.update_race(
            db=db,
            race_id=race_id,
            status=RaceStatus.COMPLETED,
            end_time=timestamp_iso
        )
        
        race_response = RaceResponse.model_validate(race, from_attributes=True)
        return create_success_response(race_response.model_dump(by_alias=True))
    except ValidationError as ve:
        raise ve
    except NotFoundError as ne:
        raise ne
    except Exception as exc:
        logger.exception(f"Failed to end race {race_id}: {exc}")
        raise exc


@app.post(f"{API_PREFIX}/race/{{race_id}}/status/update")
async def update_race_status_endpoint(
    race_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user)
):
    """
    Unified status update endpoint for races.
    Accepts JSON payload: {"status": "created"|"started"|"completed"}

    - Setting to `created` is treated as a system rollback and will be executed with `system=True`.
    - Setting to `started` will set the race to started (demoting any existing started race first).
    - Setting to `completed` will complete a started race (irreversible).
    """
    desired_status = payload.get("status")
    if not desired_status:
        raise ValidationError("Missing 'status' in request body")

    try:
        new_status = RaceStatus(desired_status)
    except Exception:
        raise ValidationError(f"Invalid status value: {desired_status}")

    system_flag = True if new_status == RaceStatus.CREATED else False

    try:
        race = race_service.update_race_status(db=db, race_id=race_id, new_status=new_status, system=system_flag)
        race_response = RaceResponse.model_validate(race, from_attributes=True)
        return create_success_response(race_response.model_dump(by_alias=True))
    except ValidationError as ve:
        raise ve
    except NotFoundError as ne:
        raise ne
    except Exception as exc:
        logger.exception(f"Failed to update race status {race_id}: {exc}")
        raise exc


# ============================================================================
# BULK UPLOAD HELPERS
# ============================================================================

def _normalize_bulk_header(value: Any) -> str:
    raw = str(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    aliases = {
        "s no": "s.no",
        "sno": "s.no",
        "sr no": "s.no",
        "serial no": "s.no",
        "serial number": "s.no",
        "sl no": "s.no",
        "army no": "army number",
        "army number": "army number",
        "rank": "rank",
        "name": "name",
        "age": "age",
        "remark": "remarks",
        "remarks": "remarks",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized


def _load_docx_table(file_bytes: bytes) -> pd.DataFrame:
    doc = Document(BytesIO(file_bytes))
    if not doc.tables:
        raise ValidationError("DOCX file does not contain a table")
    table = doc.tables[0]
    rows = []
    for row in table.rows:
        rows.append([cell.text.strip() for cell in row.cells])
    if not rows:
        raise ValidationError("DOCX table is empty")
    header = rows[0]
    data = rows[1:]
    return pd.DataFrame(data, columns=header)


def _load_bulk_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower() if filename else ""
    if name.endswith(".csv"):
        df = pd.read_csv(BytesIO(file_bytes))
    elif name.endswith(".xlsx"):
        df = pd.read_excel(BytesIO(file_bytes))
    elif name.endswith(".docx"):
        df = _load_docx_table(file_bytes)
    else:
        raise ValidationError("Unsupported file type. Use .docx, .xlsx, or .csv")

    df.columns = [_normalize_bulk_header(c) for c in df.columns]
    if set(df.columns) != set(BULK_HEADERS):
        raise ValidationError(
            "Invalid file headers. Expected: s.no, army number, rank, name, age, remarks"
        )

    df = df[BULK_HEADERS].copy()
    df = df.dropna(how="all")

    if df.empty:
        raise ValidationError("No candidate rows found")

    df["name"] = df["name"].where(df["name"].notna(), "")
    df["name"] = df["name"].astype(str).str.strip()
    df["s.no"] = pd.to_numeric(df["s.no"], errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")

    df = df[(df["name"] != "") & (df["s.no"].notna()) & (df["age"].notna())]

    if df.empty:
        raise ValidationError("No valid candidate rows after validation")

    df["s.no"] = df["s.no"].astype(int)
    df["age"] = df["age"].astype(int)

    invalid_age = df[(df["age"] < 0) | (df["age"] > 45)]
    if not invalid_age.empty:
        raise ValidationError("Age must be between 0 and 45 for bulk registration")

    df["remarks"] = None
    # Default gender to 'M' if not provided elsewhere
    df["gender"] = "M"
    return df


def _assign_bulk_rfids(df: pd.DataFrame, start_seq: int) -> pd.DataFrame:
    def _age_group_order(age: int) -> int:
        if age <= 30:
            return 0
        if age <= 40:
            return 1
        if age <= 45:
            return 2
        return 3

    df = df.copy()
    df["_age_group_order"] = df["age"].apply(_age_group_order)
    if (df["_age_group_order"] == 3).any():
        raise ValidationError("Age out of range for RFID assignment")

    df = df.sort_values(["_age_group_order", "s.no"], ascending=[True, True]).reset_index(drop=True)
    df = df.drop(columns=["_age_group_order"])

    if start_seq < 0 or start_seq > 999:
        raise ValidationError("RFID sequence start must be between 0 and 999")
    if (start_seq + len(df) - 1) > 999:
        raise ValidationError("RFID sequence exceeds 999 for this bulk upload")

    seq = pd.Series(range(start_seq, start_seq + len(df)), index=df.index)
    df["rfid_seq"] = seq
    df["rfid_tag"] = df["rfid_seq"].apply(lambda n: f"{RFID_PREFIX}{int(n):03d}")
    return df


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
        age=cast(int, participant.age),
        gender=cast(str, participant.gender),
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


@app.post(f"{API_PREFIX}/races/{{race_id}}/bulk-upload")
async def bulk_upload_candidates(
    race_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    """
    Bulk upload candidates for a race and auto-assign RFIDs using pandas.
    """
    race = race_service.get_race(db=db, race_id=race_id)
    if getattr(race, "status", None) != RaceStatus.CREATED.value:
        raise ConflictError("Bulk upload is only allowed for races in 'created' status")

    if not file or not file.filename:
        raise ValidationError("Missing upload file")

    table_name = _safe_table_name(race)
    file_bytes = await file.read()

    df = _load_bulk_dataframe(file_bytes, file.filename)

    df["army number"] = df["army number"].apply(
        lambda value: str(value).strip() if pd.notna(value) else None
    )
    df["army number"] = df["army number"].replace("", None)

    skipped_duplicate_army_numbers = 0
    duplicate_mask = df["army number"].notna() & df["army number"].duplicated()
    if duplicate_mask.any():
        skipped_duplicate_army_numbers = int(duplicate_mask.sum())
        df = df[~duplicate_mask]

    # Determine RFID sequence start based on existing tags
    max_seq = 0
    try:
        rows = db.execute(
            text(f'SELECT rfid_tag FROM "{table_name}" WHERE race_id = :race_id'),
            {"race_id": race_id}
        ).fetchall()
        for row in rows:
            tag = getattr(row, "rfid_tag", None) or row[0]
            if not tag:
                continue
            tag_str = str(tag)
            if not validate_rfid_tag(tag_str):
                continue
            if not tag_str.startswith(RFID_PREFIX) or len(tag_str) != len(RFID_PREFIX) + 3:
                continue
            suffix = tag_str[-3:]
            if not suffix.isdigit():
                continue
            try:
                max_seq = max(max_seq, int(suffix))
            except Exception:
                continue
    except Exception:
        max_seq = 0

    existing_army_numbers = set()
    try:
        rows = db.execute(
            text(
                f'SELECT army_number FROM "{table_name}" '
                'WHERE race_id = :race_id AND army_number IS NOT NULL'
            ),
            {"race_id": race_id}
        ).fetchall()
        for row in rows:
            value = getattr(row, "army_number", None) or row[0]
            if value:
                existing_army_numbers.add(str(value).strip())
    except Exception:
        existing_army_numbers = set()

    skipped_existing_army_numbers = 0
    if existing_army_numbers:
        before_count = len(df)
        df = df[~df["army number"].isin(existing_army_numbers)]
        skipped_existing_army_numbers = before_count - len(df)

    if df.empty:
        raise ValidationError("No valid candidate rows after removing existing army numbers")

    df = _assign_bulk_rfids(df, max_seq + 1)

    key_record = fernet_manager.get_or_create_active_key(db)
    encryption_key_id = str(key_record.id)

    payloads = []
    for row in df.to_dict(orient="records"):
        name = str(row.get("name", "")).strip()
        age_raw = row.get("age")
        if age_raw is None:
            continue
        age_val = int(cast(int, age_raw))
        category = rfid_service._calculate_category(age_val)
        encrypted_name = fernet_manager.encrypt(name)

        s_no_raw = row.get("s.no")
        if s_no_raw is None:
            continue
        s_no_val = int(cast(int, s_no_raw))

        payloads.append({
            "id": str(uuid.uuid4()),
            "race_id": race_id,
            "rfid_tag": row.get("rfid_tag"),
            "s_no": s_no_val,
            "army_number": row.get("army number"),
            "rank": row.get("rank"),
            "remarks": None,
            "encrypted_name": encrypted_name,
            "age": age_val,
            "gender": "M",
            "category": category,
            "encryption_key_id": encryption_key_id,
        })

    if not payloads:
        raise ValidationError("No valid candidates to insert")

    insert_sql = text(
        f"""
        INSERT INTO "{table_name}"
        (id, race_id, rfid_tag, s_no, army_number, rank, remarks, encrypted_name, age, gender, category, encryption_key_id, registered_at)
        VALUES (:id, :race_id, :rfid_tag, :s_no, :army_number, :rank, :remarks, :encrypted_name, :age, :gender, :category, :encryption_key_id, NOW())
        """
    )

    try:
        db.execute(insert_sql, payloads)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception(f"Bulk upload failed for race {race_id}: {exc}")
        raise

    return create_success_response({
        "message": "Bulk upload completed",
        "inserted": len(payloads),
        "skipped_duplicate_army_numbers": skipped_duplicate_army_numbers,
        "skipped_existing_army_numbers": skipped_existing_army_numbers,
        "rfid_start": payloads[0]["rfid_tag"],
        "rfid_end": payloads[-1]["rfid_tag"],
    })



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
            SELECT id, race_id, rfid_tag, s_no, army_number, rank, remarks, encrypted_name, age, gender, category, registered_at, encryption_key_id,
                   start_time, mid_time, end_time, status 
            FROM "{table_name}"
            ORDER BY rfid_tag ASC
        '''
    else:
        query = f'''
            SELECT id, race_id, rfid_tag, s_no, army_number, rank, remarks, encrypted_name, age, gender, category, registered_at, encryption_key_id 
            FROM "{table_name}"
            ORDER BY rfid_tag ASC
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
            "s_no": getattr(row, "s_no", None),
            "army_number": getattr(row, "army_number", None),
            "rank": getattr(row, "rank", None),
            "remarks": getattr(row, "remarks", None),
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
            participant_data["mid_time"] = row.mid_time.isoformat() if getattr(row, "mid_time", None) else None
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
        elif timing_point == "mid":
            logger.info(f"[RFID_HIT] Routing to MID handler")
            return await _handle_rfid_mid(rfid_tag, db, hit_timestamp)
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


@app.post(f"{API_PREFIX}/rfid/bulk")
async def rfid_bulk_upload(
    payload: RFIDBulkRequest,
    db: Session = Depends(get_db_session)
):
    """
    Bulk RFID upload endpoint for buffered proxy data.

    - Resolves the started race (status = 'started')
    - Updates mid_time for reader_id=2 and end_time for reader_id=3
    - Does not require start_time to exist
    """
    try:
        race_row = db.execute(
            text("""
                SELECT id, name, table_name, status
                FROM races
                WHERE status = :status
                LIMIT 1
            """),
            {"status": RaceStatus.STARTED.value}
        ).fetchone()

        if not race_row:
            return create_success_response({
                "success": False,
                "message": "No started race found",
                "processed": 0,
                "updated_mid": 0,
                "updated_end": 0
            })

        race_name = getattr(race_row, "name")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"

        processed = 0
        updated_mid = 0
        updated_end = 0
        logger.info(f"[RFID_BULK] Processing {len(payload.entries)} entries for race {race_name} (table: {table_name})")

        for entry in payload.entries:
            processed += 1
            rfid_tag = entry.rfid.upper()
            logger.info(f"[RFID_BULK] Entry {processed}: rfid={rfid_tag}, reader_id={entry.reader_id}, timestamp={entry.timestamp}")

            try:
                event_time = parser.isoparse(entry.timestamp)
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except Exception as ts_err:
                logger.warning(f"[RFID_BULK] Failed to parse timestamp {entry.timestamp}: {ts_err}")
                event_time = get_current_timestamp_IST()

            if entry.reader_id == 2:
                result = cast(CursorResult, db.execute(
                    text(f'UPDATE "{table_name}" SET mid_time = :ts WHERE rfid_tag = :rfid AND mid_time IS NULL'),
                    {"ts": event_time, "rfid": rfid_tag}
                ))
                rowcount = int(result.rowcount) if result.rowcount else 0
                if rowcount:
                    updated_mid += rowcount
                    logger.info(f"[RFID_BULK] Updated mid_time for RFID {rfid_tag} (+{rowcount})")
                else:
                    logger.debug(f"[RFID_BULK] No update for mid_time RFID {rfid_tag} (already set or not found)")
            elif entry.reader_id == 3:
                result = cast(CursorResult, db.execute(
                    text(f'UPDATE "{table_name}" SET end_time = :ts WHERE rfid_tag = :rfid AND end_time IS NULL'),
                    {"ts": event_time, "rfid": rfid_tag}
                ))
                rowcount = int(result.rowcount) if result.rowcount else 0
                if rowcount:
                    updated_end += rowcount
                    logger.info(f"[RFID_BULK] Updated end_time for RFID {rfid_tag} (+{rowcount})")
                else:
                    # Log at INFO so operators can see when expected updates don't happen
                    logger.info(f"[RFID_BULK] No update for end_time RFID {rfid_tag} (already set or not found) in table {table_name}")
            else:
                # reader_id == 1 (start) or unknown: ignore for v2 timing
                logger.debug(f"[RFID_BULK] Skipping reader_id {entry.reader_id} (start or unknown)")
                continue

        db.commit()

        # Check if we should auto-end the race after processing bulk RFID data
        if updated_end > 0:
            race_id = str(getattr(race_row, "id"))
            await check_and_auto_end_race(race_id, table_name, db)

        return create_success_response({
            "success": True,
            "message": "Bulk RFID data processed",
            "processed": processed,
            "updated_mid": updated_mid,
            "updated_end": updated_end
        })
    except Exception as exc:
        logger.error(f"[RFID_BULK] Error processing bulk upload: {exc}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk RFID data"
        )


async def _handle_rfid_start(rfid_tag: str, db: Session, hit_timestamp: Optional[str] = None) -> dict:
    """
    Handle start line RFID hit.
    
    Logic:
    1. If race NOT started: no timing updates (legacy grace/status kept but not relied upon)
    2. If race IS started: set status='running' without altering start_time
    
    Args:
        rfid_tag: RFID tag ID
        db: Database session
        hit_timestamp: ISO timestamp from proxy/listener when RFID was detected
    
    Flow:
    1. Find the started race (status = 'started')
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
                current_time = get_current_timestamp_IST()
        else:
            current_time = get_current_timestamp_IST()
            # logger.debug(f"[RFID_START] No proxy timestamp provided; using backend time: {current_time}")
        
        # Find the started race
        query = text("""
            SELECT id, name, table_name, scheduled_date, status 
            FROM races 
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.STARTED.value}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_START] No started race found")
            response = RFIDHitResponse(
                success=False,
                message="No started race found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
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
        
        # For STARTED races, mark status as running but do not alter start_time
        if current_status != "running":
            db.execute(
                text(f'UPDATE "{table_name}" SET status = :status WHERE id = :pid'),
                {"status": "running", "pid": participant_id}
            )
            db.commit()

        response = RFIDHitResponse(
            success=True,
            message=f"Runner marked running (start_time not updated) in {race_name}",
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


def _coerce_datetime(value: Any, fallback_tz: Optional[tzinfo]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = parser.isoparse(str(value))
        except Exception:
            return None
    if dt.tzinfo is None and fallback_tz is not None:
        dt = dt.replace(tzinfo=fallback_tz)
    return dt


def _get_max_allowed_seconds(age: Optional[int], race_row: Any) -> Optional[float]:
    if age is None:
        return None
    if age <= 30:
        return getattr(race_row, "age_upto30_satisfactory", None)
    if age <= 40:
        return getattr(race_row, "age_upto40_satisfactory", None)
    return getattr(race_row, "age_40to45_satisfactory", None)


async def _handle_rfid_end(rfid_tag: str, db: Session, hit_timestamp: Optional[str] = None) -> dict:
    """
    Handle end line RFID hit.
    
    Logic:
    - Record end_time for the started race regardless of start_time
    - Do not require runner to be in 'running' status
    
    Args:
        rfid_tag: RFID tag ID
        db: Database session
        hit_timestamp: ISO timestamp from proxy/listener when RFID was detected
    
    Flow:
    1. Find started race (status='started')
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
                current_time = get_current_timestamp_IST()
        else:
            current_time = get_current_timestamp_IST()
            logger.debug(f"[RFID_END] No proxy timestamp provided; using backend time: {current_time}")
        
        # Find the started race
        query = text("""
            SELECT id, name, table_name, scheduled_date, status, start_time,
                   age_upto30_satisfactory, age_upto40_satisfactory, age_40to45_satisfactory
            FROM races 
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.STARTED.value}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_END] No started race found")
            response = RFIDHitResponse(
                success=False,
                message="No started race found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        race_id = str(getattr(race_row, "id"))
        race_name = getattr(race_row, "name")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"
        
        # logger.info(f"[RFID_END] Found started race: {race_name} (id={race_id}) - table: {table_name}")
        
        # Find the participant with this RFID
        participant_row = db.execute(
            text(f'SELECT id, status, start_time, mid_time, end_time, age FROM "{table_name}" WHERE rfid_tag = :rfid'),
            {"rfid": rfid_tag}
        ).fetchone()
        
        if not participant_row:
            logger.warning(f"[RFID_END] RFID {rfid_tag} not found in race {race_name}")
            response = RFIDHitResponse(
                success=False,
                message="Participant not found in started race",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        participant_id = str(getattr(participant_row, "id"))
        existing_end_time = getattr(participant_row, "end_time", None)
        
        # logger.info(f"[RFID_END] Found participant {participant_id} in {race_name} with status: {participant_status}, end_time: {existing_end_time}")
        
        # Check if end_time already exists
        if existing_end_time:
            logger.warning(f"[RFID_END] RFID {rfid_tag} already has end_time: {existing_end_time}")
            response = RFIDHitResponse(
                success=False,
                message="End time already recorded for this runner",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())
        
        mid_time = getattr(participant_row, "mid_time", None)
        participant_age = getattr(participant_row, "age", None)
        race_start_time = getattr(race_row, "start_time", None)
        participant_start_time = getattr(participant_row, "start_time", None)
        effective_start_time = participant_start_time or race_start_time

        fallback_tz = current_time.tzinfo
        effective_start_time = _coerce_datetime(effective_start_time, cast(Optional[tzinfo], fallback_tz))

        disqualify_reasons = []
        if mid_time is None:
            disqualify_reasons.append("mid_time missing")

        max_allowed_seconds = _get_max_allowed_seconds(participant_age, race_row)
        if effective_start_time and max_allowed_seconds is not None:
            try:
                duration_seconds = (current_time - effective_start_time).total_seconds()
                if duration_seconds > float(max_allowed_seconds):
                    disqualify_reasons.append("time limit exceeded")
            except Exception as e:
                logger.warning(f"[RFID_END] Failed to compute duration for {participant_id}: {e}")

        status_to_set = "disqualified" if disqualify_reasons else "completed"

        # Record end time with timestamp from proxy and set status accordingly
        db.execute(
            text(f'UPDATE "{table_name}" SET end_time = :ts, status = :status WHERE id = :pid'),
            {"ts": current_time, "status": status_to_set, "pid": participant_id}
        )
        db.commit()
        
        # logger.info(f"✓ Recorded end time for RFID {rfid_tag} in race {race_name}, status set to 'completed'")
        
        # Check if all participants now have end times, and auto-end the race if so
        await check_and_auto_end_race(race_id, table_name, db)
        
        disqualify_note = f" (disqualified: {', '.join(disqualify_reasons)})" if disqualify_reasons else ""
        response = RFIDHitResponse(
            success=True,
            message=f"End time recorded in {race_name}, status set to {status_to_set}{disqualify_note}",
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


async def check_and_auto_end_race(race_id: str, table_name: str, db: Session) -> bool:
    """
    Check if all registered participants in a race have end_time.
    If yes, auto-end the race by:
    1. Getting the maximum end_time from all participants
    2. Updating the race end_time and status to 'completed'
    
    Args:
        race_id: Race ID
        table_name: Participant table name
        db: Database session
    
    Returns:
        bool: True if race was auto-ended, False otherwise
    """
    try:
        # Count total registered participants
        total_count_result = db.execute(
            text(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
        ).fetchone()
        total_participants = int(getattr(total_count_result, "cnt", 0)) if total_count_result else 0
        
        if total_participants == 0:
            logger.debug(f"[AUTO_END] Race {race_id} has no participants yet")
            return False
        
        # Count participants with end_time
        completed_count_result = db.execute(
            text(f'SELECT COUNT(*) as cnt FROM "{table_name}" WHERE end_time IS NOT NULL')
        ).fetchone()
        completed_participants = int(getattr(completed_count_result, "cnt", 0)) if completed_count_result else 0
        
        logger.info(f"[AUTO_END] Race {race_id}: {completed_participants}/{total_participants} participants have end_time")
        
        # If all participants have end_time, auto-end the race
        if completed_participants > 0 and completed_participants == total_participants:
            logger.info(f"[AUTO_END] All participants finished! Auto-ending race {race_id}")
            
            # Get the maximum end_time as the race end time
            max_end_time_result = db.execute(
                text(f'SELECT MAX(end_time) as max_end FROM "{table_name}" WHERE end_time IS NOT NULL')
            ).fetchone()
            
            max_end_time = getattr(max_end_time_result, "max_end", None) if max_end_time_result else None
            
            if max_end_time:
                # Update race status to completed and set end_time
                db.execute(
                    text('UPDATE races SET status = :status, end_time = :ts WHERE id = :race_id'),
                    {
                        "status": RaceStatus.COMPLETED.value,
                        "ts": max_end_time,
                        "race_id": race_id
                    }
                )
                db.commit()
                logger.info(f"✓ Race {race_id} auto-ended at {max_end_time}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"[AUTO_END] Error checking/auto-ending race {race_id}: {e}", exc_info=True)
        db.rollback()
        return False



async def _handle_rfid_mid(rfid_tag: str, db: Session, hit_timestamp: Optional[str] = None) -> dict:
    """
    Handle mid-point RFID hit.

    Logic:
    - Record mid_time for the started race regardless of start_time
    """
    try:
        if hit_timestamp:
            try:
                current_time = parser.isoparse(hit_timestamp)
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except Exception as e:
                logger.warning(f"[RFID_MID] Failed to parse hit_timestamp '{hit_timestamp}': {e}; using current time")
                current_time = get_current_timestamp_IST()
        else:
            current_time = get_current_timestamp_IST()

        query = text("""
            SELECT id, name, table_name, scheduled_date, status
            FROM races
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.STARTED.value}).fetchone()

        if not race_row:
            logger.warning(f"[RFID_MID] No started race found")
            response = RFIDHitResponse(
                success=False,
                message="No started race found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        race_name = getattr(race_row, "name")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"

        participant_row = db.execute(
            text(f'SELECT id, mid_time FROM "{table_name}" WHERE rfid_tag = :rfid'),
            {"rfid": rfid_tag}
        ).fetchone()

        if not participant_row:
            response = RFIDHitResponse(
                success=False,
                message="Participant not found in started race",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        participant_id = str(getattr(participant_row, "id"))
        existing_mid_time = getattr(participant_row, "mid_time", None)

        if existing_mid_time:
            response = RFIDHitResponse(
                success=False,
                message="Mid time already recorded for this runner",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        db.execute(
            text(f'UPDATE "{table_name}" SET mid_time = :ts WHERE id = :pid'),
            {"ts": current_time, "pid": participant_id}
        )
        db.commit()

        response = RFIDHitResponse(
            success=True,
            message=f"Mid time recorded in {race_name}",
            rfid_tag=rfid_tag
        )
        return create_success_response(response.model_dump())
        
    except Exception as e:
        logger.error(f"[RFID_MID] Error processing mid RFID: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mid RFID: {str(e)}"
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
     - Do not assign start_time from RFID hits (start_time is race-derived)
     - Update status to 'running' only if race is started
    """  
    rfid_tag_raw = payload.rfid_tag or getattr(payload, "rfid", None)
    if not rfid_tag_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFID tag is required"
        )
    rfid_tag = rfid_tag_raw.upper()
    
    try:
        # Find started race only
        query = text("""
            SELECT id, name, table_name, scheduled_date, status 
            FROM races 
            WHERE status = :status
            LIMIT 1
        """)
        race_row = db.execute(query, {"status": RaceStatus.STARTED.value}).fetchone()
        
        if not race_row:
            logger.warning(f"[RFID_START] No started race found")
            response = RFIDHitResponse(
                success=False,
                message="No started race found",
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

        if race_status != RaceStatus.STARTED.value:
            response = RFIDHitResponse(
                success=True,
                message=f"Race not started; keeping status '{current_status}'",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        if current_status != "running":
            db.execute(
                text(f'UPDATE "{table_name}" SET status = :status WHERE id = :pid'),
                {"status": "running", "pid": participant_id}
            )
            db.commit()

        response = RFIDHitResponse(
            success=True,
            message=f"Runner marked running (start_time not updated) in {race_name}",
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
    3. Backend finds the started race for this RFID
    4. Backend assigns endTIME with current server timestamp (start_time not required)
    """
    
    rfid_tag_raw = payload.rfid_tag or getattr(payload, "rfid", None)
    if not rfid_tag_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFID tag is required"
        )
    rfid_tag = rfid_tag_raw.upper()
    
    try:
        race_row = db.execute(
            text("""
                SELECT id, name, table_name, start_time,
                       age_upto30_satisfactory, age_upto40_satisfactory, age_40to45_satisfactory
                FROM races
                WHERE status = :status
                LIMIT 1
            """),
            {"status": RaceStatus.STARTED.value}
        ).fetchone()

        if not race_row:
            response = RFIDHitResponse(
                success=False,
                message="No started race found",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        race_name = getattr(race_row, "name")
        table_name_value = getattr(race_row, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race_name}_participants"

        row = db.execute(
            text(f"SELECT id, end_time, mid_time, start_time, age FROM \"{table_name}\" WHERE rfid_tag = :rfid"),
            {"rfid": rfid_tag}
        ).fetchone()

        if not row:
            response = RFIDHitResponse(
                success=False,
                message="Participant not found in started race",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        existing_end = getattr(row, "end_time", None)
        if existing_end:
            response = RFIDHitResponse(
                success=False,
                message="End time already recorded",
                rfid_tag=rfid_tag
            )
            return create_success_response(response.model_dump())

        current_time = get_current_timestamp_IST()
        mid_time = getattr(row, "mid_time", None)
        participant_age = getattr(row, "age", None)
        race_start_time = getattr(race_row, "start_time", None)
        participant_start_time = getattr(row, "start_time", None)
        effective_start_time = _coerce_datetime(participant_start_time or race_start_time, current_time.tzinfo)

        disqualify_reasons = []
        if mid_time is None:
            disqualify_reasons.append("mid_time missing")

        max_allowed_seconds = _get_max_allowed_seconds(participant_age, race_row)
        if effective_start_time and max_allowed_seconds is not None:
            try:
                duration_seconds = (current_time - effective_start_time).total_seconds()
                if duration_seconds > float(max_allowed_seconds):
                    disqualify_reasons.append("time limit exceeded")
            except Exception as e:
                logger.warning(f"[RFID_END] Failed to compute duration for {rfid_tag}: {e}")

        status_to_set = "disqualified" if disqualify_reasons else "completed"

        db.execute(
            text(f"UPDATE \"{table_name}\" SET end_time = :ts, status = :status WHERE id = :pid"),
            {"ts": current_time, "status": status_to_set, "pid": str(getattr(row, "id", row[0]))}
        )
        db.commit()
        
        disqualify_note = f" (disqualified: {', '.join(disqualify_reasons)})" if disqualify_reasons else ""
        response = RFIDHitResponse(
            success=True,
            message=f"End time recorded, status set to {status_to_set}{disqualify_note}",
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


def _set_working_directory() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)


if __name__ == "__main__":
    import uvicorn
    freeze_support()
    _set_working_directory()

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    uvicorn.run(app, host=host, port=port, log_level="info")