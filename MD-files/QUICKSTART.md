# RFID Marathon - Quick Start Guide

## Prerequisites

1. **Python 3.11+** installed
2. **PostgreSQL** installed and running
3. **pip** package manager

## Initial Setup

### 1. Install Dependencies

```bash
# Install shared dependencies
cd backend/shared
pip install -r requirements.txt
```

### 2. Configure Database

Create a PostgreSQL database:

```sql
CREATE DATABASE rfid_marathon;
```

Or use command line:

```bash
createdb rfid_marathon
```

### 3. Configure Environment (Optional)

Copy `.env.example` to `.env` and modify if needed:

```bash
copy .env.example .env
```

Default settings:
- Database: `localhost:5432/rfid_marathon`
- Username: `postgres`
- Password: `postgres`

### 4. Initialize Database

**Windows:**
```bash
init-database.bat
```

**Linux/Mac:**
```bash
cd backend/shared
python init_db.py
```

## Running the System

### Option 1: Start All Services (Windows)

Double-click `start-all-services.bat` or run:

```bash
start-all-services.bat
```

This will open 5 terminal windows:
- START LINE Backend (Port 8000)
- END LINE Backend (Port 8002)
- REGISTRATION Backend (Port 8003)
- START LINE Proxy (Port 9090)
- END LINE Proxy (Port 9090)

### Option 2: Docker Compose

```bash
docker-compose up -d
```

### Option 3: Manual Start (Individual Services)

**Start Line Backend:**
```bash
cd backend/start-line
python app.py
```

**End Line Backend:**
```bash
cd backend/end-line
python app.py
```

**Registration Backend:**
```bash
cd backend/registration
python app.py
```

**Start Line Proxy:**
```bash
cd proxy-9090/start-line
python proxy.py
```

**End Line Proxy:**
```bash
cd proxy-9090/end-line
python proxy.py
```

## Testing the System

### Run Integration Tests

```bash
python test_system.py
```

This will:
1. Check all services are running
2. Create a test race
3. Register test racers
4. Simulate pre-race scans
5. Start the race
6. Test late arrivals
7. Test start-time correction
8. Simulate finish line scans
9. Display results and statistics

### Manual Testing with cURL

**Health Check:**
```bash
curl http://localhost:8003/health
```

**Create Race:**
```bash
curl -X POST http://localhost:8003/races ^
  -H "Content-Type: application/json" ^
  -d "{\"race_name\": \"Marathon 2026\", \"race_date\": \"2026-01-24\"}"
```

**Register Racer:**
```bash
curl -X POST http://localhost:8003/races/1/register ^
  -H "Content-Type: application/json" ^
  -d "{\"rfid\": \"ABC123\", \"racer_name\": \"John Doe\", \"bib_number\": \"101\"}"
```

**Simulate RFID Scan (Start Line):**
```bash
curl -X POST http://localhost:9090/rfid/scan ^
  -H "Content-Type: application/json" ^
  -d "{\"rfid\": \"ABC123\"}"
```

**Start Race:**
```bash
curl -X POST http://localhost:8000/race/start ^
  -H "Content-Type: application/json" ^
  -d "{\"race_id\": 1}"
```

**Simulate RFID Scan (End Line):**
```bash
curl -X POST http://localhost:9090/rfid/scan ^
  -H "Content-Type: application/json" ^
  -d "{\"rfid\": \"ABC123\"}"
```

**Get Results:**
```bash
curl http://localhost:8003/races/1/results
```

## Service URLs

| Service | Port | URL |
|---------|------|-----|
| START LINE Backend | 8000 | http://localhost:8000 |
| END LINE Backend | 8002 | http://localhost:8002 |
| REGISTRATION Backend | 8003 | http://localhost:8003 |
| START LINE Proxy | 9090 | http://localhost:9090 |
| END LINE Proxy | 9090 | http://localhost:9090 |

## Laptop Setup Guide

### START LINE LAPTOP

**Services to Run:**
1. START LINE Backend (`run-start-line.bat`)
2. START LINE Proxy (`run-start-proxy.bat`)
3. Frontend (Electron app)

**Configuration:**
- Connect RFID hub to this laptop
- Configure RFID hub to send to: `http://localhost:9090/rfid/scan`

### END LINE LAPTOP

**Services to Run:**
1. END LINE Backend (`run-end-line.bat`)
2. END LINE Proxy (`run-end-proxy.bat`)

**Configuration:**
- Connect RFID hub to this laptop
- Configure RFID hub to send to: `http://localhost:9090/rfid/scan`
- No frontend needed

### REGISTRATION LAPTOP

**Services to Run:**
1. REGISTRATION Backend (`run-registration.bat`)
2. Frontend (Electron app)

**Configuration:**
- No RFID hub
- No proxy needed
- Full frontend access

## Typical Race Day Workflow

### 1. Pre-Race Setup (Registration Laptop)

```
1. Start REGISTRATION backend
2. Start frontend
3. Create race for today
4. Register racers (scan RFIDs, enter names/bib numbers)
```

### 2. Start Line Setup

```
1. Start START LINE backend
2. Start START LINE proxy
3. Connect RFID hub
4. Start frontend (for race start button)
```

### 3. End Line Setup

```
1. Start END LINE backend
2. Start END LINE proxy
3. Connect RFID hub
```

### 4. Pre-Race Check-In

```
- Racers scan at START LINE
- System records them in GRACE state
- No start times yet
```

### 5. Race Start

```
- Click "Start Race" in START LINE frontend
- All GRACE entries → RUNNING with start time
- Late arrivals get individual start times
```

### 6. During Race

```
- START LINE: Records late arrivals, applies 10-second rule
- END LINE: Records finish times for valid runners
```

### 7. Post-Race

```
- View results on REGISTRATION laptop
- Export data
- Generate reports
```

## Troubleshooting

### Services Won't Start

**Check Python:**
```bash
python --version
# Should be 3.11+
```

**Check Dependencies:**
```bash
cd backend/shared
pip install -r requirements.txt
```

### Database Connection Failed

**Check PostgreSQL is running:**
```bash
# Windows
sc query postgresql

# Linux
sudo systemctl status postgresql
```

**Verify database exists:**
```bash
psql -U postgres -l
# Should show rfid_marathon
```

### Port Already in Use

**Find process using port:**
```bash
# Windows
netstat -ano | findstr :8000

# Linux
lsof -i :8000
```

**Kill process:**
```bash
# Windows
taskkill /PID <pid> /F

# Linux
kill -9 <pid>
```

### RFID Scans Not Working

1. Check proxy is running
2. Verify backend URL in proxy
3. Check RFID hub configuration
4. Check proxy logs

## Next Steps

- See [BACKEND_README.md](BACKEND_README.md) for detailed API documentation
- Configure frontend to connect to backends
- Set up RFID hardware
- Train staff on race day procedures

## Support

For issues or questions, check the logs in each service terminal window.
