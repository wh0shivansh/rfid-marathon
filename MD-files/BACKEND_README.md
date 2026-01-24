# RFID Marathon System - Backend Architecture

## Overview

Complete backend redesign for RFID-based race tracking with start-time correction, separate laptop roles, and proxy-based RFID ingestion.

## Architecture

### System Components

The system is divided into **3 separate backend instances** that never share runtime:

1. **START LINE LAPTOP**
   - Backend: `backend/start-line/` (Port 8000)
   - Proxy: `proxy-9090/start-line/` (Port 9090)
   - Frontend: Race start control
   - Purpose: Initialize races, handle start line RFID hits, manage start-time correction

2. **END LINE LAPTOP**
   - Backend: `backend/end-line/` (Port 8002)
   - Proxy: `proxy-9090/end-line/` (Port 9090)
   - No Frontend
   - Purpose: Record end times only for valid running racers

3. **REGISTRATION LAPTOP**
   - Backend: `backend/registration/` (Port 8003)
   - Frontend: Full UI
   - No Proxy
   - Purpose: Race creation, racer registration, dashboard, reporting

### Shared Module

`backend/shared/` contains:
- Database models (Race, RaceEntry)
- Database connection utilities
- Constants and utilities
- **Used by all backends but no shared runtime**

## Folder Structure

```
rfid-marathon/
├── backend/
│   ├── shared/              # Shared models & utilities
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── utils.py
│   │   └── requirements.txt
│   ├── start-line/          # Start line backend
│   │   ├── app.py
│   │   └── Dockerfile
│   ├── end-line/            # End line backend
│   │   ├── app.py
│   │   └── Dockerfile
│   └── registration/        # Registration backend
│       ├── app.py
│       └── Dockerfile
├── proxy-9090/
│   ├── requirements.txt
│   ├── start-line/          # Start line proxy
│   │   ├── proxy.py
│   │   └── Dockerfile
│   └── end-line/            # End line proxy
│       ├── proxy.py
│       └── Dockerfile
├── frontend/                # Electron app
└── docker-compose.yml
```

## Database Schema

### Races Table

```sql
CREATE TABLE races (
    race_id SERIAL PRIMARY KEY,
    race_name VARCHAR(255) NOT NULL,
    race_date DATE NOT NULL,
    state VARCHAR(20) DEFAULT 'idle',  -- 'idle' | 'started'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Per-Race Entries Table (Dynamic)

Table name: `race_{race_id}_entries`

```sql
CREATE TABLE race_{race_id}_entries (
    entry_id SERIAL PRIMARY KEY,
    rfid VARCHAR(50) UNIQUE NOT NULL,
    racer_name VARCHAR(255),
    bib_number VARCHAR(50),
    state VARCHAR(20) DEFAULT 'grace',  -- 'grace' | 'running' | 'finished'
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### START LINE Backend (Port 8000)

#### `POST /rfid/hit`
Handle RFID scan at start line

**Request:**
```json
{
  "rfid": "ABC123456"
}
```

**Logic:**
- Race IDLE → Save in grace state (no start time)
- Race STARTED:
  - New RFID → Create entry with start_time = now, state = running
  - Existing RFID → Apply 10-second rule:
    - If time_diff > 10s → Update start_time
    - Else → Ignore scan

#### `POST /race/start`
Start the race

**Request:**
```json
{
  "race_id": 1  // Optional, defaults to today's race
}
```

**Logic:**
- Set race state = started
- Update all grace entries to running with start_time = now

#### `GET /race/today`
Get today's race information

#### `GET /race/{race_id}/entries`
Get all entries for a race

---

### END LINE Backend (Port 8002)

#### `POST /rfid/hit`
Handle RFID scan at end line

**Request:**
```json
{
  "rfid": "ABC123456"
}
```

**Logic:**
- Find active race
- Get racer entry by RFID
- Validate:
  - state == running
  - start_time IS NOT NULL
- If valid → Update end_time, state = finished
- Else → Skip silently

#### `GET /race/active`
Get currently active race

#### `GET /race/{race_id}/finished`
Get all finished racers

---

### REGISTRATION Backend (Port 8003)

#### Race Management

- `GET /races` - Get all races
- `POST /races` - Create new race
- `GET /races/{race_id}` - Get race by ID

**Create Race:**
```json
{
  "race_name": "Marathon 2026",
  "race_date": "2026-01-24"
}
```

#### Racer Registration

- `POST /races/{race_id}/register` - Register a racer
- `GET /races/{race_id}/racers` - Get all racers

**Register Racer:**
```json
{
  "rfid": "ABC123456",
  "racer_name": "John Doe",
  "bib_number": "101"
}
```

#### Results & Reporting

- `GET /races/{race_id}/results` - Get race results with rankings
- `GET /races/{race_id}/stats` - Get race statistics
- `GET /dashboard` - Get dashboard overview

---

### Proxy Servers (Port 9090 & 9090)

#### `POST /rfid/scan`
Receive RFID from hardware and forward to backend

**Request:**
```json
{
  "rfid": "ABC123456",
  "timestamp": "2026-01-24T10:30:00"  // optional
}
```

#### `POST /test`
Test endpoint to simulate RFID scans

## Race Flow

### 1. Race Creation (Registration Laptop)
```
POST /races
{
  "race_name": "Marathon 2026",
  "race_date": "2026-01-24"
}
```

### 2. Racer Registration (Registration Laptop)
```
POST /races/1/register
{
  "rfid": "ABC123",
  "racer_name": "John Doe",
  "bib_number": "101"
}
```

### 3. Pre-Race RFID Scans (Start Line)
- Race state: `idle`
- RFID scans → Saved in `grace` state
- No start times assigned yet

### 4. Race Start (Start Line Frontend)
```
POST /race/start
{
  "race_id": 1
}
```
- Race state → `started`
- All grace entries → `running` with start_time = now

### 5. Late Arrivals (Start Line)
- New RFID → Create with start_time = now
- Existing RFID → Apply 10-second rule

### 6. Finish Line Scans (End Line)
- Validate: state = running, start_time exists
- Update: end_time = now, state = finished

### 7. Results (Registration Laptop)
```
GET /races/1/results
```
- Returns ranked results by duration

## Running the System

### Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Services:**
- postgres: Port 5432
- start-line-backend: Port 8000
- end-line-backend: Port 8002
- registration-backend: Port 8003
- start-line-proxy: Port 9090
- end-line-proxy: Port 9090

### Manual Setup

#### 1. Setup Database
```bash
# Install PostgreSQL
# Create database
createdb rfid_marathon
```

#### 2. Install Dependencies
```bash
cd backend/shared
pip install -r requirements.txt
```

#### 3. Run Start Line
```bash
cd backend/start-line
python app.py
# Runs on http://localhost:8000
```

#### 4. Run End Line
```bash
cd backend/end-line
python app.py
# Runs on http://localhost:8002
```

#### 5. Run Registration
```bash
cd backend/registration
python app.py
# Runs on http://localhost:8003
```

#### 6. Run Proxies
```bash
# Start line proxy
cd proxy-9090/start-line
python proxy.py
# Runs on http://localhost:9090

# End line proxy
cd proxy-9090/end-line
python proxy.py
# Runs on http://localhost:9090
```

## Testing

### Test Start Line RFID
```bash
curl -X POST http://localhost:9090/rfid/scan \
  -H "Content-Type: application/json" \
  -d '{"rfid": "TEST123"}'
```

### Test End Line RFID
```bash
curl -X POST http://localhost:9090/rfid/scan \
  -H "Content-Type: application/json" \
  -d '{"rfid": "TEST123"}'
```

### Create Test Race
```bash
curl -X POST http://localhost:8003/races \
  -H "Content-Type: application/json" \
  -d '{
    "race_name": "Test Marathon",
    "race_date": "2026-01-24"
  }'
```

### Start Race
```bash
curl -X POST http://localhost:8000/race/start \
  -H "Content-Type: application/json" \
  -d '{"race_id": 1}'
```

## Key Features

### Start Time Correction (10-Second Rule)
- Prevents accidental duplicate scans within 10 seconds
- Allows late starters to correct their start time
- Logic in: `backend/start-line/app.py`

### Separate Backend Instances
- No shared runtime between laptops
- Independent deployments
- Isolated failures

### Proxy-Based RFID Ingestion
- Hardware → Proxy (9090/9090) → Backend (8000/8002)
- Decouples RFID hardware from business logic
- Easy to swap RFID hardware

### Dynamic Per-Race Tables
- Each race gets its own entries table
- Better performance for large events
- Clean data separation

## Environment Variables

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rfid_marathon
DB_USER=postgres
DB_PASSWORD=postgres
```

## Migration from Old Backend

⚠️ **Important:** This is a complete replacement, not a migration.

- Old backend in `backend/` (root) is deprecated
- New architecture in `backend/start-line/`, `backend/end-line/`, `backend/registration/`
- No code imports from old backend
- Database schema is different
- Re-register all racers in new system

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check environment variables
- Verify network connectivity

### Proxy Not Forwarding
- Check BACKEND_URL in proxy environment
- Ensure backend is running and healthy
- Check proxy logs

### RFID Scans Not Recording
- Verify race state (idle vs started)
- Check racer state and start_time
- Review backend logs

## License

MIT License
