# RFID Marathon System - Deployment Checklist

## 🚀 Pre-Deployment Setup

### System Requirements

- [ ] **Python 3.11+** installed on all laptops
- [ ] **PostgreSQL 15+** installed and running
- [ ] **Git** installed (optional, for updates)
- [ ] **Network connectivity** between laptops and database
- [ ] **RFID hardware** configured and tested

### Database Setup

- [ ] PostgreSQL service is running
- [ ] Database `rfid_marathon` created
- [ ] User `postgres` has access (or custom user configured)
- [ ] Database credentials configured in `.env` file
- [ ] Run `init-database.bat` successfully
- [ ] Verify `races` table exists

### Python Dependencies

- [ ] Navigate to `backend/shared/`
- [ ] Run: `pip install -r requirements.txt`
- [ ] Verify no errors during installation
- [ ] Test import: `python -c "import flask, psycopg2"`

---

## 💻 Laptop Configuration

### START LINE LAPTOP

#### Hardware Setup
- [ ] RFID hub connected via USB/Network
- [ ] RFID hub configured to send to: `http://localhost:9090/rfid/scan`
- [ ] Test RFID scans are being received

#### Software Setup
- [ ] Backend installed: `backend/start-line/app.py`
- [ ] Proxy installed: `proxy-9090/start-line/proxy.py`
- [ ] Frontend installed (Electron app)
- [ ] Database connection tested
- [ ] Run `run-start-line.bat` - server starts on port 8000
- [ ] Run `run-start-proxy.bat` - proxy starts on port 9090

#### Configuration Files
- [ ] `.env` file configured (if using custom DB settings)
- [ ] `constants.py` - verify START_LINE_BACKEND_PORT = 8000
- [ ] `constants.py` - verify START_LINE_PROXY_PORT = 9090

#### Testing
- [ ] Test health endpoint: `curl http://localhost:8000/health`
- [ ] Test proxy health: `curl http://localhost:9090/health`
- [ ] Test RFID scan simulation
- [ ] Verify logs show successful RFID processing

---

### END LINE LAPTOP

#### Hardware Setup
- [ ] RFID hub connected via USB/Network
- [ ] RFID hub configured to send to: `http://localhost:9090/rfid/scan`
- [ ] Test RFID scans are being received

#### Software Setup
- [ ] Backend installed: `backend/end-line/app.py`
- [ ] Proxy installed: `proxy-9090/end-line/proxy.py`
- [ ] **No frontend required**
- [ ] Database connection tested
- [ ] Run `run-end-line.bat` - server starts on port 8002
- [ ] Run `run-end-proxy.bat` - proxy starts on port 9090

#### Configuration Files
- [ ] `.env` file configured (if using custom DB settings)
- [ ] `constants.py` - verify END_LINE_BACKEND_PORT = 8002
- [ ] `constants.py` - verify END_LINE_PROXY_PORT = 9090

#### Testing
- [ ] Test health endpoint: `curl http://localhost:8002/health`
- [ ] Test proxy health: `curl http://localhost:9090/health`
- [ ] Test RFID scan simulation
- [ ] Verify logs show successful RFID processing

---

### REGISTRATION LAPTOP

#### Hardware Setup
- [ ] **No RFID hub required**
- [ ] Display monitor for registration UI
- [ ] Keyboard/mouse for data entry

#### Software Setup
- [ ] Backend installed: `backend/registration/app.py`
- [ ] Frontend installed (Electron app)
- [ ] **No proxy required**
- [ ] Database connection tested
- [ ] Run `run-registration.bat` - server starts on port 8003

#### Configuration Files
- [ ] `.env` file configured (if using custom DB settings)
- [ ] `constants.py` - verify REGISTRATION_BACKEND_PORT = 8003

#### Testing
- [ ] Test health endpoint: `curl http://localhost:8003/health`
- [ ] Test race creation via API
- [ ] Test racer registration via API
- [ ] Verify frontend connects to backend

---

## 🧪 Integration Testing

### Pre-Race Day Testing

- [ ] Run full integration test: `python test_system.py`
- [ ] All 11 tests pass successfully
- [ ] Verify test race created in database
- [ ] Verify test racers registered
- [ ] Verify results generated correctly

### Manual Testing Scenarios

#### Test 1: Create Race
```bash
curl -X POST http://localhost:8003/races \
  -H "Content-Type: application/json" \
  -d "{\"race_name\": \"Test Race\", \"race_date\": \"2026-01-24\"}"
```
- [ ] Race created successfully
- [ ] Race ID returned
- [ ] Race visible in database

#### Test 2: Register Racer
```bash
curl -X POST http://localhost:8003/races/1/register \
  -H "Content-Type: application/json" \
  -d "{\"rfid\": \"TEST001\", \"racer_name\": \"Test Racer\", \"bib_number\": \"001\"}"
```
- [ ] Racer registered successfully
- [ ] Racer visible in race entries

#### Test 3: Pre-Race RFID Scan
```bash
curl -X POST http://localhost:9090/rfid/scan \
  -H "Content-Type: application/json" \
  -d "{\"rfid\": \"TEST001\"}"
```
- [ ] Scan processed successfully
- [ ] Racer in `grace` state
- [ ] No start time assigned

#### Test 4: Start Race
```bash
curl -X POST http://localhost:8000/race/start \
  -H "Content-Type: application/json" \
  -d "{\"race_id\": 1}"
```
- [ ] Race state changed to `started`
- [ ] All grace entries updated to `running`
- [ ] Start times assigned

#### Test 5: Finish Line Scan
```bash
curl -X POST http://localhost:9090/rfid/scan \
  -H "Content-Type: application/json" \
  -d "{\"rfid\": \"TEST001\"}"
```
- [ ] Finish time recorded
- [ ] Racer state changed to `finished`
- [ ] Duration calculated correctly

#### Test 6: Get Results
```bash
curl http://localhost:8003/races/1/results
```
- [ ] Results returned with rankings
- [ ] Durations correct
- [ ] Sorted by fastest time

---

## 🏃 Race Day Checklist

### T-60 Minutes (1 Hour Before)

**Registration Laptop:**
- [ ] Start Registration backend: `run-registration.bat`
- [ ] Start Frontend application
- [ ] Create today's race
- [ ] Verify race created successfully
- [ ] Open registration form

**Start Line Laptop:**
- [ ] Power on RFID hub
- [ ] Start Start Line backend: `run-start-line.bat`
- [ ] Start Start Line proxy: `run-start-proxy.bat`
- [ ] Test RFID scan
- [ ] Start Frontend (for race start button)

**End Line Laptop:**
- [ ] Power on RFID hub
- [ ] Start End Line backend: `run-end-line.bat`
- [ ] Start End Line proxy: `run-end-proxy.bat`
- [ ] Test RFID scan

### T-30 Minutes (Registration Period)

**Registration Laptop:**
- [ ] Register racers as they arrive
- [ ] Scan RFID + Enter name + Enter bib number
- [ ] Verify each registration successful
- [ ] Monitor for duplicate RFIDs

**Start Line Laptop:**
- [ ] Allow racers to scan at start line
- [ ] Verify scans being logged
- [ ] Racers should be in `grace` state

### T-5 Minutes (Final Check)

**All Laptops:**
- [ ] Verify all services running
- [ ] Check database connectivity
- [ ] Review registered racer count
- [ ] Confirm RFID hubs responding

**Registration Laptop:**
- [ ] Close registration
- [ ] Verify total racer count
- [ ] Communicate count to staff

### T=0 (Race Start)

**Start Line Laptop:**
- [ ] Click "START RACE" button in frontend
- [ ] Verify race state changed to `started`
- [ ] Verify racer count updated
- [ ] Monitor for late arrivals

**End Line Laptop:**
- [ ] Ready to receive finishers
- [ ] Monitor finish scans

### During Race

**Start Line Laptop:**
- [ ] Monitor late arrivals
- [ ] Watch for duplicate scans (10-second rule)
- [ ] Log any issues

**End Line Laptop:**
- [ ] Monitor finish scans
- [ ] Verify durations look reasonable
- [ ] Watch for invalid entries (skip messages)

**Registration Laptop:**
- [ ] Monitor race progress
- [ ] View live statistics
- [ ] Prepare for results generation

### Post-Race

**Registration Laptop:**
- [ ] Generate final results: GET `/races/{id}/results`
- [ ] Verify rankings correct
- [ ] Export results
- [ ] Generate reports
- [ ] Archive race data

**All Laptops:**
- [ ] Keep services running until results confirmed
- [ ] Backup database
- [ ] Save logs

---

## 🔧 Troubleshooting Checklist

### Service Won't Start

- [ ] Check Python version: `python --version`
- [ ] Verify dependencies installed: `pip list`
- [ ] Check port not in use: `netstat -ano | findstr :8000`
- [ ] Review error logs in terminal
- [ ] Verify database connection

### Database Connection Failed

- [ ] PostgreSQL service running: `sc query postgresql`
- [ ] Database exists: `psql -U postgres -l`
- [ ] Credentials correct in `.env`
- [ ] Network connectivity to database server
- [ ] Firewall not blocking port 5432

### RFID Scans Not Processing

- [ ] RFID hub powered on
- [ ] RFID hub configured correctly
- [ ] Proxy server running
- [ ] Backend server running
- [ ] Test with manual curl command
- [ ] Review proxy logs
- [ ] Review backend logs

### Race Won't Start

- [ ] Race exists in database
- [ ] Race state is `idle` (not already started)
- [ ] Frontend connected to correct backend
- [ ] Check backend logs for errors

### Finish Scans Ignored

- [ ] Race state is `started`
- [ ] Racer has `start_time`
- [ ] Racer state is `running`
- [ ] Check end-line backend logs
- [ ] Verify racer exists in race

---

## 📊 Monitoring Checklist

### During Race

- [ ] Monitor backend logs for errors
- [ ] Watch RFID scan frequency
- [ ] Check database query performance
- [ ] Monitor network latency
- [ ] Track finish rate

### Post-Race

- [ ] Review error logs
- [ ] Check for duplicate entries
- [ ] Verify data integrity
- [ ] Confirm all finishers recorded
- [ ] Review timing accuracy

---

## 💾 Backup & Recovery Checklist

### Pre-Race Backup

- [ ] Backup database: `pg_dump rfid_marathon > backup.sql`
- [ ] Save configuration files
- [ ] Document any custom settings

### Post-Race Backup

- [ ] Backup complete database
- [ ] Export race results to CSV/JSON
- [ ] Save all logs
- [ ] Archive frontend screenshots

### Recovery Procedures

- [ ] Database restore: `psql rfid_marathon < backup.sql`
- [ ] Restart services in order: DB → Backends → Proxies
- [ ] Verify data integrity after restore

---

## 📝 Documentation Checklist

### Pre-Deployment

- [ ] Read `BACKEND_README.md` - Complete API documentation
- [ ] Read `QUICKSTART.md` - Setup guide
- [ ] Read `ARCHITECTURE.md` - System design
- [ ] Read `RACE_FLOW_SEQUENCES.md` - Race day flows
- [ ] Review `IMPLEMENTATION_SUMMARY.md`

### Training Materials

- [ ] Train staff on registration process
- [ ] Train staff on race start procedure
- [ ] Demonstrate RFID scanning
- [ ] Practice error scenarios
- [ ] Review troubleshooting guide

---

## ✅ Final Sign-Off

### System Verification

- [ ] All services start without errors
- [ ] All health checks pass
- [ ] Integration tests pass
- [ ] RFID hardware tested
- [ ] Database backup created
- [ ] Staff trained

### Race Day Ready

- [ ] All laptops configured
- [ ] All services tested
- [ ] Backup procedures documented
- [ ] Emergency contacts available
- [ ] Troubleshooting guide accessible

---

## 🎯 Key Contacts

| Role | Name | Contact |
|------|------|---------|
| System Administrator | _________ | _________ |
| Database Admin | _________ | _________ |
| Race Director | _________ | _________ |
| Technical Support | _________ | _________ |

---

## 📞 Emergency Procedures

### If Database Goes Down

1. Check PostgreSQL service status
2. Restart PostgreSQL
3. Verify data integrity
4. Resume operations

### If Start Line Fails

1. Restart Start Line backend
2. Restart Start Line proxy
3. Test RFID scan
4. Manual time recording if needed

### If End Line Fails

1. Restart End Line backend
2. Restart End Line proxy
3. Manual finish time recording
4. Update database after race

---

**Deployment Date**: __________  
**Deployed By**: __________  
**Sign-Off**: __________

---

**Version**: 1.0.0  
**Last Updated**: January 24, 2026  
**Status**: Ready for Deployment ✅
