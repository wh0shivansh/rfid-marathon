# RFID Marathon Management System - Backend

## 🎯 Overview

Production-grade, military-spec backend for RFID-based marathon race management with end-to-end encryption, immutable timing records, and offline-first synchronization.

**Security Level**: Military-grade, Audit-ready  
**Technology Stack**: FastAPI + PostgreSQL (Supabase) + Docker  
**Encryption**: Fernet (DB) + RSA-4096 (API responses)  
**Authentication**: JWT + Timestamp-based Replay Protection

---

## 🏗️ Architecture

### Layered Architecture

```
backend/
├── constants.py           # Global constants & enums
├── basefunctions.py       # Shared utilities
├── models.py              # Pydantic & SQLAlchemy models
├── main.py                # FastAPI application
│
├── database/              # Database layer
│   ├── connection.py      # SSL-enforced connection pool
│   └── migrations.py      # Idempotent schema creation
│
├── services/              # Business logic (isolated)
│   └── ...py              # All services in separate py file
│
├── middleware/            # Request interceptors
│   ├── auth_middleware.py    # JWT validation
│   ├── rate_limiter.py       # DOS protection
│   └── audit_logger.py       # Immutable audit log
│
├── Dockerfile             # Multi-stage container
├── docker-compose.yml     # Orchestration
└── .env.template          # Configuration template
```

---

## 🔐 Security Model

### Data Protection

| Data Type | Storage Encryption | Transit Encryption | Decryption |
|-----------|-------------------|-------------------|------------|
| Participant Names | Fernet (symmetric) | RSA-4096 (public key) | Frontend (private key) |
| RFID Tags | **Plaintext** (requirement) | HTTPS | N/A |
| Credentials | Bcrypt (12 rounds) | HTTPS | One-way hash |
| Tokens | JWT (HS256) | HTTPS | Backend validation |

### Authentication Flow

```
1. Frontend → POST /auth/login
   Headers: X-Timestamp, X-Nonce
   Body: {username, password, timestamp, nonce}

2. Backend validates:
   ✓ Timestamp within 60-second window
   ✓ Nonce not reused (replay protection)
   ✓ Password hash matches (bcrypt)

3. Backend returns:
   {access_token, expires_in, user_id}

4. All subsequent requests:
   Authorization: Bearer <access_token>
```

### Replay Attack Protection

- **X-Timestamp**: ISO 8601 timestamp (must be within ±60 seconds)
- **X-Nonce**: Unique 64-character hex string
- Nonces cached in database with expiration
- Automatic cleanup of expired nonces

---

## 📊 Database Schema

### Core Tables

**users** - Authentication  
**races** - Race definitions  
**participants** - Encrypted participant data  
**rfid_mapping** - RFID → Participant lookup  
**timing_records** - **IMMUTABLE** timing events  
**audit_log** - **IMMUTABLE** security audit trail  
**nonce_cache** - Replay attack prevention  
**encryption_keys** - Key rotation tracking  

### Key Constraints

```sql
-- IMMUTABILITY: Timing records cannot be updated
UNIQUE (race_id, participant_id, timing_point)

-- RFID uniqueness per race
UNIQUE (race_id, rfid_tag)

-- SSL enforcement
sslmode=require (connection string)
```

---

## 🚀 API Endpoints

### Authentication

```
POST /api/v1/auth/login
  Request: {username, password, timestamp, nonce}
  Response: {access_token, expires_in}
```

### Race Management

```
POST   /api/v1/race          # Create race
GET    /api/v1/race/{id}     # Get race
GET    /api/v1/race          # List races
PATCH  /api/v1/race/{id}     # Update race
```

### Participant Registration

```
POST /api/v1/participant/register
  Request: {race_id, rfid_tag, name, age, gender, category}
  Response: {id, encrypted_name_rsa}
  
POST /api/v1/participant/lookup
  Request: {race_id, rfid_tag}
  Response: {encrypted_name_rsa, age, gender, ...}
```

### Timing Operations

```
POST /api/v1/timing/start
  Request: {race_id, rfid_tag, timestamp, device_id}
  Response: {id, recorded_at, synced}
  
POST /api/v1/timing/end
  Request: {race_id, rfid_tag, timestamp, device_id}
  Response: {id, recorded_at, synced}
```

### Offline Sync

```
POST /api/v1/sync/handshake
  Request: {timing_record_ids: []}
  Response: {confirmed_ids: [], failed_ids: []}
```

---

## 🐳 Docker Deployment

### Environment Variables (Required)

```bash
# Database (Supabase)
SUPABASE_DB_HOST=aws-0-us-west-1.pooler.supabase.com
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.xxxxx
SUPABASE_DB_PASSWORD=your_secure_password

# Security
JWT_SECRET_KEY=<64-char-hex-string>
FERNET_MASTER_KEY=<44-char-base64-string>

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_ENV=production
```

### Quick Start

```bash
# 1. Copy environment template
cp .env.template .env

# 2. Edit .env with your Supabase credentials
nano .env

# 3. Build and run
docker-compose up --build

# 4. Verify health
curl http://localhost:8000/health
```

### Production Deployment

```bash
# Build production image
docker build -t rfid-backend:1.0.0 .

# Run with health checks
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f backend

# Database migrations (automatic on startup)
# Check logs for migration status
```

---

## 🔧 Development

### Prerequisites

- Python 3.11+
- PostgreSQL (or Supabase account)
- Docker & Docker Compose

### Local Setup (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SUPABASE_DB_HOST=...
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export FERNET_MASTER_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Run migrations
python -c "from database.migrations import run_migrations; run_migrations()"

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Generate Encryption Keys

```python
# JWT Secret
import secrets
print(secrets.token_hex(32))

# Fernet Master Key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## 🛡️ Security Features

### Implemented

✅ **SSL/TLS Enforcement** - All database connections use SSL  
✅ **Password Hashing** - Bcrypt with 12 rounds  
✅ **JWT Tokens** - Short-lived (15 min) access tokens  
✅ **Replay Protection** - Timestamp + nonce validation  
✅ **Rate Limiting** - 60 requests/minute per IP  
✅ **Audit Logging** - Immutable log of all actions  
✅ **Encryption at Rest** - Fernet for participant names  
✅ **Encryption in Transit** - HTTPS + RSA for API responses  
✅ **Timing Immutability** - Database constraints prevent updates  
✅ **Input Validation** - Pydantic schemas on all endpoints  

### Attack Mitigation

| Attack Vector | Mitigation |
|--------------|------------|
| SQL Injection | Parameterized queries (SQLAlchemy ORM) |
| Replay Attacks | Timestamp + nonce validation |
| Brute Force | Rate limiting + account lockout |
| DOS | Rate limiting + connection pooling |
| Man-in-the-Middle | SSL/TLS enforcement |
| Token Theft | Short expiration + refresh tokens |
| Data Breach | Encryption at rest (Fernet) |

---

## 📈 Performance

### Optimizations

- **Connection Pooling**: 20 connections + 10 overflow
- **Database Indexes**: All foreign keys and lookup fields
- **Query Optimization**: Eager loading for relationships
- **Caching**: Nonce cache for replay protection
- **Async Operations**: FastAPI async endpoints

### Scalability

- **Stateless Design**: No server-side sessions
- **Horizontal Scaling**: Multiple backend containers
- **Database**: Supabase handles scaling
- **CDN**: Serve static assets separately

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/ -v

# Test specific module
pytest tests/test_encryption.py -v

# Coverage report
pytest --cov=. --cov-report=html

# Security scan
bandit -r . -ll

# Dependency check
safety check
```

---

## 📝 API Response Format

### Success Response

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... },
  "timestamp": "2026-01-21T12:00:00Z"
}
```

### Error Response

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid input data",
  "details": { "field": "error_description" },
  "timestamp": "2026-01-21T12:00:00Z"
}
```

---

## 🔍 Monitoring & Logging

### Log Levels

- **DEBUG**: Detailed information for diagnostics
- **INFO**: Confirmation of expected operations
- **WARNING**: Unexpected but handled situations
- **ERROR**: Serious issues affecting functionality
- **CRITICAL**: System-level failures

### Audit Trail

All actions logged to `audit_log` table:

- User ID (if authenticated)
- IP address
- Timestamp
- Action type
- Success/failure
- Request details

**Retention**: 365 days (configurable)

---

## 🚨 Troubleshooting

### Database Connection Fails

```bash
# Check Supabase credentials
psql "postgresql://user:pass@host:port/dbname?sslmode=require"

# Verify SSL
openssl s_client -connect host:port -starttls postgres
```

### Migrations Fail

```bash
# Check existing tables
docker-compose exec backend python -c "from database.migrations import MigrationManager; print(MigrationManager().get_existing_tables())"

# Manual migration
docker-compose exec backend python -c "from database.migrations import run_migrations; run_migrations()"
```

### JWT Errors

```bash
# Verify secret key is set
docker-compose exec backend env | grep JWT_SECRET_KEY

# Test token generation
docker-compose exec backend python -c "from services.jwt_manager import get_jwt_manager; print(get_jwt_manager().create_access_token('test_user', 'test'))"
```

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase PostgreSQL](https://supabase.com/docs/guides/database)
- [Cryptography Library](https://cryptography.io/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

## 👤 Default Credentials

**⚠️ CHANGE IMMEDIATELY IN PRODUCTION**

```
Username: admin
Password: AdminPassword123!
```

---

**Last Updated**: January 21, 2026  
**Version**: 1.0.0  
**Security Audit**: Pending
