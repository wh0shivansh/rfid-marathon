# Control Hub - Windows Service Management GUI

## 📋 Overview

The Control Hub is a Tkinter-based Windows desktop application for managing and monitoring all RFID Marathon system services. It provides a centralized dashboard for starting/stopping services, viewing real-time logs, initializing the database, and managing service dependencies.

**Key Characteristics:**
- **Framework:** Tkinter (Python native GUI)
- **Platform:** Windows (uses Windows-specific process management)
- **Services Managed:** PostgreSQL, Backend API, RFID Listener, UDP Services
- **Features:** Service control, log viewing, database initialization, dependency tracking
- **Log Capture:** Real-time per-service output capture to tabs
- **Build:** PyInstaller executable for Windows distribution
- **Target OS:** Windows 7+ (x64)

---

## 🏗️ Architecture

### Application Structure

```
┌──────────────────────────────────────────────────┐
│   Control Hub (Tkinter GUI)                      │
│   ┌────────────────────────────────────────────┐ │
│   │  Service Control Panel (Top)               │ │
│   │  ┌─────────────────────────────────────┐   │ │
│   │  │ [🟢 Database]   [🔴 Backend]        │   │ │
│   │  │ [🟢 RFID] [🟢 UDP Listen] [🟢 UDP] │   │ │
│   │  │ [🟢 Proxy] [🟢 Frontend]            │   │ │
│   │  │                                     │   │ │
│   │  │ Group Controls:                     │   │ │
│   │  │ [▶ Start Frontend] [⏹ Stop]        │   │ │
│   │  │ [▶ Start End-Line] [⏹ Stop]        │   │ │
│   │  │ [↻ Init Database] [🗂 Open Logs]   │   │ │
│   │  └─────────────────────────────────────┘   │ │
│   ├────────────────────────────────────────────┤ │
│   │ Log Viewer (Bottom - Tabbed)               │ │
│   │ ┌─────────────────────────────────────┐    │ │
│   │ │ [Database] [Backend] [RFID] [UDP]   │    │ │
│   │ ├─────────────────────────────────────┤    │ │
│   │ │ 2024-01-01 10:00:15 - Server ready  │    │ │
│   │ │ 2024-01-01 10:00:16 - Listening...  │    │ │
│   │ │ [Scroll to bottom...]               │    │ │
│   │ └─────────────────────────────────────┘    │ │
│   └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘

Service Dependency Tree:

Database (PostgreSQL)
    ↓
Backend API (FastAPI)
    ├─ RFID Listener
    ├─ UDP Sender
    └─ UDP Listener
         ↓
Frontend (Electron) - optional
```

---

## 🚀 Quick Start

### Installation

```bash
# Navigate to control-hub directory
cd control-hub

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Control Hub

```bash
# Development mode
python control-hub.py

# Or via PowerShell
python .\control-hub.py

# Build as Windows executable
python build_control_hub.ps1
# Output: control-hub.exe (standalone, no Python needed)
```

### Post-Installation Setup

1. **Database Setup:**
   - Click [↻ Init Database] button
   - Waits for PostgreSQL initialization script
   - Creates `marathon_db` database and schema

2. **Service Paths Configuration:**
   - Edit paths in `control-hub.py` constants section:
   ```python
   BACKEND_PATH = r"C:\path\to\backend\v2\main.py"
   RFID_LISTENER_PATH = r"C:\path\to\proxy\v2\rfid_listener.py"
   UDP_SENDER_PATH = r"C:\path\to\udp_server\udp_sender.py"
   UDP_LISTENER_PATH = r"C:\path\to\udp_server\udp_listener.py"
   ```

3. **Environment Variables:**
   - Create `.env` files in each service directory
   - Or set Windows environment variables globally

---

## 📋 User Interface Guide

### Control Panel (Top Section)

#### Individual Service Buttons

```
[🟢 Database]  - PostgreSQL status indicator + toggle
[🔴 Backend]   - FastAPI status indicator + toggle  
[🟢 RFID]      - RFID Listener status indicator + toggle
[🟢 UDP Listen]- UDP Listener status indicator + toggle
[🟢 UDP Send]  - UDP Sender status indicator + toggle
[🟢 Proxy]     - Proxy service status indicator + toggle
[🟢 Frontend]  - Frontend app status indicator + toggle
```

**Color Codes:**
- 🟢 Green = Running
- 🔴 Red = Stopped
- 🟡 Yellow = Starting/Stopping
- ⚫ Gray = Error/Unknown

#### Group Controls

**Start Frontend Group:**
```
[▶ Start Frontend]
├─ Dependency: Database must be running
├─ Starts: Database (if needed)
├─ Starts: Backend API
├─ Starts: RFID Listener  
├─ Starts: UDP Listener
├─ Starts: UDP Sender
└─ Starts: Frontend (Electron)
```

**Start End-Line Group:**
```
[▶ Start End-Line]
├─ Dependencies: Backend required
├─ Starts: Backend (if needed)
├─ Starts: RFID Listener
├─ Starts: UDP Listener  
├─ Starts: UDP Sender
└─ Purpose: Run without frontend (background only)
```

#### Utility Buttons

**[↻ Init Database]**
- Executes `database/build_database.ps1`
- Waits for PostgreSQL setup
- Creates/initializes `marathon_db`
- Loads schema from `database/init.sql`
- Displays output in Database tab

**[🗂 Open Logs]**
- Opens log directory in Windows Explorer
- Location: `%CD%\logs\`
- Files: Individual logs per service

### Log Viewer (Bottom Section)

#### Tabbed Interface

```
[Database] [Backend] [RFID] [UDP Listen] [UDP Send] [Frontend]

Each tab shows:
- Real-time service output (stdout + stderr)
- Timestamps for each log line
- Auto-scroll to latest (unless scrolled up)
- Color coding: Errors in red, warnings in yellow
```

#### Log Features

```
per-service output capture:
- Database → PostgreSQL startup messages
- Backend → FastAPI debug output + requests
- RFID → Cache statistics + RFID hits  
- UDP → UDP packet statistics
- Frontend → Electron window events

Behavior:
- Continuously appends new lines
- Max 1000 lines per tab (auto-trim old)
- Auto-scroll when at bottom
- Manual scroll up to review history
```

---

## 🔧 Configuration

### Service Paths

Edit `control-hub.py` to set service locations:

```python
# Service executables/scripts
SERVICES = {
    'database': {
        'script': r'database\build_database.ps1',
        'name': 'PostgreSQL',
        'type': 'powershell'
    },
    'backend': {
        'script': r'backend\v2\main.py',
        'name': 'FastAPI Backend',
        'type': 'python'
    },
    'rfid_listener': {
        'script': r'proxy\v2\rfid_listener.py',
        'name': 'RFID Listener',
        'type': 'python'
    },
    'udp_sender': {
        'script': r'udp_server\udp_sender.py',
        'name': 'UDP Sender',
        'type': 'python'
    },
    'udp_listener': {
        'script': r'udp_server\udp_listener.py',
        'name': 'UDP Listener',
        'type': 'python'
    },
    'frontend': {
        'script': r'frontend\node_modules\.bin\electron',
        'args': [r'frontend'],
        'name': 'Electron Frontend',
        'type': 'executable'
    }
}
```

### Log Configuration

```python
# Logging setup
LOG_DIRECTORY = './logs'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO

# Per-service log files
DATABASE_LOG = './logs/database.log'
BACKEND_LOG = './logs/backend.log'
RFID_LISTENER_LOG = './logs/rfid_listener.log'
UDP_SENDER_LOG = './logs/udp_sender.log'
UDP_LISTENER_LOG = './logs/udp_listener.log'
FRONTEND_LOG = './logs/frontend.log'
```

### Process Management

```python
# Windows-specific settings
CREATE_NEW_PROCESS_GROUP = True       # Isolated process group
CREATION_FLAGS = (
    subprocess.CREATE_NEW_PROCESS_GROUP |
    subprocess.CREATE_NEW_CONSOLE
)

# Timeout settings
STARTUP_TIMEOUT = 10       # 10 seconds to verify startup
SHUTDOWN_TIMEOUT = 5       # 5 seconds for graceful shutdown
KILL_TIMEOUT = 2           # 2 seconds before force kill
```

---

## 📚 Operation Guides

### Starting Services

#### Option 1: Full System (Recommended)

```
1. Click [▶ Start Frontend]
2. Wait for all indicators to turn 🟢 green
3. Check Backend tab for "Server running on :8000"
4. Check RFID tab for "Health check OK"
5. Electron window opens automatically
```

**Expected Timeline:**
```
T+0s:   Database starts
T+2s:   Backend starts (waits for DB)
T+3s:   RFID Listener starts
T+3s:   UDP Sender/Listener start
T+5s:   Frontend launches
T+7s:   All services ready for race
```

#### Option 2: Backend Only (No Frontend)

```
1. Click [▶ Start End-Line]
2. All services except Electron start
3. Good for testing/debugging without UI
4. Use curl/postman to test APIs
```

### Stopping Services

```
1. Click [⏹ Stop Frontend] (stops all)
   OR
   Click [⏹ Stop End-Line] (stops except frontend)

2. Individual service buttons stop that service only
   (May leave dependent services running)

3. Services stop in reverse dependency order:
   Frontend → UDP Services → RFID → Backend → Database
```

### Database Initialization

```
1. Connect PostgreSQL to system (or Docker container)
2. Click [↻ Init Database]
3. Waits for `database/build_database.ps1` to complete
4. Creates `marathon_db` database
5. Loads schema from `database/init.sql`
6. Check Database tab for success messages

If fails:
- Check PostgreSQL is running: psql -U postgres
- Verify path to init.sql exists
- Check .env DATABASE_URL is set correctly
```

### Log Review

```
1. Select service tab (e.g., Backend)
2. Read log output for errors
3. Click [🗂 Open Logs] to access files
4. Copy relevant lines for debugging

Common log patterns:
- Backend: "INFO:     Uvicorn running on http://0.0.0.0:8000"
- RFID: "Health check OK" or "Cache flushed: X hits"
- UDP: "UDP packet sent to 192.168.X.X:5000"
```

---

## 🧪 Testing

### Health Check Sequence

```bash
# From Control Hub, verify services are running:

1. Database:
   psql -U postgres -d marathon_db -c "SELECT NOW();"
   # Should return current timestamp

2. Backend:
   curl http://localhost:8000/api/v2/health
   # Should return: {"status": "ok"}

3. RFID Listener:
   curl http://localhost:9090/health
   # Should return: {"status": "ok"}

4. UDP Sender:
   curl http://localhost:6001/health
   # Should return: {"status": "ok"}

5. Frontend:
   # Window should be visible and responsive
```

### Service Startup Verification

```
Expected Control Hub Behavior:

1. Click [▶ Start Frontend]
2. Database tab shows:
   "PostgreSQL 12 started"
   "Initialized database marathon_db"

3. Backend tab shows:
   "Starting Uvicorn server..."
   "Uvicorn running on 0.0.0.0:8000"

4. RFID tab shows:
   "Starting RFID Listener..."
   "Listening on http://0.0.0.0:9090"

5. UDP tabs show:
   "UDP Sender listening on 0.0.0.0:6001"
   "UDP Listener bound to 0.0.0.0:8889"

6. Frontend tab shows:
   "Electron main process started"
   "Window created successfully"
   Window opens with login screen

If any service fails to show ready message:
→ Click [🗂 Open Logs]
→ Check corresponding .log file
→ Look for error messages
```

### Interactive Testing

```
1. All services running (green indicators)
2. Click individual service log tabs
3. From terminal, test each service:

# Database
psql -U postgres -d marathon_db

# Backend - create race
curl -X POST http://localhost:8000/api/v2/race/create \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"race_name":"Test","category":"BPET"}'

# RFID - send hit
curl -X POST http://localhost:9090/reader \
  -d '{"race_id":"uuid","rfid":"EPC001"}'

# UDP - send via sender
curl -X POST http://localhost:6001/reader \
  -d '{"race_id":"uuid","rfid":"EPC002"}'

4. Watch corresponding tabs update in real-time
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Fails to Start

**Error:** "PostgreSQL not found" or connection refused

**Solutions:**
```bash
# 1. Verify PostgreSQL is installed
psql --version

# 2. Check PostgreSQL service is running
# Windows Services: Services.msc → PostgreSQL
# Or: pg_isready -h localhost -p 5432

# 3. Verify .env DATABASE_URL
cat .env | grep DATABASE_URL
# Should be: postgresql://user:password@localhost:5432/marathon_db

# 4. Check password is correct
psql -U postgres -c "SELECT NOW();"
# If fails, reset password or update .env

# 5. Run init script manually
cd database
powershell -ExecutionPolicy Bypass -File build_database.ps1
```

#### 2. Backend Won't Start

**Error:** "Port 8000 already in use" or import error

**Solutions:**
```bash
# 1. Check port is free
netstat -ano | findstr 8000
# If already running: kill or change port

# 2. Verify dependencies installed
cd backend/v2
pip install -r requirements.txt

# 3. Test manually
python main.py
# Should show: "Uvicorn running on http://0.0.0.0:8000"

# 4. Check .env variables
grep SECRET_KEY .env
# Must be set to valid string

# 5. Check database accessible
python -c "from database.connection import db; print(db.test_connection())"
```

#### 3. RFID Listener Not Connecting to Backend

**Error:** "Failed to forward hits" or timeout

**Solutions:**
```bash
# 1. Verify backend is running
curl http://localhost:8000/api/v2/health

# 2. Check RFID can reach backend
curl -X POST http://localhost:8000/api/v2/rfid/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"race_id":"uuid","hits":[]}'
# Should return 200 OK

# 3. Check .env in proxy/v2
grep BACKEND_URL .env
# Should be: http://localhost:8000

# 4. Test RFID Listener directly
curl http://localhost:9090/health
# Should return: {"status": "ok"}

# 5. Send test hit
curl -X POST http://localhost:9090/reader \
  -d '{"race_id":"uuid","rfid":"EPC001"}'
# Should return: {"cached": true}
```

#### 4. Control Hub Services Not Showing Status

**Error:** Status indicators stuck on 🔴 or ⚫

**Solutions:**
```bash
# 1. Check service processes exist
Get-Process | grep python
# Should see backend, rfid_listener, udp_*.py processes

# 2. Check port is listening
netstat -ano | findstr 8000
# Should show LISTENING on port

# 3. Check process logs
ls logs/
# Files should have recent timestamps
tail -f logs/backend.log

# 4. Restart individual service
# Click service button to stop, wait 2s, click to start

# 5. Force refresh Control Hub
# Restart Control Hub application
# All services should re-detect
```

#### 5. Log Viewer Shows Errors

**Error:** "ERROR: [Errno 10061]" or similar in logs

**Solutions:**
```bash
# [Errno 10061] = Connection refused (Windows)
# Usually means downstream service not running

# 1. Check what service errored
# Look at tab: which service has the error?

# 2. Check dependent services
# If Backend errors → Database must run first
# If RFID errors → Backend must run first

# 3. Check firewall
# Windows Defender may block service
# Settings → Firewall → Allow app

# 4. Check .env files all present
# Each service needs its own .env or inherited vars
ls backend/v2/.env
ls proxy/v2/.env
ls udp_server/.env

# 5. Try manual start
cd backend/v2
python main.py
# If manual works but Control Hub fails:
# Check process creation flags in control-hub.py
```

#### 6. Frontend Won't Launch

**Error:** "Electron not found" or window doesn't appear

**Solutions:**
```bash
# 1. Verify Electron is installed
cd frontend
npm list electron
# Should show: electron@40.0.0

# 2. Check dependencies
npm install

# 3. Test manual start
npm start
# Window should open

# 4. Check firewall allows frontend
# May need Windows Defender exception

# 5. Verify backend running first
curl http://localhost:8000/api/v2/health
# Frontend requires backend API
```

---

## 📚 Related Documentation

- **Main Project:** [../../README.md](../../README.md)
- **System Architecture:** [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Backend API:** [../../backend/v2/README.md](../../backend/v2/README.md)
- **Documentation Index:** [../../DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)
- **Full Control Hub Notes:** [../../CONTROL_HUB_NOTES.txt](../../CONTROL_HUB_NOTES.txt)

---

## 📦 File Structure

```
control-hub/
├── control-hub.py         ← Main Tkinter application (800+ lines)
├── build_control_hub.ps1  ← PyInstaller build script
├── control-hub.spec       ← PyInstaller configuration
├── README.md              ← This file
├── requirements.txt       ← Python dependencies
│   ├── tkinter (built-in)
│   ├── python-dotenv
│   └── (minimal - few deps)
├── logs/
│   ├── database.log
│   ├── backend.log
│   ├── rfid_listener.log
│   ├── udp_sender.log
│   ├── udp_listener.log
│   └── frontend.log
└── icons/
    ├── green_dot.png      ← "Running" indicator
    ├── red_dot.png        ← "Stopped" indicator
    └── logo.ico           ← Window icon
```

### Key Dependencies

```
tkinter              # GUI framework (Python built-in)
subprocess           # Process management (Python built-in)
threading            # Threading for log capture (Python built-in)
logging              # Logging system (Python built-in)
python-dotenv        # .env file support
pyinstaller          # Build to executable (dev only)
```

---

## 🎯 Build & Deployment

### Build to Executable

```bash
# Prerequisites:
pip install pyinstaller

# Build:
python build_control_hub.ps1
# Or manually:
pyinstaller --onefile control-hub.py

# Output:
dist/control-hub.exe  ← Standalone executable

# Run:
dist/control-hub.exe  ← No Python needed!
```

### Distribution

```
1. Copy dist/control-hub.exe to any Windows machine
2. Copy logs/ directory (empty)
3. Copy database/, backend/, etc. folders
4. Run control-hub.exe
5. Click [↻ Init Database] to setup
6. Click [▶ Start Frontend] to run

No Python installation needed on target machine!
```

---

## ⌨️ Keyboard Shortcuts

```
Ctrl+Q  - Quit Control Hub
Ctrl+L  - Clear All Logs
Ctrl+D  - Toggle Dark Mode (if implemented)
Ctrl+O  - Open logs folder
Space   - Start/Stop service (if selected)
```

---

## 📊 Performance

**Startup Time:**
- Control Hub window: <1 second
- Database service: 2-3 seconds
- Backend service: 2-3 seconds
- All services ready: 5-8 seconds

**Memory Usage:**
- Control Hub itself: ~50MB
- Backend process: ~200MB
- RFID Listener: ~100MB
- Total system: ~600MB (minimal)

**CPU Usage:**
- Idle: <2%
- Processing 100 RFID hits/sec: ~15%
- Processing 1000 RFID hits/sec: ~50%

---

**Last Updated:** March 2024  
**Version:** 2.0  
**Status:** Production Ready  
**Platform:** Windows 7+ (x64)
