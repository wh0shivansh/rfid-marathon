# RFID Marathon Management System - Architecture Overview

## 🏗️ System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                     RFID MARATHON TIMING SYSTEM                                │
└────────────────────────────────────────────────────────────────────────────────┘

TIMING POINTS:
═════════════════════════════════════════════════════════════════════════════════

            START LINE              MID POINT (Optional)           FINISH LINE
       ┌──────────────────────────────────────────────────────────────────────────────┐
       │                        │                         │                           │
       │    RFID Hub (HTTP)     │    RFID Hub (HTTP/UDP)  │    RFID Hub (HTTP/UDP)    │
       │    Reader ID: 1        │    Reader ID: 2         │    Reader ID: 3           │
       │                        │                         │                           │
       └──────────┬─────────────┴─────────────┬───────────┴────────────────┬──────────┘
                  │                           │                            │
                  ▼                           ▼                            ▼
          ┌───────────────┐          ┌──────────────────┐        ┌──────────────────┐
          │   RFID HUB    │          │  MID-LINE SETUP  │        │  END-LINE SETUP  │
          │    (HTTP)     │          │  (HTTP or UDP)   │        │      (HTTP)      │
          └───────────────┘          └──────────────────┘        └──────────────────┘
                  │                           │                            │
                  │ HTTP POST                 │ HTTP/UDP                   │ HTTP POST
                  │                           │                            │
                  ▼                           ▼                            ▼
          ┌─────────────────────────────────────────────────────────────────────┐
          │  RFID LISTENER (Proxy)                                              │
          │  - Unified reader endpoint                                          │
          │  - Timestamp capture                                                │
          │  - Event buffering                                                  │
          │  - Batch forwarding                                                 │
          └─────────────────────────────────────────────────────────────────────┘
                  │
                  │ HTTP POST /api/v2/rfid/bulk
                  │
                  ▼
          ┌─────────────────────────────────────────────┐
          │ BACKEND API (FastAPI)                       │
          │  - Race management                          │
          │  - Participant registration                 │
          │  - RFID hit processing                      │
          │  - Real-time status updates                 │
          │  - Dashboard data aggregation               │
          └─────────────────────────────────────────────┘
                  │
                  │ HTTP REST API
                  │
                  ▼
          ┌─────────────────────────────────────────────┐
          │ DATABASE (PostgreSQL/Supabase)              │
          │  - Race configurations                      │
          │  - Per-race participant tables              │
          │  - Timing records                           │
          │  - User authentication                      │
          │  - Encryption key management                │
          └─────────────────────────────────────────────┘
                  ▲
                  │ JDBC/SQL
                  │
          ┌───────┴──────────────────────────────────────┐
          │                                              │
          ▼                                              ▼
    ┌──────────────┐                          ┌──────────────────┐
    │  FRONTEND    │                          │  CONTROL HUB     │
    │  (Electron)  │                          │  (Tkinter GUI)   │
    │  - User Auth │                          │  - Service Mgmt  │
    │  - Reg/Race  │                          │  - Log Viewing   │
    │  - Timing    │                          │  - DB Setup      │
    │  - Results   │                          │  - Status Monitor│
    └──────────────┘                          └──────────────────┘

```

## 📊 Data Flow - Single Participant Timing

```
START:
  RFID Reader → reader_id=1 → RFID Listener → Backend → Database
  Action: participant.status = "running"

MID (Optional):
  RFID Reader → reader_id=2 → RFID Listener → Backend → Database
  Action: participant.mid_time = timestamp

FINISH:
  RFID Reader → reader_id=3 → RFID Listener → Backend → Database
  Action: participant.status = "completed"
  Check: All participants finished? → Auto-end race

DISPLAY:
  Frontend → GET /api/v2/race/{id}/participants
  Display: Real-time participant status, timing, category
```

## 🔄 Service Dependencies

```
MINIMAL (Frontend Only):
    Database
        │
        └─→ Backend
                │
                └─→ Frontend (Desktop App)

TYPICAL (End-Point Timing):
    Database
        │
        ├─→ Backend
        │       │
        │       └─→ RFID Listener
        │               │
        │               └─→ UDP Listener (optional)
        │
        └─→ Frontend

UDP RELAY (Multi-Point):
    HD Line Hub
        │
        └─→ UDP Sender (HTTP→UDP)
                │
                └─→ Network
                        │
                        └─→ UDP Listener (UDP→HTTP)
                                │
                                └─→ RFID Listener
```

## 🗂️ Project Structure

```
rfid-marathon/
├── backend/v2/                    # Core API Server
│   ├── main.py                    # FastAPI application
│   ├── models.py                  # Data schemas
│   ├── constants.py               # Configuration
│   ├── basefunctions.py           # Utilities
│   ├── database/                  # Database layer
│   │   ├── connection.py
│   │   └── migrations.py
│   ├── services/                  # Business logic
│   │   ├── race_service.py
│   │   ├── rfid_service.py
│   │   ├── jwt_manager.py
│   │   ├── password_manager.py
│   │   ├── fernet_manager.py
│   │   └── rsa_manager.py
│   └── middleware/
│       └── auth_middleware.py
│
├── frontend/                      # Desktop Application (Electron)
│   ├── src/
│   │   ├── main/
│   │   │   └── main.js            # Electron main process
│   │   └── renderer/
│   │       ├── app.js             # Main app logic
│   │       ├── services/          # Service layer
│   │       ├── views/             # UI components
│   │       └── utils/             # Utilities
│   ├── public/                    # Static assets
│   └── package.json               # Dependencies
│
├── proxy/v2/                      # RFID Listener Service
│   └── rfid_listener.py           # Unified RFID receiver
│
├── udp_server/                    # UDP Protocol Bridge
│   ├── udp_sender.py              # HTTP→UDP converter
│   └── udp_listener.py            # UDP→HTTP converter
│
├── control-hub/                   # Service Management GUI
│   └── control-hub.py             # Tkinter dashboard
│
├── database/                      # Database Setup
│   ├── init.sql                   # Schema definition
│   └── build_database.ps1         # Setup script
│
└── README.md (main documentation)

```

## 🔐 Security Architecture

```
AUTHENTICATION:
    User ─→ Login ─→ Backend → JWT Token → Frontend/All Requests

ENCRYPTION:
    Names (Fernet) ┐
                   └─→ Database (at rest)
    
    Responses (RSA) ─→ Frontend (from API)

REPLAY PROTECTION:
    Timestamp + Nonce ─→ Window validation (60 sec)
```

## 🚀 Typical Workflow

```
SETUP:
1. Start Control Hub
2. Initialize Local Database
3. Start Backend Service
4. Start RFID Listener
5. Start Frontend App

PRE-RACE:
1. Create Race (name, distance, category)
2. Register Participants (single/bulk upload)
3. Configure Start Times (per age group)
4. Verify all systems ready

RACE EXECUTION:
1. Hit [Start Race] in Frontend
2. Participants assigned start_time
3. RFID hits begin flowing from readers
4. Real-time results displayed
5. Hit [End Race] when complete

POST-RACE:
1. Export results (HTML/PDF/Excel)
2. Analyze performance metrics
3. Archive if needed
```

## 📱 Key Endpoints (REST API)

```
Authentication:
  POST /api/v2/auth/login

Race Management:
  POST   /api/v2/race                    # Create
  GET    /api/v2/race                    # List
  GET    /api/v2/race/{id}               # Detail
  PATCH  /api/v2/race/{id}               # Update
  DELETE /api/v2/race/{id}               # Delete
  POST   /api/v2/race/{id}/start         # Activate
  POST   /api/v2/race/{id}/end           # Complete
  POST   /api/v2/race/{id}/start-times   # Config times

Participants:
  POST   /api/v2/participant/register    # Single
  POST   /api/v2/participant/lookup      # By RFID
  POST   /api/v2/races/{id}/bulk-upload  # Bulk
  GET    /api/v2/participants            # All
  GET    /api/v2/race/{id}/participants  # Per race
  PATCH  /api/v2/participant/{id}        # Update
  DELETE /api/v2/participant/{id}        # Delete

RFID Timing:
  POST /api/v2/rfid/hit                  # Single hit
  POST /api/v2/rfid/bulk                 # Batch hits

Dashboard:
  GET /api/v2/dashboard-data             # Statistics
```

## 🎯 Technology Stack

```
BACKEND:
  Framework: FastAPI
  Database: PostgreSQL (Supabase)
  Auth: JWT + Replay Protection
  Crypto: Fernet (symmetric), RSA (asymmetric)
  ORM: SQLAlchemy 2.0

FRONTEND:
  Framework: Electron (Chromium + Node.js)
  UI: Vanilla JS + CSS
  HTTP Client: Axios
  File Handling: xlsx, docx, pdf-lib
  Crypto: Fernet.js

RFID LISTENER:
  Framework: FastAPI
  Transport: HTTP/UDP
  Buffering: In-memory queue

UDP SERVERS:
  Protocol: UDP + JSON
  Conversion: HTTP ↔ UDP
  Batching: Configurable chunks

CONTROL HUB:
  Framework: Tkinter (Python)
  OS: Windows (PowerShell integration)
  Process Mgmt: subprocess + threading

DEVOPS:
  Build: PyInstaller (Python → EXE)
  Version: Electron Forge (Desktop packages)
  Config: Environment files (.env)
```

## 📈 Performance Targets

```
THROUGHPUT:
  - RFID Hit Processing: ~1000/second per reader
  - Participant Registration: ~50/second bulk
  - API Response: < 100ms (p95)

LATENCY (RFID to Display):
  - Direct proxy: < 2 seconds
  - With UDP relay: < 10 seconds
  - Batch sync: < 5 seconds

SCALABILITY:
  - Participants per race: 10,000+
  - Concurrent races: 1+ (current design)
  - Connection pool: 20 + 10 overflow

STORAGE:
  - Per race timing: ~1KB per participant
  - Annual: ~100GB (1M participants)
  - Database: Auto-managed by Supabase
```

## 🔧 Manual Testing Commands

```bash
# Test Backend Health
curl http://localhost:8000/health

# Test RFID Listener Health
curl http://localhost:9090/health

# Test RFID Hit
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "tag_read",
    "event_data": [{"rfid": "ABC123456"}],
    "reader_name": "Reader 1"
  }'

# Test UDP Sender
curl -X POST http://localhost:6001/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "tag_read",
    "event_data": [{"rfid": "ABC123456"}]
  }'

# Monitor Backend Logs
tail -f backend/logs/v2.log

# Check Database Connection
psql -h localhost -U postgres -d rfid_marathon -c "SELECT COUNT(*) FROM races;"
```

---

**See individual module documentation files for detailed technical information:**
- `BACKEND_V2_NOTES.txt` - API, security, database schema
- `FRONTEND_NOTES.txt` - UI, features, workflows
- `RFID_LISTENER_NOTES.txt` - Event handling, buffering, formats
- `UDP_SERVERS_NOTES.txt` - Protocol conversion, configuration
- `CONTROL_HUB_NOTES.txt` - Service management, GUI usage

