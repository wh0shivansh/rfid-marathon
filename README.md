# 🏃 RFID Marathon System

Complete backend redesign for RFID-based race tracking with start-time correction, separate laptop roles, and proxy-based RFID ingestion.

---

## 🎯 Quick Links

| Document | Purpose |
|----------|---------|
| **[QUICKSTART.md](QUICKSTART.md)** | ⚡ Get up and running fast |
| **[BACKEND_README.md](BACKEND_README.md)** | 📚 Complete API documentation |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | 🏗️ System architecture & diagrams |
| **[RACE_FLOW_SEQUENCES.md](RACE_FLOW_SEQUENCES.md)** | 📊 Race day flow diagrams |
| **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** | ✅ Pre-deployment checklist |
| **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** | 📋 Implementation overview |

---

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies
```bash
cd backend/shared
pip install -r requirements.txt
```

### 2. Setup Database
```bash
# Create PostgreSQL database
createdb rfid_marathon

# Initialize schema
init-database.bat
```

### 3. Start Services
```bash
# Windows: Start all services at once
start-all-services.bat

# Or start individually:
run-start-line.bat      # Port 8000
run-end-line.bat        # Port 8002
run-registration.bat    # Port 8003
run-start-proxy.bat     # Port 9090
run-end-proxy.bat       # Port 9090
```

### 4. Test the System
```bash
python test_system.py
```

---

## 📋 System Overview

### Architecture

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  START LINE      │  │  END LINE        │  │  REGISTRATION    │
│  LAPTOP          │  │  LAPTOP          │  │  LAPTOP          │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ Frontend (Start) │  │ (No Frontend)    │  │ Frontend (Full)  │
│ Backend (8000)   │  │ Backend (8002)   │  │ Backend (8003)   │
│ Proxy (9090)     │  │ Proxy (9090)     │  │ (No Proxy)       │
│ RFID Hub         │  │ RFID Hub         │  │                  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                      │
         └─────────────────────┴──────────────────────┘
                               │
                       ┌───────▼────────┐
                       │   PostgreSQL   │
                       └────────────────┘
```

### Key Features

✅ **Start-time correction** (10-second rule)  
✅ **Separate laptop roles** (start, end, registration)  
✅ **Proxy-based RFID ingestion** (hardware abstraction)  
✅ **Dynamic per-race tables** (scalability)  
✅ **Real-time race tracking**  
✅ **Automatic rankings**

---

## 🗂️ Project Structure

```
rfid-marathon/
├── backend/
│   ├── shared/              # Shared models & utilities
│   │   ├── models.py        # Race & RaceEntry models
│   │   ├── database.py      # DB connection
│   │   ├── constants.py     # System constants
│   │   └── utils.py         # Helper functions
│   ├── start-line/          # Start line backend (Port 8000)
│   ├── end-line/            # End line backend (Port 8002)
│   └── registration/        # Registration backend (Port 8003)
├── proxy-9090/
│   ├── start-line/          # Start proxy (Port 9090)
│   └── end-line/            # End proxy (Port 9090)
├── frontend/                # Electron app
├── docker-compose.yml       # Docker orchestration
└── test_system.py           # Integration tests
```

---

## 🎯 Laptop Roles

### START LINE LAPTOP
- **Purpose**: Initialize races, handle start line RFID hits
- **Services**: Backend (8000), Proxy (9090), Frontend
- **RFID Hub**: ✓ Connected
- **Logic**: Start-time correction (10-second rule)

### END LINE LAPTOP
- **Purpose**: Record finish times only
- **Services**: Backend (8002), Proxy (9090)
- **RFID Hub**: ✓ Connected
- **Logic**: Validate runner state before recording

### REGISTRATION LAPTOP
- **Purpose**: Race creation, registration, reporting
- **Services**: Backend (8003), Frontend
- **RFID Hub**: ✗ Not needed
- **Logic**: Full CRUD operations, results generation

---

## 🔌 API Endpoints

### START LINE (8000)
- `POST /rfid/hit` - Process RFID scan at start
- `POST /race/start` - Start the race
- `GET /race/today` - Get today's race

### END LINE (8002)
- `POST /rfid/hit` - Process RFID scan at finish
- `GET /race/active` - Get active race
- `GET /race/{id}/finished` - Get finished racers

### REGISTRATION (8003)
- `POST /races` - Create race
- `POST /races/{id}/register` - Register racer
- `GET /races/{id}/results` - Get results with rankings
- `GET /races/{id}/stats` - Get statistics

### PROXIES (9090, 9090)
- `POST /rfid/scan` - Receive RFID from hardware
- `GET /health` - Health check

---

## 🏁 Race Day Workflow

### 1. Pre-Race Setup (T-60 minutes)
```
Registration Laptop:
  ✓ Create race for today
  ✓ Register racers (RFID + name + bib)

Start Line Laptop:
  ✓ Start services
  ✓ Connect RFID hub

End Line Laptop:
  ✓ Start services
  ✓ Connect RFID hub
```

### 2. Check-In (T-5 minutes)
```
Racers scan at START LINE
→ Recorded in GRACE state
→ No start times yet
```

### 3. Race Start (T=0)
```
Click "START RACE" button
→ Race state: idle → started
→ All GRACE entries → RUNNING
→ Start times assigned
```

### 4. During Race
```
START LINE:
  ✓ Late arrivals get individual start times
  ✓ 10-second rule prevents duplicates

END LINE:
  ✓ Records finish times for valid runners
  ✓ Skips invalid entries
```

### 5. Post-Race
```
Registration Laptop:
  ✓ View results with rankings
  ✓ Export data
  ✓ Generate reports
```

---

## 🧪 Testing

### Run Integration Tests
```bash
python test_system.py
```

Tests:
- ✅ Health checks (all services)
- ✅ Race creation
- ✅ Racer registration
- ✅ Pre-race scans
- ✅ Race start
- ✅ Late arrivals
- ✅ Start-time correction
- ✅ Finish line scans
- ✅ Results & rankings

### Manual Testing
```bash
# Create race
curl -X POST http://localhost:8003/races \
  -H "Content-Type: application/json" \
  -d "{\"race_name\": \"Test\", \"race_date\": \"2026-01-24\"}"

# Start race
curl -X POST http://localhost:8000/race/start \
  -H "Content-Type: application/json" \
  -d "{\"race_id\": 1}"

# Simulate RFID scan
curl -X POST http://localhost:9090/rfid/scan \
  -H "Content-Type: application/json" \
  -d "{\"rfid\": \"ABC123\"}"
```

---

## 🐳 Docker Deployment

### Start All Services
```bash
docker-compose up -d
```

### Check Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f
```

### Stop Services
```bash
docker-compose down
```

---

## 📊 Database Schema

### Races Table
```sql
CREATE TABLE races (
    race_id SERIAL PRIMARY KEY,
    race_name VARCHAR(255),
    race_date DATE,
    state VARCHAR(20),  -- 'idle' | 'started'
    created_at TIMESTAMP
);
```

### Per-Race Entries (Dynamic)
```sql
CREATE TABLE race_{race_id}_entries (
    entry_id SERIAL PRIMARY KEY,
    rfid VARCHAR(50) UNIQUE,
    racer_name VARCHAR(255),
    bib_number VARCHAR(50),
    state VARCHAR(20),  -- 'grace' | 'running' | 'finished'
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP
);
```

---

## 🔧 Configuration

### Environment Variables
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rfid_marathon
DB_USER=postgres
DB_PASSWORD=postgres
```

### Port Allocation
| Service | Port |
|---------|------|
| START LINE Backend | 8000 |
| END LINE Backend | 8002 |
| REGISTRATION Backend | 8003 |
| START LINE Proxy | 9090 |
| END LINE Proxy | 9090 |
| PostgreSQL | 5432 |

---

## 🛠️ Troubleshooting

### Services Won't Start
```bash
# Check Python version
python --version  # Should be 3.11+

# Check dependencies
pip list

# Check port availability
netstat -ano | findstr :8000
```

### Database Connection Failed
```bash
# Check PostgreSQL is running
sc query postgresql

# Verify database exists
psql -U postgres -l
```

### RFID Scans Not Working
1. Check proxy is running
2. Verify backend URL in proxy
3. Check RFID hub configuration
4. Review proxy logs

---

## 📚 Documentation

### Essential Reading
1. **[QUICKSTART.md](QUICKSTART.md)** - Start here!
2. **[BACKEND_README.md](BACKEND_README.md)** - API reference
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design

### Advanced Topics
4. **[RACE_FLOW_SEQUENCES.md](RACE_FLOW_SEQUENCES.md)** - Detailed flows
5. **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Production ready
6. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical details

---

## 🎓 Key Concepts

### Start-Time Correction (10-Second Rule)
When a racer scans their RFID after the race starts:
- **< 10 seconds**: Scan ignored (prevents duplicates)
- **> 10 seconds**: Start time updated (late arrival correction)

### Race States
- **idle**: Race created but not started
- **started**: Race in progress

### Racer States
- **grace**: Pre-race, no start time
- **running**: Has start time, racing
- **finished**: Has end time, completed

---

## 🚦 System Status

✅ **Ready for Deployment**

- [x] Complete backend redesign
- [x] All services implemented
- [x] Database schema created
- [x] API endpoints tested
- [x] Integration tests passing
- [x] Documentation complete
- [x] Docker configuration ready

---

## 📞 Support

### Getting Help
1. Check documentation in this repository
2. Review error logs in service terminals
3. Run integration tests to verify setup
4. Check troubleshooting sections

### Reporting Issues
Include:
- Service name (start-line, end-line, registration)
- Error message from logs
- Steps to reproduce
- System configuration

---

## 📜 License

MIT License

---

## 🙏 Acknowledgments

Built with:
- Flask (Python web framework)
- PostgreSQL (Database)
- psycopg2 (PostgreSQL driver)
- Docker (Containerization)

---

**Version**: 1.0.0  
**Last Updated**: January 24, 2026  
**Status**: Production Ready ✅

---

## 🎉 Next Steps

1. ✅ **Read [QUICKSTART.md](QUICKSTART.md)** to get started
2. ✅ **Run `init-database.bat`** to setup database
3. ✅ **Run `start-all-services.bat`** to start services
4. ✅ **Run `python test_system.py`** to verify installation
5. ✅ **Review [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** for production

**Ready to track your first race! 🏁**
