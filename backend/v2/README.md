# Backend API v2 - FastAPI Marathon Management Service

## 📋 Overview

The Backend v2 is the core REST API service for the RFID Marathon Management System. It's built with FastAPI and manages all business logic including race lifecycle, participant registration, real-time RFID hit processing, and secure data handling.

**Key Characteristics:**
- **Framework:** FastAPI + Python 3.10+
- **Port:** 8000
- **Database:** PostgreSQL/Supabase with dynamic per-race tables
- **Authentication:** JWT (HS256, 15-min expiry)
- **Encryption:** Fernet (symmetric) for names, RSA 4096-bit for responses
- **ORM:** SQLAlchemy 2.0
- **Participants:** Supports 3000+ per race concurrently

---

## 🏗️ Architecture

### System Overview

```
        ┌─────────────────────────────────────┐
        │   Frontend / Controller Apps        │
        │   (Electron, Tkinter, etc.)         │
        └────────────┬──────────────────────┘
                     │
                     │ HTTP/REST
                     ▼
        ┌──────────────────────────────────┐
        │   Backend API v2 (Port 8000)     │
        │   - Authentication               │
        │   - Race Management              │
        │   - Participant CRUD             │
        │   - RFID Hit Processing          │
        │   - Encryption/Decryption        │
        └────────────┬─────────────────────┘
                     │
                     │ SQL
                     ▼
        ┌──────────────────────────────────┐
        │   PostgreSQL Database            │
        │   - Race Tables                  │
        │   - Dynamic Participant Tables   │
        │   - Encryption Keys              │
        │   - Nonce Cache (Replay Protect) │
        └──────────────────────────────────┘

    ┌─────────────────────────────────────┐
    │  RFID Listener/Proxy (Port 9090)    │
    │  Forwards RFID hits via HTTP        │
    │  POST /api/v2/rfid/bulk             │
    └────────────┬──────────────────────┘
                 │
                 └──→ /api/v2/rfid/hit
                      /api/v2/rfid/bulk
```

### Database Schema

```
PUBLIC SCHEMA:
├── races
│   ├── id (UUID, PK)
│   ├── race_name (String)
│   ├── category (Enum: BPET, CPT, PPT)
│   ├── status (Enum: CREATED, STARTED, COMPLETED)
│   ├── start_time (DateTime)
│   ├── created_at (DateTime)
│   └── configuration (JSON)
│
├── encryption_keys
│   ├── id (UUID, PK)
│   ├── race_id (UUID, FK → races)
│   ├── fernet_key (String - Base64)
│   └── rotation_date (DateTime)
│
└── nonce_cache
    ├── race_id (UUID, FK → races)
    ├── nonce (String, PK)
    ├── timestamp (DateTime)
    └── expires_at (DateTime)

DYNAMIC TABLES (per race):
race_{race_id}_participants:
├── id (UUID, PK)
├── bib_number (String)
├── name_encrypted (String - Fernet encrypted)
├── age_category (String: U18, 18-30, 30-40, etc.)
├── status (Enum: REGISTERED, STARTED, MID, FINISHED)
├── start_time (DateTime)
├── mid_time (DateTime)
├── end_time (DateTime)
├── rfid_tag (String - Indexed)
└── created_at (DateTime)
```

---

## 🚀 Quick Start

### Installation

```bash
# Navigate to backend directory
cd backend/v2

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup

Create `.env` file in `backend/v2/`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/marathon_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=marathon_db
DB_USER=postgres
DB_PASSWORD=password

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15

# RFID Listener
RFID_LISTENER_URL=http://localhost:9090
RFID_BULK_ENDPOINT=/api/v2/rfid/bulk

# Encryption
RSA_PUBLIC_KEY_PATH=./keys/public_key.pem
RSA_PRIVATE_KEY_PATH=./keys/private_key.pem
FERNET_KEY_ROTATION_DAYS=30

# Logging
LOG_LEVEL=INFO
LOG_FILE=backend.log
```

### Run the Service

```bash
# Development mode
python main.py

# With custom settings
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode (with gunicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

### Health Check

```bash
curl http://localhost:8000/api/v2/health
```

Expected response: `{"status": "ok"}`

---

## 📚 API Endpoints Reference

### Authentication

```
POST /api/v2/auth/login
├─ Body: {"username": "admin", "password": "password"}
└─ Response: {"access_token": "jwt_token", "token_type": "bearer"}

POST /api/v2/auth/logout
└─ Headers: Authorization: Bearer {token}
```

### Race Management

```
POST /api/v2/race/create
├─ Headers: Authorization: Bearer {token}
├─ Body: {
│   "race_name": "Marathon 2024",
│   "category": "BPET",
│   "start_time": "2024-01-01T09:00:00",
│   "rfid_config": {
│     "timing_points": ["START", "MID", "END"],
│     "dedup_window_ms": 5000
│   }
├─ Response: {"race_id": "uuid", "status": "CREATED"}
└─ Status: 201

GET /api/v2/race/{race_id}
├─ Headers: Authorization: Bearer {token}
├─ Response: Complete race object with statistics
└─ Status: 200

GET /api/v2/race/{race_id}/participants
├─ Headers: Authorization: Bearer {token}
├─ Query: ?status=STARTED&limit=100&offset=0
├─ Response: List of participant objects with timing data
└─ Status: 200

PATCH /api/v2/race/{race_id}/status
├─ Headers: Authorization: Bearer {token}
├─ Body: {"new_status": "STARTED"}
├─ Response: Updated race object
└─ Status: 200

GET /api/v2/race/list
├─ Headers: Authorization: Bearer {token}
├─ Response: All races with pagination
└─ Status: 200

DELETE /api/v2/race/{race_id}
├─ Headers: Authorization: Bearer {token}
└─ Status: 204

DELETE /api/v2/race/{race_id}/participants
└─ Status: 204 (Clears all participants)
```

### Participant Management

```
POST /api/v2/participant/register
├─ Headers: Authorization: Bearer {token}
├─ Body: {
│   "race_id": "uuid",
│   "name": "John Doe",
│   "age": 28,
│   "bib_number": "001",
│   "rfid": "EPC123456789"
├─ Response: {"participant_id": "uuid", "status": "REGISTERED"}
└─ Status: 201

POST /api/v2/participant/register/bulk
├─ Headers: Authorization: Bearer {token}
├─ Body: {
│   "race_id": "uuid",
│   "participants": [
│     {"name": "John", "age": 28, "rfid": "EPC123"},
│     {"name": "Jane", "age": 30, "rfid": "EPC456"}
│   ]
├─ Response: {"created": 2, "failed": 0, "rfid_mapping": {...}}
└─ Status: 201

GET /api/v2/participant/{participant_id}
├─ Headers: Authorization: Bearer {token}
├─ Response: Participant object (name encrypted)
└─ Status: 200

PATCH /api/v2/participant/{participant_id}
├─ Headers: Authorization: Bearer {token}
├─ Body: {"status": "FINISHED", "end_time": "2024-01-01T10:30:00"}
└─ Status: 200

GET /api/v2/participant/by-rfid/{rfid}
├─ Headers: Authorization: Bearer {token}
├─ Response: Participant data (RSA encrypted)
└─ Status: 200

DELETE /api/v2/participant/{participant_id}
└─ Status: 204
```

### RFID Processing

```
POST /api/v2/rfid/hit
├─ Headers: Authorization: Bearer {token}
├─ Body: {
│   "race_id": "uuid",
│   "rfid": "EPC123456789",
│   "timing_point": "START",
│   "reader_name": "reader-1",
│   "hit_timestamp": "2024-01-01T09:00:15.123Z"
├─ Response: {"status": "processed", "participant_id": "uuid"}
└─ Status: 200

POST /api/v2/rfid/bulk
├─ Headers: Authorization: Bearer {token}
├─ Body: {
│   "race_id": "uuid",
│   "hits": [
│     {"rfid": "EPC123", "timing_point": "START", "hit_timestamp": "..."},
│     {"rfid": "EPC456", "timing_point": "MID", "hit_timestamp": "..."}
│   ]
├─ Response: {"processed": 2, "failed": 0}
└─ Status: 200

GET /api/v2/rfid/stats/{race_id}
├─ Headers: Authorization: Bearer {token}
├─ Response: {
│   "total_hits": 150,
│   "by_timing_point": {"START": 50, "MID": 50, "END": 50}
│ }
└─ Status: 200
```

### Dashboard & Analytics

```
GET /api/v2/dashboard/races
├─ Headers: Authorization: Bearer {token}
├─ Response: Aggregated race statistics
└─ Status: 200

GET /api/v2/dashboard/race/{race_id}/stats
├─ Headers: Authorization: Bearer {token}
├─ Response: {
│   "total_registered": 100,
│   "total_started": 95,
│   "total_finished": 87,
│   "average_time": 1800
│ }
└─ Status: 200

GET /api/v2/dashboard/leaderboard/{race_id}
├─ Query: ?limit=50
├─ Response: Top finishers with times
└─ Status: 200
```

---

## 🔐 Security Implementation

### JWT Authentication

```python
# Flow:
1. POST /auth/login with credentials
2. Backend validates password (bcrypt)
3. Generate JWT token (HS256, 15-min expiry)
4. Client includes in all requests: Authorization: Bearer {token}
5. Backend validates token signature and expiry

# Token Structure:
{
  "sub": "username",
  "iat": 1234567890,
  "exp": 1234568790,
  "scopes": ["read", "write"]
}
```

### Name Encryption (Fernet)

```python
# Per-race symmetric encryption key stored in database
fernet_key = Fernet.generate_key()  # 32 bytes, Base64 encoded

# On participant registration:
encrypted_name = Fernet(fernet_key).encrypt(name.encode())

# On participant lookup:
decrypted_name = Fernet(fernet_key).decrypt(encrypted_name).decode()
```

### Response Encryption (RSA)

```python
# Public key deployed to frontend/clients
# Private key kept secure on backend

# On participant lookup by RFID:
response_data = {
  "participant_id": "...",
  "name": "John Doe",
  "status": "FINISHED"
}
encrypted_response = public_key.encrypt(json.dumps(response_data))
```

### Replay Attack Protection

```python
# Mechanism: Timestamp + Nonce
# Window: 60 seconds

# On RFID hit:
1. Extract hit_timestamp from request
2. Verify within 60-second window: |now - hit_timestamp| <= 60s
3. Extract nonce from request
4. Check nonce NOT in PostgreSQL nonce_cache
5. If valid, INSERT nonce + expiry_time (now + 120s)
6. Reject if duplicate nonce found

# Cleanup: Expired nonces auto-deleted by scheduler
```

---

## 📝 Core Services

### RaceService (`services/race_service.py`)

Handles race business logic:

```python
# Create race with dynamic table
create_race(race_name, start_time, category)

# Get race with aggregated stats
get_race(race_id)

# Update race status (CREATED → STARTED → COMPLETED)
update_race_status(race_id, new_status)

# Delete race and all related data
delete_race(race_id)

# Get paginated race list
list_races(skip, limit)
```

### RfidService (`services/rfid_service.py`)

Handles RFID and encryption:

```python
# Register participant with encrypted name
register_participant_with_rfid(race_id, name, age, rfid)

# Lookup participant by RFID
lookup_participant_by_rfid(race_id, rfid)

# Process RFID hit and update status
process_rfid_hit(race_id, rfid, timing_point)

# Auto-assign age category
_calculate_category(age)

# Encrypt/decrypt using race-specific Fernet key
_encrypt_name(race_id, name)
_decrypt_name(race_id, encrypted_name)
```

### DatabaseManager (`database/connection.py`)

PostgreSQL connection pooling:

```python
# Singleton pattern
DatabaseManager()
  ├─ Connection Pool: 20 base + 10 overflow
  ├─ Retry logic: 3 attempts with backoff
  ├─ SSL mode: configurable (disabled by default for dev)
  └─ Test connection on init
```

### Migrations (`database/migrations.py`)

Idempotent schema management:

```python
# Dynamic column addition per race
ensure_participant_time_columns(race_id)
  ├─ Adds: start_time
  ├─ Adds: mid_time
  └─ Adds: end_time

ensure_participant_status_column(race_id)
  └─ Adds: status (DEFAULT 'REGISTERED')
```

---

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_race_service.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Commands

#### 1. Authentication Tests

```bash
# Get token
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Response: {"access_token":"eyJhbGc...","token_type":"bearer"}
```

#### 2. Create Race

```bash
TOKEN="your-jwt-token"

curl -X POST http://localhost:8000/api/v2/race/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_name": "Marathon 2024",
    "category": "BPET",
    "start_time": "2024-01-01T09:00:00"
  }'
```

#### 3. Register Participants

```bash
# Single participant
curl -X POST http://localhost:8000/api/v2/participant/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race-uuid",
    "name": "John Doe",
    "age": 28,
    "bib_number": "001",
    "rfid": "EPC123456789"
  }'

# Bulk participants
curl -X POST http://localhost:8000/api/v2/participant/register/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race-uuid",
    "participants": [
      {"name":"John","age":28,"rfid":"EPC123"},
      {"name":"Jane","age":30,"rfid":"EPC456"}
    ]
  }'
```

#### 4. Process RFID Hits

```bash
# Single hit
curl -X POST http://localhost:8000/api/v2/rfid/hit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race-uuid",
    "rfid": "EPC123456789",
    "timing_point": "START",
    "reader_name": "reader-1",
    "hit_timestamp": "2024-01-01T09:00:15.123Z"
  }'

# Bulk hits
curl -X POST http://localhost:8000/api/v2/rfid/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race-uuid",
    "hits": [
      {"rfid":"EPC123","timing_point":"START","hit_timestamp":"2024-01-01T09:00:15Z"},
      {"rfid":"EPC456","timing_point":"MID","hit_timestamp":"2024-01-01T09:30:00Z"}
    ]
  }'
```

#### 5. Get Race Statistics

```bash
curl http://localhost:8000/api/v2/dashboard/race/{race_id}/stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔧 Configuration Reference

### Constants (`constants.py`)

```python
# JWT
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 15

# Password hashing
BCRYPT_COST = 12

# Replay protection
REPLAY_PROTECTION_WINDOW_SECONDS = 60
NONCE_EXPIRY_SECONDS = 120

# Database
DB_POOL_SIZE = 20
DB_POOL_OVERFLOW = 10
DB_POOL_TIMEOUT = 30

# RFID Processing
RFID_BULK_SIZE = 100  # Events per batch
RFID_CACHE_TIMEOUT = 5000  # milliseconds

# Age categories
AGE_CATEGORIES = {
  "U18": (0, 18),
  "18-30": (18, 30),
  "30-40": (30, 40),
  "40+": (40, 150)
}

# Race categories
RACE_CATEGORIES = ["BPET", "CPT", "PPT"]

# Service URLs
RFID_LISTENER_URL = "http://localhost:9090"
RFID_BULK_ENDPOINT = "/api/v2/rfid/bulk"
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Error:** `postgresql.psycopg.OperationalError: connection failed`

**Solutions:**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection manually
psql -h localhost -U postgres -d marathon_db

# Check DATABASE_URL format
# Should be: postgresql://user:password@host:port/dbname

# Verify credentials in .env
cat .env | grep DATABASE_URL
```

#### 2. JWT Token Invalid

**Error:** `Invalid authentication credentials` or `Token expired`

**Solutions:**
```bash
# Verify SECRET_KEY is set
echo $SECRET_KEY

# Re-authenticate to get new token
curl -X POST http://localhost:8000/api/v2/auth/login \
  -d '{"username":"admin","password":"admin"}'

# Check token expiry (15 minutes default)
# Tokens are time-limited, must login again if expired
```

#### 3. RFID Listener Not Connected

**Error:** `Timeout connecting to RFID Listener` or `Connection refused`

**Solutions:**
```bash
# Check RFID Listener is running
curl http://localhost:9090/health

# Verify RFID_LISTENER_URL in .env
grep RFID_LISTENER_URL .env

# Check firewall allows port 9090
netstat -ano | findstr 9090
```

#### 4. Encryption Key Not Found

**Error:** `FileNotFoundError: keys/public_key.pem`

**Solutions:**
```bash
# Check keys directory exists
ls -la keys/

# Generate new RSA keypair
python -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
with open('keys/private_key.pem', 'wb') as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

with open('keys/public_key.pem', 'wb') as f:
    f.write(private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))
"
```

#### 5. Participant Table Not Created

**Error:** `ProgrammingError: relation "race_abc123_participants" does not exist`

**Solutions:**
```bash
# Manually trigger migrations
python -c "from database.migrations import ensure_participant_time_columns; ensure_participant_time_columns('race_id')"

# Check existing tables
python -c "from sqlalchemy import inspect; inspector = inspect(db.engine); print(inspector.get_table_names())"
```

---

## 📊 Performance Tuning

### Database Indexes

The backend automatically creates indexes on:

```python
# Participant lookups
CREATE INDEX idx_participant_rfid ON race_{race_id}_participants(rfid_tag);

# Status queries
CREATE INDEX idx_participant_status ON race_{race_id}_participants(status);

# Time-based queries
CREATE INDEX idx_participant_start_time ON race_{race_id}_participants(start_time);
```

### Connection Pooling

```python
# Current Settings:
pool_size = 20        # Base connections
max_overflow = 10     # Additional connections when demand exceeds base
pool_timeout = 30     # Max wait time for connection from pool

# For high-traffic (1000+ hits/sec):
pool_size = 50
max_overflow = 20
```

### RFID Hit Batching

```python
# Batch RFID hits in v2 API (more efficient)
# Instead of 100 single hits:
bulk_hits = [
  {"rfid": "EPC123", "timing_point": "START", ...},
  {"rfid": "EPC456", "timing_point": "START", ...},
  ...
]
POST /api/v2/rfid/bulk  # 100x batch in 1 request
```

---

## 📚 Related Documentation

- **Main Project:** [../../README.md](../../README.md)
- **System Architecture:** [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Documentation Index:** [../../DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)
- **Full Backend Notes:** [../../BACKEND_V2_NOTES.txt](../../BACKEND_V2_NOTES.txt)

---

## 📦 File Structure

```
backend/v2/
├── main.py                 ← FastAPI app (1800+ lines)
├── models.py              ← Pydantic + SQLAlchemy models
├── constants.py           ← Configuration constants
├── requirements.txt       ← Python dependencies
├── README.md              ← This file
├── Dockerfile             ← Container image
├── database/
│   ├── __init__.py
│   ├── connection.py      ← DatabaseManager singleton
│   └── migrations.py      ← Schema migrations
├── services/
│   ├── __init__.py
│   ├── race_service.py    ← Race business logic
│   ├── rfid_service.py    ← RFID operations
│   ├── fernet_manager.py  ← Symmetric encryption
│   └── rsa_manager.py     ← Asymmetric encryption
├── middleware/
│   ├── auth_middleware.py ← JWT validation
│   └── __pycache__/
├── keys/
│   ├── public_key.pem     ← RSA public key
│   └── private_key.pem    ← RSA private key (keep secure!)
├── tests/
│   ├── test_race_service.py
│   ├── test_rfid_service.py
│   └── test_auth.py
└── __pycache__/
```

---

**Last Updated:** March 2024  
**Version:** 2.0  
**Status:** Production Ready
