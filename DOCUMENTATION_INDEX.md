# RFID Marathon Management System - Documentation Index

## 📚 Documentation Structure

This project has comprehensive documentation split into multiple files for clarity and ease of navigation:

### 🚀 Quick Start
**→ Start here:** [README.md](README.md)
- System overview and features
- Quick start guide with step-by-step setup
- Verification checklist
- Common testing scenarios
- Troubleshooting guide

### 🏗️ System Architecture
**→ Understand the big picture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- System-level architecture diagram
- Data flow between components
- Technology stack overview
- API endpoints summary
- System flow diagram (timing points)

---

## 📖 Detailed Module Documentation

### 1. Backend API (FastAPI v2)
**Primary File:** `backend/v2/`  
**Documentation:** [BACKEND_V2_NOTES.txt](BACKEND_V2_NOTES.txt) (800 lines)

**Key Topics:**
- REST API endpoints (30+ endpoints documented)
- Database schema and models
- Authentication & security
- Race and participant management
- RFID hit processing
- Service layer architecture
- Configuration reference

**Key Files in Module:**
- `main.py` - FastAPI application (1800+ lines, all endpoints)
- `models.py` - Pydantic schemas and SQLAlchemy ORM
- `constants.py` - Global configuration and security settings
- `database/connection.py` - PostgreSQL connection pooling
- `database/migrations.py` - Dynamic schema migrations
- `services/race_service.py` - Race business logic
- `services/rfid_service.py` - RFID encryption and lookups

**Quick Facts:**
- Port: 8000
- Protocol: HTTP/REST
- Database: PostgreSQL/Supabase
- Authentication: JWT (HS256)
- Encryption: Fernet (names), RSA 4096 (responses)
- Max participants: 3000+ per race

**Test Examples:**
```bash
# Start backend
cd backend/v2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Verify
curl http://localhost:8000/api/v2/health

# Create race
curl -X POST http://localhost:8000/api/v2/race/create \
  -H "Authorization: Bearer {token}" \
  -d "{race_name: test}"
```

---

### 2. Frontend Desktop App (Electron)
**Primary File:** `frontend/`  
**Documentation:** [FRONTEND_NOTES.txt](FRONTEND_NOTES.txt) (750 lines)

**Key Topics:**
- Views and UI components (7 views)
- State management architecture
- Service layer integration
- Feature workflows
- File upload handling (CSV/XLSX/DOCX)
- Real-time race monitoring
- Configuration and settings

**Key Files in Module:**
- `src/renderer/app.js` - Central state management (500+ lines)
- `src/renderer/services/CandidateRegistration.js` - Registration workflows
- `src/renderer/services/RaceStart.js` - Real-time race monitoring
- `src/renderer/services/Dashboard.js` - Race statistics
- `src/renderer/services/RaceScoreboard.js` - Results display
- `public/app.js` - Main process manager

**Quick Facts:**
- Framework: Electron 40.0.0 with Vanilla JavaScript
- HTTP Client: axios
- File Support: XLSX, CSV, DOCX, TXT
- State: Global object with property watchers
- Timing Integration: Real-time clock and duration tracking
- Target OS: Windows

**Launch:**
```bash
cd frontend
npm install
npm start

# Build executable
npm run build
```

---

### 3. RFID Listener/Proxy (FastAPI v2)
**Primary File:** `proxy/v2/`  
**Documentation:** [RFID_LISTENER_NOTES.txt](RFID_LISTENER_NOTES.txt) (900 lines)

**Key Topics:**
- Event handling architecture
- Buffering and batching mechanism
- Middleware timestamp capture
- Timing point detection (START/MID/END)
- Deduplication strategy
- Hub state management
- Health checks and monitoring
- Testing and debugging

**Key Files in Module:**
- `rfid_listener.py` - Main FastAPI service (500+ lines)
- Processes RFID hits from multiple readers
- Implements in-memory cache with periodic flush
- Auto-detects timing point from HTTP headers/URL path

**Quick Facts:**
- Port: 9090
- Protocol: HTTP/REST
- Cache Strategy: Per-reader deduplication
- Flush Interval: Configurable (default 5 seconds)
- Upstream: sends to backend `/api/v2/rfid/bulk`
- Handles: Multiple RFID field names (rfid, epc, tid, id)

**Test Example:**
```bash
# Start RFID listener
cd proxy/v2
python rfid_listener.py

# Send RFID hit
curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: START" \
  -H "X-ReaderName: reader-1" \
  -d '{"rfid": "EPC123456789"}'

# Force flush
curl http://localhost:9090/flush-now
```

---

### 4. UDP Servers (HTTP ↔ UDP Gateway)
**Primary File:** `udp_server/`  
**Documentation:** [UDP_SERVERS_NOTES.txt](UDP_SERVERS_NOTES.txt) (1100 lines)

**Key Topics:**
- Two-way protocol conversion
- UDP sender (HTTP → UDP)
- UDP listener (UDP → HTTP)
- Caching and deduplication
- Performance optimization
- Resend mechanism
- Troubleshooting network issues
- Integration examples

**Key Files in Module:**
- `udp_sender.py` - HTTP to UDP converter (350+ lines)
- `udp_listener.py` - UDP to HTTP converter (250+ lines)
- `send_test_tag.py` - Test utilities
- `requirements.txt` - Dependencies list

**Quick Facts:**

**UDP Sender:**
- Port: 6001 (HTTP)
- Target: Configurable UDP host/port
- Cache: Per-reader deduplication
- Resend: 5x repetition by default
- Chunking: Max 100 tags per UDP packet

**UDP Listener:**
- Port: 8889 (UDP)
- Forwards to: RFID Listener (port 9090)
- Flush Interval: Configurable (default 3 seconds)
- Threading: Background thread per reader

**Integration:**
```
[RFID Reader] --UDP--> [UDP Listener:8889]
                            |
                            (forward via HTTP)
                            v
                     [RFID Listener:9090]
                            |
                            (forward via HTTP)
                            v
                     [Backend API:8000]

OR

[RFID Reader] --HTTP--> [UDP Sender:6001]
                            |
                            (convert to UDP)
                            v
                      [UDP Host:Port]
```

---

### 5. Control Hub (Tkinter GUI)
**Primary File:** `control-hub/`  
**Documentation:** [CONTROL_HUB_NOTES.txt](CONTROL_HUB_NOTES.txt) (900 lines)

**Key Topics:**
- Tkinter GUI interface
- Service process management
- Database setup and initialization
- Logging and monitoring
- Configuration management
- Troubleshooting procedures
- Platform-specific features (Windows)

**Key Files in Module:**
- `control-hub.py` - Main Tkinter application (800+ lines)
- `build_control_hub.ps1` - Build script for executable
- `control-hub.spec` - PyInstaller configuration

**Quick Facts:**
- Framework: Tkinter (Python native GUI)
- Platform: Windows (uses CREATE_NEW_PROCESS_GROUP)
- Services Managed:
  - PostgreSQL Database
  - FastAPI Backend (v2)
  - RFID Listener (proxy v2)
  - UDP Listener
  - UDP Sender
- Features:
  - Start/stop individual or grouped services
  - Real-time log viewing per service
  - Database initialization
  - Service dependency management
  - Error/warning capture

**Launch:**
```bash
cd control-hub
python control-hub.py

# Build executable
python build_control_hub.ps1
```

---

## 🔄 Data Flow Overview

### 1. RFID Hit Pipeline
```
[RFID Reader Hardware]
         ↓
    [UDP Socket] or [HTTP]
         ↓
[UDP Listener] → [RFID Listener] → [Backend API] → [PostgreSQL]
                                         ↓
                                   [Participant Status Updated]
                                         ↓
                                   [Frontend Displays Change]
```

### 2. Participant Registration Flow
```
[Frontend Upload CSV/XLSX]
         ↓
[CandidateRegistration Service]
         ↓
[Parse File → Extract Data]
         ↓
[Validate Against Race Config]
         ↓
[POST /api/v2/participant/register/bulk]
         ↓
[Backend: RfidService.register_participant_with_rfid()]
         ↓
[Encrypt Name (Fernet) + Generate Table Column]
         ↓
[INSERT into race_participant_table]
         ↓
[Return RFID Map]
         ↓
[Frontend: Update Local perRaceRFIDMap] → [Use for dedup during race]
```

### 3. Race Execution Flow
```
[Race Start Button]
         ↓
[Frontend: startRaceDataPolling()] - 2-5 second refresh
         ↓
[GET /api/v2/race/{race_id}/participants]
         ↓
[Backend: _get_race_participants()] - Query dynamic participant table
         ↓
[Return Participant Status List]
         ↓
[Frontend: Display in RaceStart Service]
         ↓
[Show: Start Times, Mid Times, End Times, Status]
         ↓
[Duration Clock Updates Continuously]
```

---

## 🔐 Security Architecture

### Authentication
- **Method:** JWT (HS256)
- **Expiration:** 15 minutes
- **Headers:** `Authorization: Bearer {token}`
- **Login:** POST `/api/v2/auth/login` with username/password
- **Password Hashing:** bcrypt (cost 12)

### Data Encryption
- **Names (Symmetric):** Fernet encryption (symmetric key per race)
- **API Responses (Asymmetric):** RSA 4096-bit public key encryption
- **Keys Located:** `backend/v2/keys/` directory

### Replay Attack Protection
- **Mechanism:** Timestamp + Nonce
- **Window:** 60 seconds
- **Nonce Storage:** PostgreSQL cache table
- **Validation:** Per RFID hit at backend

### Database Security
- **Connection:** SSL-capable (configurable)
- **Pool:** 20 persistent + 10 overflow connections
- **Credentials:** Environment variables (`.env` file)

---

## 🛠️ Configuration Reference

### Environment Variables
Create `.env` file in `backend/v2/`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/marathon_db
SECRET_KEY=your-secret-key-here (for JWT)
RFID_LISTENER_HOST=http://localhost:9090
REDIS_URL=redis://localhost:6379 (optional, for caching)
```

### Key Configuration Files
- `backend/v2/constants.py` - Global settings (security, timeouts, etc.)
- `frontend/src/renderer/app.js` - RACE_CATEGORY_CONFIG, API_BASE_URL
- `proxy/v2/rfid_listener.py` - CACHE_FLUSH_INTERVAL, BUFFER_SIZE
- `udp_server/udp_sender.py` - TARGET_HOST, TARGET_PORT, RESEND_COUNT
- `control-hub/control-hub.py` - Process paths, log levels

---

## 📊 Testing Commands

### 1. Health Checks
```bash
# Backend
curl http://localhost:8000/api/v2/health

# RFID Listener
curl http://localhost:9090/health

# UDP Listener (check via netstat on port 8889)
netstat -an | find "8889"
```

### 2. Create Test Race
```bash
# Get auth token
TOKEN=$(curl -X POST http://localhost:8000/api/v2/auth/login \
  -d '{"username":"admin","password":"admin"}' | jq '.access_token')

# Create race
curl -X POST http://localhost:8000/api/v2/race/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_name":"TestRace","category":"BPET","start_time":"2024-01-01T09:00:00"
  }'
```

### 3. Register Participant
```bash
curl -X POST http://localhost:8000/api/v2/participant/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "race_id":"race-uuid","name":"John Doe","age":30,"rfid":"EPC123456"
  }'
```

### 4. Simulate RFID Hit
```bash
# Via RFID Listener (HTTP)
curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: START" \
  -H "X-ReaderName: reader-1" \
  -d '{"rfid":"EPC123456"}'

# Via UDP Listener (must be running)
python udp_server/send_test_tag.py --rfid "EPC123456" --reader "reader-1"
```

---

## 🚨 Troubleshooting Index

### Common Issues
See detailed troubleshooting sections in individual module documentation:
- **Backend Issues:** [BACKEND_V2_NOTES.txt](BACKEND_V2_NOTES.txt#L700-L800)
- **Frontend Issues:** [FRONTEND_NOTES.txt](FRONTEND_NOTES.txt#L600-L700)
- **RFID Listener Issues:** [RFID_LISTENER_NOTES.txt](RFID_LISTENER_NOTES.txt#L800-L900)
- **UDP Issues:** [UDP_SERVERS_NOTES.txt](UDP_SERVERS_NOTES.txt#L1000-L1100)
- **Control Hub Issues:** [CONTROL_HUB_NOTES.txt](CONTROL_HUB_NOTES.txt#L800-L900)

### Debug Commands
```bash
# Check all ports in use
netstat -ano | findstr /E "8000|9090|6001|8889|5432"

# View backend logs
Get-Content "control-hub-logs\backend.log" -Tail 50

# Test database connection
cd backend/v2 && python -c "from database.connection import db; print(db.test_connection())"

# Clear RFID cache
curl http://localhost:9090/flush-now
```

---

## 📋 File Organization

```
/
├── README.md                      ← START HERE (main project doc)
├── ARCHITECTURE.md                ← System architecture & diagrams
├── DOCUMENTATION_INDEX.md         ← This file (navigation guide)
│
├── BACKEND_V2_NOTES.txt          (800 lines - detailed API reference)
├── FRONTEND_NOTES.txt            (750 lines - UI/UX implementation)
├── RFID_LISTENER_NOTES.txt       (900 lines - event processing)
├── UDP_SERVERS_NOTES.txt         (1100 lines - protocol conversion)
├── CONTROL_HUB_NOTES.txt         (900 lines - service management)
│
├── backend/v2/                   (Main FastAPI application)
├── frontend/                     (Electron desktop client)
├── proxy/v2/                     (RFID event aggregation)
├── udp_server/                   (HTTP↔UDP gateway)
├── control-hub/                  (Tkinter service manager)
└── database/                     (PostgreSQL initialization)
```

---

## 📝 Documentation Statistics

| Component | Lines | Format | Focus |
|-----------|-------|--------|-------|
| Backend v2 | 800 | .txt | API, database, security |
| Frontend | 750 | .txt | Views, state, workflows |
| RFID Listener | 900 | .txt | Events, buffering, testing |
| UDP Servers | 1100 | .txt | Conversion, integration, perf |
| Control Hub | 900 | .txt | GUI, processes, setup |
| Architecture | 350 | .md | System design, diagrams |
| Main README | 600 | .md | Quick start, examples |
| **TOTAL** | **4,400+** | **Mixed** | **Complete coverage** |

---

## 🔗 Quick Links

**Getting Started:**
1. [README.md](README.md) - Start here
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the system

**By Component:**
- [Backend API](BACKEND_V2_NOTES.txt)
- [Frontend UI](FRONTEND_NOTES.txt)
- [RFID Processing](RFID_LISTENER_NOTES.txt)
- [Protocol Gateway](UDP_SERVERS_NOTES.txt)
- [Service Manager](CONTROL_HUB_NOTES.txt)

**Common Tasks:**
- Setting up development environment → README.md
- Understanding data flow → ARCHITECTURE.md
- Adding a new API endpoint → BACKEND_V2_NOTES.txt
- Styling UI → FRONTEND_NOTES.txt
- Debugging RFID issues → RFID_LISTENER_NOTES.txt
- Managing services → CONTROL_HUB_NOTES.txt

---

## 📞 Support

For detailed information on any component:
1. Check the main [README.md](README.md) for common issues
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for system understanding
3. Consult the component-specific .txt files for implementation details
4. Check the troubleshooting sections in relevant documentation

**Last Updated:** 2024  
**Documentation Version:** 1.0  
**System Version:** v2 (Backend/RFID Listener/Control Hub)

---

*This documentation was generated through comprehensive codebase analysis and contains 4,400+ lines of structured technical reference covering all system components.*
