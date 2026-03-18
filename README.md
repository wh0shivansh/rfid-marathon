# RFID Marathon Management System

**Military-Grade RFID Timing System for Marathon Events**

A comprehensive, secure, and scalable system for real-time participant timing in marathon events using RFID technology. Built with enterprise-grade security, encryption, and audit capabilities.

![Status](https://img.shields.io/badge/Status-Production-brightgreen)
![Version](https://img.shields.io/badge/Version-2.0.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

---

## 📚 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Quick Start](#quick-start)
- [Module Documentation](#module-documentation)
- [Deployment](#deployment)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## Overview

The RFID Marathon Management System provides:

1. **Real-Time Timing**: Capture participant start, mid-point, and finish times via RFID readers
2. **Secure Management**: Military-grade encryption, JWT authentication, and replay attack protection
3. **Multi-Point Architecture**: Support for START, MID-POINT, and FINISH line timing
4. **Flexible Deployment**: Works with single or multiple RFID readers via HTTP or UDP
5. **Desktop & Web Interfaces**: Native Electron desktop app and responsive web dashboard
6. **Comprehensive Reporting**: Real-time results, performance analysis, and export capabilities

**Perfect for:**
- Military marathons and running events
- Age-group categorized races
- Multi-point timing systems
- Events requiring 1,000+ participant capacity

---

## 🎯 Key Features

### Race Management
- Create races with custom distances, locations, and scheduled dates
- Support for BPET, CPT, and PPT categories with different age groups
- Qualifying time standards per category and age group
- Dynamic per-race participant tables (isolated data)
- Race status lifecycle: CREATED → STARTED → COMPLETED

### Participant Management
- Single participant registration with encryption
- Bulk upload via CSV/XLSX/DOCX files (1,000+ participants at once)
- Auto-assignment of RFID tags with configurable prefix/sequence
- Per-participant encrypted name storage
- Army number validation and duplicate prevention

### RFID Timing System
- Unified RFID listener for START, MID, and END lines
- Real-time timestamp capture (Asia/Kolkata timezone)
- Idempotent processing (duplicate-safe)
- Status tracking: registered → running → completed
- Automatic race completion when all participants finish

### Security Architecture
- **Authentication**: JWT tokens with 15-minute expiry
- **Replay Protection**: Timestamp + nonce validation (60-second window)
- **Encryption**: Fernet (symmetric) for names, RSA (4096-bit) for responses
- **Password Security**: bcrypt (cost 12) with auto-rehasing
- **Database Security**: SSL-capable PostgreSQL with connection pooling

### Real-Time Dashboard
- Live participant status updates
- Per-race statistics (registered, started, completed counts)
- Performance category assignments
- Historical race data
- Search and filtering capabilities

### Data Integrity
- Atomic transactions for bulk operations
- Non-destructive migrations (schema changes safe)
- Audit trail for authentication events
- Encryption key rotation (90-day policy)

---

## 🏗️ System Architecture

### High-Level Components

```
  RFID READERS (Multiple Points)
              ↓
   RFID LISTENER (FastAPI Proxy)
              ↓
BACKEND API (FastAPI + PostgreSQL)
       ↙      ↓      ↘
 Frontend  Dashboard  Control Hub
```

### Detailed Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for:
- Data flow diagrams
- Service dependencies
- Technology stack details
- Performance metrics
- REST API endpoints

### Module Structure

```
backend/v2/          - Core API server (FastAPI, PostgreSQL)
frontend/            - Desktop app (Electron, JavaScript)
proxy/v2/            - RFID listener service (FastAPI)
udp_server/          - HTTP↔UDP gateway services
control-hub/         - Service management GUI (Tkinter)
database/            - PostgreSQL initialization scripts
```

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10/11** (or Linux/Mac for backend only)
- **Python 3.10+**
- **PostgreSQL 12+** (or Supabase cloud)
- **Node.js 16+** (for frontend development)

### Installation & Setup

#### 1. **Clone Repository**
```bash
git clone https://github.com/innogative/rfid-marathon.git
cd rfid-marathon
```

#### 2. **Setup Backend**
```bash
cd backend/v2
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

#### 3. **Setup Database** (Local or Cloud)

**Option A: Supabase (Cloud - Recommended)**
```bash
# Create .env file with credentials
cp .env.example .env
# Edit .env with your Supabase connection string
```

**Option B: Local PostgreSQL**
```bash
cd database
powershell -ExecutionPolicy Bypass -File build_database.ps1
```

#### 4. **Start Backend Service**
```bash
cd backend/v2
python main.py
# Listens on http://localhost:8000
# Swagger docs: http://localhost:8000/api/v2/docs
```

#### 5. **Start RFID Listener** (if using RFID readers)
```bash
cd proxy/v2
python rfid_listener.py
# Listens on http://localhost:9090
# Health check: curl http://localhost:9090/health
```

#### 6. **Start Desktop Frontend**
```bash
cd frontend
npm install
npm start
# Opens Electron application
```

#### 7. **Launch Control Hub** (for managing all services)
```bash
python control-hub/control-hub.py
# Provides unified service management GUI
```

### Verify Installation

```bash
# Test Backend Health
curl http://localhost:8000/health

# Test RFID Listener Health  
curl http://localhost:9090/health

# Login and get token
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123",
    "timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'",
    "nonce": "nonce123456789nonce123456789no"
  }'
```

---

## 📖 Module Documentation

### Backend API (`backend/v2/`)
**Comprehensive REST API for race and participant management**

- [BACKEND_V2_NOTES.txt](BACKEND_V2_NOTES.txt) - Complete technical documentation
- Features:
  - FastAPI with JWT authentication
  - PostgreSQL with encrypted fields
  - RFID hit processing (sync and async)
  - Dashboard data aggregation
  - Bulk participant upload with auto-RFID assignment

**Key Endpoints:**
```
POST   /api/v2/auth/login
POST   /api/v2/race                    # Create race
GET    /api/v2/race                    # List races
POST   /api/v2/race/{id}/start         # Activate
POST   /api/v2/participant/register    # Register participant
POST   /api/v2/races/{id}/bulk-upload  # Bulk upload
POST   /api/v2/rfid/hit                # Single RFID hit
POST   /api/v2/rfid/bulk               # Batch RFID hits
```

### Frontend Desktop App (`frontend/`)
**Electron application for race setup and monitoring**

- [FRONTEND_NOTES.txt](FRONTEND_NOTES.txt) - UI features and workflows
- Features:
  - Authentication (login with 2FA support planned)
  - Race creation and management
  - Participant registration (single/bulk)
  - Real-time timing display
  - Results export (HTML/PDF/Excel)
  - RFID listener integration

### RFID Listener Service (`proxy/v2/`)
**Unified RFID event receiver and aggregator**

- [RFID_LISTENER_NOTES.txt](RFID_LISTENER_NOTES.txt) - Service details
- Features:
  - Multi-point reader support (START/MID/END)
  - Batch buffering with async flushing (5-second interval)
  - Hub state tracking and health monitoring
  - Automatic timing point detection
  - GPIO state change handling

### UDP Servers (`udp_server/`)
**Optional protocol bridge for distributed timing points**

- [UDP_SERVERS_NOTES.txt](UDP_SERVERS_NOTES.txt) - Configuration and usage
- Two services:
  - **UDP Sender**: HTTP→UDP converter (mid-point forwarder)
  - **UDP Listener**: UDP→HTTP converter (network bridge)
- Features:
  - Transparent protocol conversion
  - Redundant packet transmission (5x repeat)
  - Per-reader deduplication
  - Flexible chunking (max 100 RFIDs/packet)

### Control Hub GUI (`control-hub/`)
**Windows service management and monitoring dashboard**

- [CONTROL_HUB_NOTES.txt](CONTROL_HUB_NOTES.txt) - GUI and operations
- Features:
  - Unified service control (Start/Stop/Restart)
  - Real-time log viewing (per-service tabs)
  - Service grouping (Frontend, End-Line)
  - Local PostgreSQL setup automation
  - Health status monitoring
  - Log file persistence

### System Architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) - Data flows, diagrams, tech stack

---

## 🔧 Deployment

### Production Deployment

#### Backend (Cloud - Supabase)
```bash
# Deploy to cloud provider (Heroku, DigitalOcean, AWS)
# Use CI/CD pipeline with PostgreSQL managed service
# Environment variables:
export DB_HOST=db.supabase.co
export DB_PORT=5432
export DB_NAME=postgres
export DB_USER=postgres
export DB_PASSWORD=***
export JWT_SECRET_KEY=***
export ENCRYPTION_KEY_PATH=/secure/path/key.pem
```

#### Frontend (Desktop Distribution)
```bash
# Build Electron package
cd frontend
npm run package

# Outputs to: RFID-Marathon-Automation/marathon-win32-x64/
# Distribute .exe installer or portable app
```

#### RFID Services (Windows)
```bash
# Create executable packages
pyinstaller rfid_listener.py --onefile
pyinstaller udp_sender.py --onefile
pyinstaller udp_listener.py --onefile

# Deploy to event location
# Configure IP addresses in .env files
# Run via Control Hub GUI
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/v2/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/v2/ .
EXPOSE 8000
CMD ["python", "main.py"]
```

---

## 🔐 Security

### Authentication & Authorization
- JWT tokens with configurable expiry (default 15 minutes)
- Replay attack protection via timestamp/nonce validation
- Password bcrypt hashing (cost 12) with auto-rehash on auth
- User account activation/deactivation

### Data Encryption
- **At Rest**: Participant names encrypted with Fernet (symmetric)
- **In Transit**: RSA 4096-bit public key for API responses
- **Database**: SSL-capable PostgreSQL recommended
- **Key Management**: Encryption keys tracked per participant, rotated every 90 days

### API Security
- HTTPS (recommended for production)
- CORS configuration (restrictable)
- Rate limiting (60 req/min per client, configurable)
- Error handling without information leakage

### Audit Trail
- Logging of authentication failures
- Audit records for race status changes
- Encryption key rotation tracking
- Database connection pooling security

### Compliance
- No plaintext passwords stored or transmitted
- PII (participant names) encrypted at rest
- Timestamps in UTC for consistency
- GDPR-ready architecture (data isolation per race)

---

## 🐛 Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check port 8000 is available
netstat -ano | findstr :8000

# Verify database connection
psql -h localhost -U postgres -d rfid_marathon -c "SELECT 1"

# Check .env file exists and is valid
cat .env | grep DB_
```

#### RFID Listener Not Receiving Events
```bash
# Verify listener is running and listening on port 9090
netstat -ano | findstr :9090

# Test with curl
curl -X POST http://localhost:9090/test \
  -H "Content-Type: application/json" \
  -d '{"rfid": "TEST123"}'

# Check hub configuration - verify hub IP_ADDRESS points to listener
# Review rfid_listener.log for errors
```

#### Participants Not Timing Out
```bash
# Check race status is "started"
curl http://localhost:8000/api/v2/diagnostics/races

# Verify RFID reader connectivity
curl http://localhost:9090/health

# Check participant status in database
select rfid_tag, status, start_time, end_time from race_xxxxx_participants limit 5;

# Review backend logs for RFID hit processing
tail -f backend/logs/rfid-marathon.log
```

#### Database Setup Fails
```bash
# For local PostgreSQL
# 1. Verify postgres/bin/postgres.exe exists
ls -la database-setup/postgres/bin/

# 2. Check .env file in database-setup/
cat database-setup/.env

# 3. Review postgres.log
cat database-setup/postgres.log

# 4. Verify port 5432 is free
netstat -ano | findstr :5432
```

### Debug Mode

```bash
# Enable debug logging in backend
export LOG_LEVEL=DEBUG
python backend/v2/main.py

# Enable Control Hub debug mode
set CONTROL_HUB_DEBUG=1
python control-hub/control-hub.py

# Monitor RFID listener with verbose output
python proxy/v2/rfid_listener.py  # Watch logs
```

### Performance Optimization

```bash
# Increase database connection pool
export DB_POOL_SIZE=50
export DB_MAX_OVERFLOW=20

# Reduce RFID flush interval for faster response
export RFID_BULK_FLUSH_SECONDS=2

# Adjust UDP send repeats for reliability/speed
export UDP_SEND_REPEATS=3  # instead of 5

# Monitor system resources
Task Manager: Performance tab
  - Memory usage (should be < 500MB for backend)
  - CPU usage (spikes during bulk upload expected)
  - Network bandwidth
```

---

## 📊 API Specification

### Example: Create Race & Participants

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123",
    "timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'",
    "nonce": "unique_nonce_here"
  }' | jq -r '.data.access_token')

# 2. Create Race
RACE=$(curl -s -X POST http://localhost:8000/api/v2/race \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Marathon 2025",
    "distance_meters": 42195,
    "location": "City Park",
    "scheduled_date": "2025-01-15T06:00:00Z",
    "race_category": "BPET",
    "rfid_placement_mode": "START_MID_END"
  }' | jq -r '.data.id')

# 3. Register Participant
curl -s -X POST http://localhost:8000/api/v2/participant/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "'$RACE'",
    "rfid_tag": "ABC123456",
    "name": "John Doe",
    "age": 28,
    "gender": "M"
  }'

# 4. Start Race
curl -s -X POST http://localhost:8000/api/v2/race/$RACE/start \
  -H "Authorization: Bearer $TOKEN"

# 5. Send RFID Hit (when participant crosses reader)
curl -s -X POST http://localhost:8000/api/v2/rfid/hit \
  -H "Content-Type: application/json" \
  -d '{
    "rfid_tag": "ABC123456",
    "timing_point": "start",
    "hit_timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'"
  }'
```

---

## 📚 Additional Resources

### Configuration Files
- `backend/v2/.env` - Backend secrets and database credentials
- `frontend/.env` - Frontend API URL and feature flags
- `proxy/v2/.env` - RFID listener configuration
- `control-hub/config.json` - Service definitions

### Default Credentials
```
Username: admin
Password: SecurePassword123 (CHANGE IN PRODUCTION)
```

### Environment Variables Reference
See each module's `.env.example` file for:
- Database connection strings
- API URLs and ports
- Encryption keys
- Feature flags
- Logging levels

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## ✅ Verification Checklist

Before deploying to production:

- [ ] All services start without errors
- [ ] Database connectivity verified
- [ ] RFID readers configured and connected
- [ ] TLS/SSL certificates in place
- [ ] Backups configured
- [ ] Monitoring/alerting configured
- [ ] Load tested with expected participant volume
- [ ] Security audit completed
- [ ] User training completed
- [ ] Incident response plan documented

---

## 🆘 Support

For issues, questions, or contributions:

1. **GitHub Issues**: Report bugs and request features
2. **Documentation**: Review [ARCHITECTURE.md](ARCHITECTURE.md) and module docs
3. **Email Support**: contact@innogative.com
4. **Emergency**: On-call support during events: +1-XXX-XXX-XXXX

---

**Made with ❤️ by [Innogative Technologies](https://innogative.com)**

**Last Updated**: January 21, 2026  
**Version**: 2.0.0
