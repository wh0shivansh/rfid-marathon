"""
RFID Marathon Management System - FastAPI Application
Security Level: Military-grade
Last Updated: January 21, 2026

Main entrypoint for the backend API with:
- Strict authentication (JWT + replay protection)
- Encryption (Fernet at rest, RSA for responses)
- Idempotent migrations on startup
- Rate limiting and immutable audit logging
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, cast

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from constants import API_PREFIX, RaceStatus, TimingPoint, ErrorMessages, FeatureFlags
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
from services.timing_service import get_timing_service
from services.rsa_manager import get_rsa_manager
from services.fernet_manager import get_fernet_manager
from middleware.rate_limiter import get_rate_limiter
from middleware.audit_logger import get_audit_logger
from middleware.auth_middleware import get_auth_middleware, get_current_user
from models import (
    LoginRequest,
    RaceCreateRequest,
    RaceUpdateRequest,
    ParticipantRegisterRequest,
    ParticipantLookupRequest,
    TimingRecordRequest,
    SyncHandshakeRequest,
    RaceResponse,
    DashboardDataResponse,
    ParticipantResponse,
    TimingRecordResponse,
    SyncHandshakeResponse,
)
from basefunctions import (
    create_success_response,
    create_error_response,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ApplicationError,
)

logger = logging.getLogger("rfid-marathon")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database and running migrations...")
    initialize_database()
    run_migrations()
    logger.info("Startup complete")
    yield
    logger.info("Shutting down services...")
    shutdown_database()
    logger.info("Shutdown complete")


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
timing_service = get_timing_service()
rsa_manager = get_rsa_manager()
fernet_manager = get_fernet_manager()
rate_limiter = get_rate_limiter()
audit_logger = get_audit_logger()
auth_middleware = get_auth_middleware()

# CORS configuration (restrict to desktop app origins; adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"] if FeatureFlags.ENFORCE_HTTPS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================================
# GLOBAL MIDDLEWARE (Rate limiting, audit logging, error handling)
# ============================================================================

@app.middleware("http")
async def security_pipeline(request: Request, call_next):
    """Global middleware for rate limiting and audit logging."""
    start_time = time.time()

    # Rate limiting
    try:
        await rate_limiter(request)
    except HTTPException as exc:
        response = JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                error_code="RATE_LIMIT_EXCEEDED",
                message=str(exc.detail)
            )
        )
        await audit_logger.log_request(request, response, time.time() - start_time)
        return response

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

    # Audit logging (best-effort)
    try:
        await audit_logger.log_request(
            request=request,
            response=response,
            processing_time=time.time() - start_time
        )
    except Exception:
        logger.warning("Audit logging failed but request completed")

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
            if user:
                logger.info(f"Case-insensitive username match: provided={payload.username!r}, matched={user.username!r}")
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
            from models import TimingRecord
            
            started_count = db.query(func.count(func.distinct(TimingRecord.participant_id))).filter(
                TimingRecord.race_id == race.id,
                TimingRecord.timing_point == TimingPoint.START
            ).scalar() or 0
            
            finished_count = db.query(func.count(func.distinct(TimingRecord.participant_id))).filter(
                TimingRecord.race_id == race.id,
                TimingRecord.timing_point == TimingPoint.END
            ).scalar() or 0
            
            started_today += started_count
            finished_today += finished_count
    
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


def _fetch_participants_for_race(db: Session, race, fernet_mgr, rsa_mgr):
    participants = []
    table_name = _safe_table_name(race)
    try:
        rows = db.execute(
            text(
                f'''
                SELECT id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at, encryption_key_id 
                FROM "{table_name}"
                '''
            )
        ).fetchall()
    except Exception as exc:
        logger.debug(f"Could not query participants for race {race.id} table {table_name}: {exc}")
        return participants

    for row in rows:
        try:
            key = fernet_mgr.get_key_by_id(str(row.encryption_key_id))
        except Exception as exc:
            logger.debug(f"Could not fetch Fernet key for {row.encryption_key_id}: {exc}")
            key = None

        participants.append({
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
        })
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
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    race = race_service.get_race(db=db, race_id=race_id)
    participants = _fetch_participants_for_race(db, race, fernet_manager, rsa_manager)
    return create_success_response(participants)


# ============================================================================
# TIMING ENDPOINTS (IMMUTABLE)
# ============================================================================

@app.post(f"{API_PREFIX}/timing/start")
async def record_start(
    payload: TimingRecordRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    if payload.timing_point != TimingPoint.START:
        raise ValidationError("timing_point must be 'start'")

    timing_record = timing_service.record_timing(
        db=db,
        race_id=payload.race_id,
        rfid_tag=payload.rfid_tag,
        timing_point=payload.timing_point,
        recorded_at_str=payload.timestamp,
        device_id=payload.device_id
    )

    response = TimingRecordResponse(
        id=str(timing_record.id),
        race_id=str(timing_record.race_id),
        participant_id=str(timing_record.participant_id),
        rfid_tag=str(timing_record.rfid_tag),
        timing_point=TimingPoint(cast(str, timing_record.timing_point)),
        recorded_at=timing_record.recorded_at.isoformat(),
        device_id=str(timing_record.device_id),
        synced=cast(bool, timing_record.synced)
    )
    return create_success_response(response.model_dump())


@app.post(f"{API_PREFIX}/timing/end")
async def record_end(
    payload: TimingRecordRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    if payload.timing_point != TimingPoint.END:
        raise ValidationError("timing_point must be 'end'")

    timing_record = timing_service.record_timing(
        db=db,
        race_id=payload.race_id,
        rfid_tag=payload.rfid_tag,
        timing_point=payload.timing_point,
        recorded_at_str=payload.timestamp,
        device_id=payload.device_id
    )

    response = TimingRecordResponse(
        id=str(timing_record.id),
        race_id=str(timing_record.race_id),
        participant_id=str(timing_record.participant_id),
        rfid_tag=str(timing_record.rfid_tag),
        timing_point=TimingPoint(cast(str, timing_record.timing_point)),
        recorded_at=timing_record.recorded_at.isoformat(),
        device_id=str(timing_record.device_id),
        synced=cast(bool, timing_record.synced)
    )
    return create_success_response(response.model_dump())


# ============================================================================
# SYNC ENDPOINTS (OFFLINE HANDSHAKE)
# ============================================================================

@app.post(f"{API_PREFIX}/sync/handshake")
async def sync_handshake(
    payload: SyncHandshakeRequest,
    db: Session = Depends(get_db_session),
    _user=Depends(get_current_user)
):
    result = timing_service.confirm_sync(
        db=db,
        timing_record_ids=payload.timing_record_ids
    )
    handshake = SyncHandshakeResponse(
        confirmed_ids=result["confirmed_ids"],
        failed_ids=result["failed_ids"],
        timestamp=result["timestamp"]
    )
    return create_success_response(handshake.model_dump())


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
