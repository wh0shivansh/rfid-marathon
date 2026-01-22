# Secure RFID Marathon Management System

**Security Level:** Military-grade, audit-ready  
**Stack:** FastAPI (Python) + PostgreSQL (Supabase) + Electron + React + Vite  
**Encryption:** Fernet (at rest), RSA-4096 (API responses), HTTPS in transit  
**Authentication:** JWT + timestamp/nonce replay protection  
**Offline-first:** SQLite cache with handshake-based sync  
**Status:** Backend Complete ✅ | Frontend In Progress 🚧

---

## Architecture

- **Backend**: FastAPI, stateless, Dockerized, connects to Supabase PostgreSQL with enforced SSL (sslmode=require).
- **Frontend**: Electron + React + Vite desktop app with offline SQLite, RSA decryption, and sync retry.
- **Data Flow**: RFID scans → local cache → signed API requests → backend validation → encrypted storage.

```
frontend (Electron + React)
  │  (HTTPS + JWT + RSA)
  ▼
backend (FastAPI)
  │  (SSL enforced)
  ▼
Supabase PostgreSQL (encrypted names via Fernet)
```

Key flows:
- **Registration**: RFID scan → name encrypted (Fernet) → stored; RSA-encrypted name returned to UI.
- **Timing**: Start/end timestamps immutable; duplicates rejected; replay-protected.
- **Sync**: Offline records queued in SQLite → handshake API confirms persistence → local delete.

---

## Implementation Status

### ✅ Backend (Complete)

**Core Services:**
- ✅ Race Management (CRUD operations, status validation)
- ✅ Participant Service (registration, lookup, encrypted names)
- ✅ RFID Mapping (unique constraints per race)
- ✅ Timing Service (immutable records, duplicate detection)
- ✅ Encryption (Fernet for DB, RSA for API responses)
- ✅ Authentication (JWT with replay protection, bcrypt password hashing)

**Infrastructure:**
- ✅ Database migrations with idempotent schema creation
- ✅ SSL-enforced PostgreSQL connection pooling
- ✅ Middleware (auth validation, rate limiting, audit logging)
- ✅ Docker containerization with multi-stage builds
- ✅ Health checks and monitoring endpoints

**Security:**
- ✅ Timestamp + nonce replay attack prevention (60-second window)
- ✅ Rate limiting (60 requests/minute per IP)
- ✅ Immutable audit log with IP tracking
- ✅ Input validation via Pydantic schemas
- ✅ SQL injection protection (SQLAlchemy ORM)

### 🚧 Frontend (In Progress)

**Completed:**
- ✅ Vite + React + Electron setup
- ✅ SQLite schema for offline cache
- ✅ Service layer architecture (API, Database, Encryption, Sync)
- ✅ Environment configuration structure

**Pending:**
- ⏳ UI components implementation
- ⏳ RFID scanning integration
- ⏳ Login and race selection workflows
- ⏳ Registration loop (continuous scanning)
- ⏳ Timing device interfaces (Device 1 & 2)
- ⏳ Results dashboard with decryption
- ⏳ Sync queue management with retry logic

---

## Security Model

### Transport Layer
- **HTTPS**: All API communication encrypted
- **SSL/TLS**: Database connections require SSL (sslmode=require)
- **CORS**: Configured for Electron app origin only

### Authentication & Authorization
- **JWT**: HS256 algorithm, 15-minute access tokens
- **Password Hashing**: Bcrypt with 12 rounds
- **Replay Protection**: Headers `X-Timestamp` (ISO 8601) + `X-Nonce` (64-char hex)
- **Nonce Tracking**: Database-backed cache with 60-second window, automatic cleanup

### Data Protection
| Data Type | At Rest | In Transit | Decryption |
|-----------|---------|------------|------------|
| Participant Names | Fernet (symmetric) | RSA-4096 (asymmetric) | Frontend private key |
| RFID Tags | Plaintext* | HTTPS | N/A |
| Passwords | Bcrypt (one-way) | HTTPS | Never decrypted |
| JWT Tokens | N/A | HTTPS | Backend validation only |

*RFID tags stored as plaintext per requirement (needed for quick lookups)

### Immutability Guarantees
- **Timing Records**: Database unique constraint `(race_id, participant_id, timing_point)` prevents updates
- **Audit Log**: Insert-only table with no UPDATE/DELETE permissions
- **Key Rotation**: Tracked in `encryption_keys` table with version history

---

## Deployment (Docker)

### Quick Start

```bash
cd backend

# 1. Copy and configure environment
cp .env.template .env
nano .env  # Add Supabase credentials

# 2. Generate encryption keys
python - <<'PY'
from cryptography.fernet import Fernet
import secrets
print('JWT_SECRET_KEY=' + secrets.token_hex(32))
print('FERNET_MASTER_KEY=' + Fernet.generate_key().decode())
PY

# 3. Build and run
docker-compose up --build

# 4. Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", "database": "connected", "encryption": "ready"}
```

### Environment Variables (Required)

```bash
# Database (Supabase)
SUPABASE_DB_HOST=aws-0-us-west-1.pooler.supabase.com
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.xxxxx
SUPABASE_DB_PASSWORD=your_secure_password

# Security Keys
JWT_SECRET_KEY=<64-char-hex>
FERNET_MASTER_KEY=<44-char-base64>

# Server (optional, defaults provided)
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_ENV=production
```

Backend auto-runs migrations on startup. Check logs:
```bash
docker-compose logs backend | grep "Migration"
```

---

## Project Structure

```
rfid-marathon/
├── backend/                  # ✅ FastAPI Backend (Complete)
│   ├── constants.py          # Global enums and constants
│   ├── basefunctions.py      # Shared utilities (validators, formatters)
│   ├── models.py             # Pydantic schemas + SQLAlchemy models
│   ├── main.py               # FastAPI app with middleware stack
│   │
│   ├── database/
│   │   ├── connection.py     # SSL-enforced connection pool
│   │   └── migrations.py     # Idempotent schema creation
│   │
│   ├── services/
│   │   ├── race/             # Race CRUD and status management
│   │   ├── participant/      # Registration and lookup
│   │   ├── rfid/             # RFID-to-participant mapping
│   │   ├── timing/           # Immutable timing records
│   │   ├── encryption/       # Fernet + RSA managers
│   │   ├── auth/             # JWT + password hashing
│   │   └── sync/             # Offline handshake confirmation
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py   # JWT validation + replay protection
│   │   ├── rate_limiter.py      # IP-based rate limiting
│   │   └── audit_logger.py      # Immutable audit trail
│   │
│   ├── Dockerfile            # Multi-stage production build
│   ├── docker-compose.yml    # Orchestration with health checks
│   └── requirements.txt      # Python dependencies
│
├── frontend/                 # 🚧 Electron + React (In Progress)
│   ├── src/
│   │   ├── main.js           # Electron main process
│   │   ├── renderer.js       # React app entry
│   │   ├── services/         # API, Database, Encryption, Sync
│   │   └── components/       # React UI (to be implemented)
│   │
│   ├── database/
│   │   └── schema.sql        # SQLite offline cache schema
│   │
│   └── package.json          # Node dependencies
│
├── README.md                 # This file
├── sprint.md                 # Sprint plan with progress tracking
└── notes.txt                 # Developer notes
```

---

## API Endpoints (Backend)

### Health & Crypto
- `GET /health` - System health check
- `GET /api/v1/crypto/public-key` - Get RSA public key for encryption

### Authentication
- `POST /api/v1/auth/login` - Login with username/password, returns JWT

### Race Management
- `POST /api/v1/race` - Create race
- `GET /api/v1/race/{race_id}` - Get race details
- `GET /api/v1/race` - List all races
- `PATCH /api/v1/race/{race_id}` - Update race (status, etc.)

### Participant Operations
- `POST /api/v1/participant/register` - Register participant (returns RSA-encrypted name)
- `POST /api/v1/participant/lookup` - Lookup by RFID tag

### Timing Operations
- `POST /api/v1/timing/start` - Record start time (Device 1)
- `POST /api/v1/timing/end` - Record end time (Device 2)
- `GET /api/v1/timing/race/{race_id}` - Get all timing records for race

### Offline Sync
- `POST /api/v1/sync/handshake` - Confirm synced records (returns confirmed/failed IDs)

---

## Data Flow (Detailed)

### 1. Authentication Flow
```
Frontend → POST /auth/login
  Headers: X-Timestamp, X-Nonce
  Body: {username, password, timestamp, nonce}

Backend validates:
  ✓ Timestamp within ±60 seconds
  ✓ Nonce not in cache (replay check)
  ✓ Password hash matches (bcrypt)

Backend returns:
  {access_token, expires_in, user_id}

All subsequent requests:
  Authorization: Bearer <token>
```

### 2. Registration Flow
```
Frontend (Offline Mode):
  1. Scan RFID → prompt for name
  2. Insert into local SQLite (participants table)
  3. Add to sync_queue with action="register"

Frontend (Online Mode):
  1. POST /participant/register {race_id, rfid_tag, name, ...}
  2. Backend: Encrypt name with Fernet → store in DB
  3. Backend: Encrypt name with RSA → return to client
  4. Frontend: Decrypt with private key → display confirmation

Sync Process:
  1. Queue processor checks connectivity
  2. POST queued registrations to backend
  3. Receive encrypted names
  4. POST /sync/handshake with record IDs
  5. Delete confirmed records from local queue
```

### 3. Timing Flow (Immutable)
```
Device 1 (Start):
  1. Scan RFID at start line
  2. Record timestamp + device_id
  3. POST /timing/start {race_id, rfid_tag, timestamp, device_id}
  4. Backend: Unique constraint enforced (race_id, participant_id, "start")
  5. Frontend: Display "Started" status

Device 2 (End):
  1. Scan RFID at finish line
  2. Record timestamp + device_id
  3. POST /timing/end {race_id, rfid_tag, timestamp, device_id}
  4. Backend: Calculate duration if start exists
  5. Frontend: Display "Finished" + duration
```

---

## Security Features (Implemented)

✅ **SSL/TLS Enforcement** - Database connection requires SSL  
✅ **Password Hashing** - Bcrypt 12 rounds  
✅ **JWT Authentication** - HS256, 15-minute expiration  
✅ **Replay Protection** - Timestamp (±60s) + nonce validation  
✅ **Rate Limiting** - 60 requests/minute per IP  
✅ **Audit Logging** - Immutable log with IP, user, timestamp  
✅ **Encryption at Rest** - Fernet for participant names  
✅ **Encryption in Transit** - HTTPS + RSA for API responses  
✅ **Timing Immutability** - Database constraints prevent updates  
✅ **Input Validation** - Pydantic schemas on all endpoints  
✅ **SQL Injection Protection** - SQLAlchemy ORM with parameterized queries  

---

## Testing

### Backend
```bash
cd backend

# Unit tests
pytest -v

# Security scan
bandit -r . -ll

# Dependency vulnerability check
safety check

# Coverage report
pytest --cov=. --cov-report=html
```

### Frontend (To Be Implemented)
```bash
cd frontend

# Unit tests
npm test

# E2E tests
npm run test:e2e
```

---

## Known Limitations & Future Work

### Current Limitations
1. **Frontend UI**: Core components not yet implemented
2. **RFID Hardware Integration**: Requires physical device testing
3. **Key Rotation**: Manual process (HSM integration planned)
4. **Backup Strategy**: Manual PostgreSQL dumps (automated backups planned)

### Planned Enhancements
- [ ] Hardware security module (HSM) for key storage
- [ ] Automated database backups to S3
- [ ] Real-time WebSocket updates for timing dashboard
- [ ] Mobile app for race officials
- [ ] Biometric authentication option
- [ ] Multi-language support

---

## Troubleshooting

### Backend Won't Start
```bash
# Check Supabase connection
docker-compose logs backend | grep "Database"

# Verify SSL
psql "postgresql://user:pass@host:port/dbname?sslmode=require"

# Check migrations
docker-compose exec backend python -c "from database.migrations import run_migrations; run_migrations()"
```

### JWT Authentication Fails
```bash
# Verify secret is set
docker-compose exec backend env | grep JWT_SECRET_KEY

# Check token expiration
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/race
```

### Rate Limiting Triggered
```bash
# Clear rate limit cache (Redis if implemented, or restart)
docker-compose restart backend
```

---

## Default Credentials

**⚠️ CHANGE IMMEDIATELY IN PRODUCTION**

```
Username: admin
Password: AdminPassword123!
```

Create in database:
```python
from services.auth.password_manager import PasswordManager
pm = PasswordManager()
hashed = pm.hash_password("AdminPassword123!")
# Insert into users table with username='admin'
```

---

## Contributing

1. Follow sprint plan in `sprint.md`
2. All PRs require security review
3. Test coverage must be >80%
4. No secrets in code (use .env)
5. Document all API changes in README

---

## License

Proprietary - Innogative © 2026

---

**Last Updated**: January 22, 2026  
**Version**: 1.0.0 (Backend Complete)  
**Security Audit**: Pending (Sprint 8)
