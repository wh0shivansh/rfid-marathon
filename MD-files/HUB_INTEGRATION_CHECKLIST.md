# RFID Hub Integration Checklist

**Last Updated:** January 24, 2026

---

## Pre-Integration Setup

### Hub Hardware
- [ ] RFID hub physically installed at start line
- [ ] RFID hub physically installed at end line
- [ ] Antennas properly positioned and secured
- [ ] Hub has power and network connectivity
- [ ] Hub IP address is static or reserved in DHCP

### Laptop Setup
- [ ] Start line laptop has fixed IP (or static reservation)
- [ ] End line laptop has fixed IP (or static reservation)
- [ ] Registration laptop has network access to both
- [ ] All laptops can ping each other: `ping <ip>`
- [ ] Firewall allows ports 8000, 8002, 8003, 9090, 9090

### Software Installation
- [ ] Python 3.11+ installed on all laptops
- [ ] Docker and Docker Compose installed
- [ ] PostgreSQL running or Docker will start it
- [ ] All requirements.txt files installed
- [ ] Services can start without errors

---

## Hub Configuration

### Hub Admin Panel

1. **Access Hub Admin**
   - [ ] Open browser to: `http://<hub-ip>:8088` (or vendor port)
   - [ ] Login with admin credentials
   - [ ] Navigate to Settings

2. **Configure Event Posting**
   - [ ] Find "Event Posting" or "Webhook" section
   - [ ] Set **Method:** POST
   - [ ] Set **Target URL (START LINE):** `http://<start-laptop-ip>:9090/reader`
   - [ ] Set **Target URL (END LINE):** `http://<end-laptop-ip>:9090/reader`
   - [ ] Set **Content-Type:** `application/json`
   - [ ] Set **Event Types to Send:**
     - [ ] tag_read (required)
     - [ ] tag_coming (optional)
     - [ ] heart_beat (recommended)
     - [ ] gpi_changed (if available)
     - [ ] reader_exception (recommended)
   - [ ] Enable: Yes
   - [ ] Save settings
   - [ ] **Restart hub service**

3. **Verify Hub Configuration**
   - [ ] Confirm URLs saved correctly
   - [ ] Check that HTTPS is not required (or use http if allowed)
   - [ ] Note any timeout settings (suggest 5-10 seconds)
   - [ ] Note any retry settings

---

## Start Line Laptop Configuration

### Services Setup

1. **Start Proxy (Port 9090)**
   ```bash
   cd e:\Innogative\rfid-marathon\proxy-9090\start-line
   python -m pip install -r requirements.txt
   python proxy.py
   ```
   - [ ] Proxy starts without error
   - [ ] Logs show: "Starting START LINE Proxy on port 9090"
   - [ ] Logs show: "Backend URL: http://localhost:8000"

2. **Start Backend (Port 8000)**
   ```bash
   cd e:\Innogative\rfid-marathon\backend\start-line
   python -m pip install -r requirements.txt
   python app.py
   ```
   - [ ] Backend starts without error
   - [ ] Logs show: "Running on http://0.0.0.0:8000"
   - [ ] Database connection successful

3. **Verify Services Running**
   ```bash
   curl http://localhost:9090/health
   curl http://localhost:8000/health
   ```
   - [ ] Both return HTTP 200
   - [ ] Both include `"status": "ok"`

---

## End Line Laptop Configuration

### Services Setup

1. **Start Proxy (Port 9090)**
   ```bash
   cd e:\Innogative\rfid-marathon\proxy-9090\end-line
   python -m pip install -r requirements.txt
   python proxy.py
   ```
   - [ ] Proxy starts without error
   - [ ] Logs show: "Starting END LINE Proxy on port 9090"
   - [ ] Logs show: "Backend URL: http://localhost:8002"

2. **Start Backend (Port 8002)**
   ```bash
   cd e:\Innogative\rfid-marathon\backend\end-line
   python -m pip install -r requirements.txt
   python app.py
   ```
   - [ ] Backend starts without error
   - [ ] Logs show: "Running on http://0.0.0.0:8002"
   - [ ] Database connection successful

3. **Verify Services Running**
   ```bash
   curl http://localhost:9090/health
   curl http://localhost:8002/health
   ```
   - [ ] Both return HTTP 200
   - [ ] Both include `"status": "ok"`

---

## Registration Laptop Configuration

### Services Setup

1. **Start Registration Service (Port 8003)**
   ```bash
   cd e:\Innogative\rfid-marathon\backend\registration
   python -m pip install -r requirements.txt
   python app.py
   ```
   - [ ] Service starts without error
   - [ ] Logs show: "Running on http://0.0.0.0:8003"
   - [ ] Database connection successful

2. **Verify Service Running**
   ```bash
   curl http://localhost:8003/health
   ```
   - [ ] Returns HTTP 200
   - [ ] Includes `"status": "ok"`

---

## Integration Testing

### Test 1: Hub to Proxy Connection

**From Start Line Laptop:**
```bash
# Check if hub can reach proxy
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "tag_read",
    "event_data": [{
      "ep": "TEST123456",
      "epc": "TEST123456",
      "at": 1,
      "rc": 1,
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }]
  }'
```

- [ ] Response: `{"status": "ok", "tags_processed": 1, "tags_total": 1}`
- [ ] Check proxy logs for: "Processing RFID: TEST123456"
- [ ] Check backend logs for: "RFID hit recorded"

**From End Line Laptop:**
```bash
# Same test but port 9090
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "tag_read",
    "event_data": [{
      "ep": "TEST987654",
      "epc": "TEST987654",
      "at": 1,
      "rc": 1,
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }]
  }'
```

- [ ] Response: `{"status": "ok", "tags_processed": 1, "tags_total": 1}`
- [ ] Backend logs show entry recorded

---

### Test 2: Database Recording

**Verify Entry in Database:**

Start Line:
```bash
# Check recent entries
curl http://localhost:8000/race/today
```
- [ ] Response includes race ID
- [ ] Response includes at least 1 entry with RFID: TEST123456

End Line:
```bash
# Check recent finished entries
curl http://localhost:8002/race/active
```
- [ ] Response includes active race
- [ ] Check for entries

---

### Test 3: End-to-End Race Simulation

1. **Create a Test Race** (from registration laptop)
   ```bash
   curl -X POST http://localhost:8003/races \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Integration Test Race",
       "distance_meters": 5000,
       "date": "2026-01-24"
     }'
   ```
   - [ ] Response includes race_id
   - [ ] Note the race_id

2. **Register Test Participants**
   ```bash
   curl -X POST http://localhost:8003/races/<race_id>/register \
     -H "Content-Type: application/json" \
     -d '{
       "rfid": "TEST123456",
       "name": "Test Runner 1"
     }'
   ```
   - [ ] Response: success

3. **Simulate Start Line Scan**
   ```bash
   curl -X POST http://localhost:9090/reader \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "tag_read",
       "event_data": [{
         "ep": "TEST123456",
         "epc": "TEST123456",
         "at": 1,
         "rc": 1,
         "pt": "EPC",
         "ri": -65,
         "ft": 1703419200,
         "lt": 1703419200
       }]
     }'
   ```
   - [ ] Logs show tag processed

4. **Start the Race**
   ```bash
   curl -X POST http://localhost:8000/race/start \
     -H "Content-Type: application/json" \
     -d '{
       "race_id": "<race_id>"
     }'
   ```
   - [ ] Response: race state changed to STARTED

5. **Simulate End Line Scan**
   ```bash
   # Wait a few seconds to simulate running time
   sleep 5
   
   curl -X POST http://localhost:9090/reader \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "tag_read",
       "event_data": [{
         "ep": "TEST123456",
         "epc": "TEST123456",
         "at": 1,
         "rc": 1,
         "pt": "EPC",
         "ri": -65,
         "ft": 1703419205,
         "lt": 1703419205
       }]
     }'
   ```
   - [ ] Logs show tag processed
   - [ ] Backend records finish

6. **Get Results**
   ```bash
   curl http://localhost:8003/races/<race_id>/results
   ```
   - [ ] Response includes completed runner
   - [ ] Shows start_time and end_time
   - [ ] Shows duration (should be ~5 seconds)

---

### Test 4: Start-Time Correction (10-Second Rule)

This tests the key feature: within 10 seconds, same RFID is not recorded twice.

1. **First Detection** (at 0 seconds)
   ```bash
   curl -X POST http://localhost:9090/reader \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "tag_read",
       "event_data": [{
         "ep": "CORRECTION_TEST",
         "epc": "CORRECTION_TEST",
         "at": 1,
         "rc": 1,
         "pt": "EPC",
         "ri": -65,
         "ft": 1703419200,
         "lt": 1703419200
       }]
     }'
   ```

2. **Second Detection** (at 5 seconds - within threshold)
   ```bash
   sleep 5
   
   curl -X POST http://localhost:9090/reader \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "tag_read",
       "event_data": [{
         "ep": "CORRECTION_TEST",
         "epc": "CORRECTION_TEST",
         "at": 1,
         "rc": 2,
         "pt": "EPC",
         "ri": -62,
         "ft": 1703419200,
         "lt": 1703419205
       }]
     }'
   ```
   - [ ] Logs show: "Skipping update, within 10 second threshold"
   - [ ] Start time unchanged

3. **Third Detection** (at 12 seconds - beyond threshold)
   ```bash
   sleep 7
   
   curl -X POST http://localhost:9090/reader \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "tag_read",
       "event_data": [{
         "ep": "CORRECTION_TEST",
         "epc": "CORRECTION_TEST",
         "at": 1,
         "rc": 1,
         "pt": "EPC",
         "ri": -71,
         "ft": 1703419200,
         "lt": 1703419212
       }]
     }'
   ```
   - [ ] Logs show: "Start time corrected"
   - [ ] Start time updated to match new first_seen

---

## Network Testing

### Test Hub IP Connectivity

**From Start Line Laptop:**
```bash
ping <hub-ip>
ipconfig getifaddr en0  # Get your IP
telnet <hub-ip> 80      # Test connectivity
```
- [ ] Hub responds to ping
- [ ] Laptop IP is noted
- [ ] Can telnet to hub

### Test Proxy Accessibility from Hub

**From Hub (if possible):**
```bash
# Replace <laptop-ip> with actual IP
curl http://<start-laptop-ip>:9090/health
curl http://<end-laptop-ip>:9090/health
```
- [ ] Both return HTTP 200
- [ ] Both show proxy is running

### Test Firewall Rules

```bash
# Check if port is open (from hub machine)
netstat -an | grep 9090
netstat -an | grep 9090

# Or test with telnet
telnet <start-laptop-ip> 9090
telnet <end-laptop-ip> 9090
```
- [ ] Ports are listening
- [ ] Can connect from hub

---

## Live Race Preparation

### Day Before Race

- [ ] All services started and running
- [ ] Test RFID tags available
- [ ] Network connectivity verified
- [ ] Database backups taken
- [ ] Documentation printed

### Race Morning

1. **Start Services** (in order):
   ```bash
   # Start Line Laptop
   start-all-services.bat  # If using Windows batch
   
   # Or manually:
   # Terminal 1: python proxy.py (from start-line proxy dir)
   # Terminal 2: python app.py (from start-line backend dir)
   ```

2. **Verify Health**
   ```bash
   curl http://localhost:9090/health
   curl http://localhost:8000/health
   curl http://localhost:8002/health
   curl http://localhost:8003/health
   ```
   - [ ] All services respond with HTTP 200

3. **Test with Actual RFID Tags**
   - [ ] Take 2-3 test tags
   - [ ] Scan at start line (verify recorded)
   - [ ] Move to end line, scan (verify recorded)
   - [ ] Check registration system for entry
   - [ ] Verify no duplicates within 10-second window

4. **Monitor Logs**
   - Keep proxy and backend terminals visible
   - Watch for errors during race
   - Note any missing RFID reads

---

## Troubleshooting During Race

### No RFID Detected

1. [ ] Check hub admin panel - is event posting enabled?
2. [ ] Check hub logs for errors
3. [ ] Verify proxy port in hub configuration
4. [ ] Check firewall between hub and laptop
5. [ ] Restart proxy service

### Duplicate Entries

1. [ ] Check start-time correction logic in logs
2. [ ] Verify 10-second rule is being applied
3. [ ] Check if same tag being sent by hub twice
4. [ ] Review proxy logs for duplicate forwards

### Wrong Timestamps

1. [ ] Check system clock on hub: `date`
2. [ ] Check system clock on laptop: `date`
3. [ ] Sync if different: `ntpdate pool.ntp.org`
4. [ ] Verify first_seen/last_seen from hub

### Database Errors

1. [ ] Check if PostgreSQL is running
2. [ ] Check database connection logs
3. [ ] Verify network path to central DB (if not local)
4. [ ] Check disk space on database machine

---

## Post-Race

- [ ] Export results from registration system
- [ ] Verify all participants have entries
- [ ] Check for any errors in logs
- [ ] Backup database
- [ ] Archive logs

---

## Quick Reference Commands

### Start All Services

**Start Line Laptop:**
```bash
cd backend/start-line && python app.py &
cd proxy-9090/start-line && python proxy.py &
```

**End Line Laptop:**
```bash
cd backend/end-line && python app.py &
cd proxy-9090/end-line && python proxy.py &
```

**Registration Laptop:**
```bash
cd backend/registration && python app.py &
```

### Health Checks

```bash
curl http://localhost:9090/health  # Start proxy
curl http://localhost:9090/health  # End proxy
curl http://localhost:8000/health  # Start backend
curl http://localhost:8002/health  # End backend
curl http://localhost:8003/health  # Registration
```

### Test RFID Scan

```bash
# Start line
curl -X POST http://localhost:9090/test \
  -H "Content-Type: application/json" \
  -d '{"rfid": "TEST123", "antenna": 1}'

# End line
curl -X POST http://localhost:9090/test \
  -H "Content-Type: application/json" \
  -d '{"rfid": "TEST123", "antenna": 1}'
```

### View Logs

```bash
# If running in Docker
docker logs rfid-marathon-start-proxy
docker logs rfid-marathon-start-backend
docker logs rfid-marathon-end-proxy
docker logs rfid-marathon-end-backend

# If running standalone
# Check terminal output where services started
```

---

## Status Summary

After completing all checklist items, you should have:

- [ ] ✅ RFID hub configured to POST to both proxies
- [ ] ✅ Start line proxy (9090) receiving and forwarding scans
- [ ] ✅ End line proxy (9090) receiving and forwarding scans
- [ ] ✅ Start line backend (8000) recording entries
- [ ] ✅ End line backend (8002) recording finishes
- [ ] ✅ Registration service (8003) managing races
- [ ] ✅ Database recording all events
- [ ] ✅ 10-second start-time correction working
- [ ] ✅ Results accurately calculated
- [ ] ✅ Network connectivity verified
- [ ] ✅ Ready for live race

**System Status:** 🟢 READY FOR RACE

