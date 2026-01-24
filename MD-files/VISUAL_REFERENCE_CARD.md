# RFID Hub API - Visual Reference Card

**Print this page and keep at your desk during integration**

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         RFID HUB SETUP                           │
└──────────────────────────────────────────────────────────────────┘

START LINE SETUP                      END LINE SETUP
─────────────────────────────────     ────────────────────────────

RFID Hub (Start)          RFID Hub (End)
      │                        │
      │ HTTP POST              │ HTTP POST
      │ Port 9090              │ Port 9090
      │ /reader                │ /reader
      ▼                        ▼
Start-Line Laptop         End-Line Laptop
┌─────────────────┐      ┌─────────────────┐
│ Proxy:9090      │      │ Proxy:9090      │
│ Backend:8000    │      │ Backend:8002    │
│ Database        │      │ Database        │
└────────┬────────┘      └────────┬────────┘
         │                        │
         │ Syncs                  │
         └────────────┬───────────┘
                      │
            Registration Laptop
            ┌─────────────────┐
            │ Service:8003    │
            │ Central DB      │
            └─────────────────┘
```

---

## Event Flow Diagram

```
VENDOR HUB                    PROXY                  BACKEND
   │                            │                       │
   │ POST /reader               │                       │
   │ {event_type:"tag_read"     │                       │
   │  event_data:[...]}         │                       │
   ├───────────────────────────>│                       │
   │                            │ Parse JSON           │
   │                            │ Check event_type    │
   │                            │ Extract RFID        │
   │                            │ POST /rfid/hit      │
   │                            ├──────────────────────>
   │                            │                      │
   │                            │              Record entry
   │                            │              Update state
   │                            │                      │
   │                            │      HTTP 200 OK    │
   │                            │<──────────────────────┤
   │                            │                      │
   │    HTTP 200 OK             │                      │
   │<───────────────────────────┤                      │
   │                            │                      │
```

---

## Hub Configuration (3 Steps)

```
Step 1: Access Hub Admin Panel
├─ Open: http://<hub-ip>:8088
├─ Login: admin / password
└─ Go to: Settings → Event Posting

Step 2: Configure Start Line
├─ Target URL: http://<start-laptop-ip>:9090/reader
├─ Method: POST
├─ Content-Type: application/json
├─ Events: tag_read ✓, heart_beat ✓
└─ Save & Apply

Step 3: Configure End Line
├─ Target URL: http://<end-laptop-ip>:9090/reader
├─ Method: POST
├─ Content-Type: application/json
├─ Events: tag_read ✓, heart_beat ✓
├─ Save & Apply
└─ Restart Hub
```

---

## Event Types at a Glance

```
┌─────────────────┬──────────────────┬──────────────────┐
│ EVENT TYPE      │ WHEN SENT         │ WHAT IT CONTAINS │
├─────────────────┼──────────────────┼──────────────────┤
│ tag_read        │ RFID detected     │ RFID + metadata  │
│                 │ once per scan     │ (antenna,RSSI)   │
├─────────────────┼──────────────────┼──────────────────┤
│ tag_coming      │ Continuous        │ Same as above    │
│                 │ detection         │ (can duplicate!) │
├─────────────────┼──────────────────┼──────────────────┤
│ heart_beat      │ Every 5-10 sec    │ Count (integer)  │
│                 │ Hub alive signal  │                  │
├─────────────────┼──────────────────┼──────────────────┤
│ gpi_changed     │ GPIO pin changed  │ State array      │
│                 │ (optional)        │                  │
├─────────────────┼──────────────────┼──────────────────┤
│ reader_exception│ Hub error occurs  │ Error code +     │
│                 │                   │ error message    │
└─────────────────┴──────────────────┴──────────────────┘
```

---

## RFID Tag Field Mapping

```
VENDOR HUB SENDS              PROXY EXTRACTS              BACKEND RECEIVES
─────────────────────────     ──────────────────────      ──────────────────
"ep": "ABC123456"    ────┐    RFID = ep or epc    ────>  "rfid": "ABC123456"
"epc": "ABC123456"   ────┤
"at": 1              ────┼──> antenna = at        ────>  "antenna": 1
"rc": 1              ────┼──> read_count = rc     ────>  "read_count": 1
"ri": -65            ────┼──> signal = ri         ────>  "signal_strength": -65
"ft": 1703419200     ────┼──> first_seen = ft    ────>  "first_seen": 1703419200
"lt": 1703419200     ────┼──> last_seen = lt     ────>  "last_seen": 1703419200
"bd": "data"         ────┼──> bank_data = bd     ────>  "bank_data": "data"
"pt": "EPC"          ────┴──> protocol = pt       ────>  "protocol": "EPC"
```

---

## Quick Test Checklist

```
□ Hub can reach proxy?
  telnet <laptop-ip> 9090

□ Proxy running?
  curl http://localhost:9090/health

□ Backend running?
  curl http://localhost:8000/health

□ RFID scan recorded?
  curl -X POST http://localhost:9090/reader \
    -H "Content-Type: application/json" \
    -d '{"event_type":"tag_read","event_data":[{"ep":"TEST"}]}'

□ Response is {"status":"ok"}?
  ✓ Yes = All good!
  ✗ No = Check logs
```

---

## Port Quick Reference

```
┌────────────┬──────┬─────────────────────────────────┐
│ Service    │ Port │ Purpose                         │
├────────────┼──────┼─────────────────────────────────┤
│ Start Proxy│ 9090 │ Receives RFID from hub          │
│ End Proxy  │ 9090 │ Receives RFID from hub          │
├────────────┼──────┼─────────────────────────────────┤
│ Start BE   │ 8000 │ Processes start line scans      │
│ End BE     │ 8002 │ Processes finish line scans     │
│ Reg BE     │ 8003 │ Race management & results       │
├────────────┼──────┼─────────────────────────────────┤
│ Database   │ 5432 │ PostgreSQL (if not local)       │
└────────────┴──────┴─────────────────────────────────┘
```

---

## JSON Payload Examples

### Tag Read Event
```json
{
  "event_type": "tag_read",
  "event_data": [{
    "ep": "RACER_ID",
    "at": 1,
    "rc": 1,
    "ri": -65,
    "ft": 1703419200,
    "lt": 1703419200
  }]
}
```
**Response:** `{"status":"ok","tags_processed":1,"tags_total":1}`

### Heartbeat Event
```json
{
  "event_type": "heart_beat",
  "event_data": 42
}
```
**Response:** `{"status":"ok","heartbeat_received":true}`

### Error Event
```json
{
  "event_type": "reader_exception",
  "event_data": {
    "err_code": 1001,
    "err_string": "Antenna disconnected"
  }
}
```
**Response:** `{"status":"error","error_code":1001}`

---

## Troubleshooting Decision Tree

```
Can you ping hub?
├─ NO → Check network cable, firewall
│
└─ YES → Is proxy running?
   ├─ NO → Start proxy: python proxy.py
   │
   └─ YES → Can you curl /health?
      ├─ NO → Check port 9090/9090, firewall
      │
      └─ YES → Does hub send to proxy?
         ├─ NO → Check hub config (URL, method, port)
         │
         └─ YES → Does proxy log show "Processing RFID"?
            ├─ NO → Check proxy code/logs
            │
            └─ YES → Is backend running?
               ├─ NO → Start backend: python app.py
               │
               └─ YES → Is tag in database?
                  ├─ NO → Check backend logs, database connection
                  │
                  └─ YES → ✓ Everything working!
```

---

## Hub State Health Indicators

```
GET /health response:

{
  "status": "ok",                      ← Proxy is running
  "hub_state": {
    "heartbeat_count": 42,             ← Hub alive (should increment)
    "device_state": "OK",              ← No errors detected
    "gpi_states": "1010",              ← GPIO states (if any)
    "last_heartbeat": "2026-01-24T..." ← Recent timestamp
  }
}
```

**Good signs:**
✓ heartbeat_count incrementing every 5-10 sec
✓ device_state = "OK"
✓ last_heartbeat recent (< 30 seconds ago)

**Bad signs:**
✗ heartbeat_count not changing
✗ device_state contains "ERROR"
✗ last_heartbeat is old

---

## 10-Second Rule Explanation

```
RACER SCANS AT START LINE

Timeline:
────────────────────────────────────────────────

t=0s: First scan
     CREATE entry
     start_time = 0s
     
t=5s: Same racer scans again (false positive)
     SKIP UPDATE (within 10 second window)
     start_time remains 0s
     
t=12s: Third scan (late start correction)
     UPDATE start_time = 12s
     (12 > 0 + 10, so update)

Result:
─────
- No duplicate entries
- Allows correction for late starters
- Exactly 10-second threshold
```

---

## Response Codes Cheat Sheet

```
200 OK
├─ All event types (success or graceful failure)
├─ Always used, even if some tags fail
└─ Safe to ignore/retry

400 Bad Request
├─ Invalid JSON
└─ Missing event_type field

500 Server Error
├─ Unhandled exception in proxy
├─ Check proxy logs
└─ Restart proxy if persistent
```

---

## Commands at a Glance

```bash
# Start proxy
python proxy.py

# Check health
curl http://localhost:9090/health

# Test tag scan
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"event_type":"tag_read","event_data":[{"ep":"TEST"}]}'

# View logs (Docker)
docker logs rfid-marathon-start-proxy

# View logs (standalone)
# Check terminal where you started python

# Kill proxy (if needed)
# Ctrl+C in terminal
```

---

## Common Issues Quick Fix

```
"Connection refused"
→ Proxy not running? Start it: python proxy.py

"No response from hub"
→ Hub config wrong? Check target URL in hub admin panel

"Duplicate entries"
→ Disable tag_coming in hub config (use only tag_read)

"Tags not appearing"
→ Backend running? Check port 8000/8002

"Proxy crashes on startup"
→ Check requirements.txt: pip install -r requirements.txt

"Wrong IP in hub config"
→ Find your IP: ipconfig | grep IPv4
   (Windows) or ifconfig (Linux/Mac)
```

---

## Verification Checklist

```
BEFORE RACE DAY:

□ Hub configured to POST to /reader
□ Hub method set to POST
□ Hub content-type set to application/json
□ Both proxies (9090, 9090) running
□ Both backends (8000, 8002) running
□ Registration (8003) running
□ curl /health returns "ok" for all
□ Test scan shows "tags_processed": 1
□ Database shows entry created
□ No errors in logs
```

**All checked? ✓ Ready for race!**

---

## Need More Help?

```
Quick Start?          → HUB_QUICK_START.md
Setup Guide?          → HUB_INTEGRATION_CHECKLIST.md
Full Details?         → RFID_HUB_INTEGRATION.md
API Specification?    → API_CONTRACT_HUB_PROXY.md
What Changed?         → VENDOR_API_INTEGRATION_SUMMARY.md
Troubleshooting?      → RFID_HUB_INTEGRATION.md (Troubleshooting section)
```

---

## Last Resort Commands

```bash
# Restart everything (nuclear option)
pkill python              # Kill all Python
sleep 2
python proxy.py &         # Restart proxy
python app.py &           # Restart backend

# Check what's running
netstat -an | grep 909    # Find proxy ports
netstat -an | grep 800    # Find backend ports

# Test hub connectivity directly
ping <hub-ip>
telnet <hub-ip> 80        # Test hub port

# Check database
psql -h localhost -U rfid_user -d rfid_marathon
SELECT * FROM races LIMIT 5;  # Check races

# Restart database
docker-compose restart db
```

---

## Print This!

This page fits on one double-sided sheet. Print and:
- Keep at desk during integration
- Reference during troubleshooting
- Share with team members
- Post near RFID hub

---

**System Version:** 2.0 (Vendor API Compliant)  
**Last Updated:** January 24, 2026  
**Status:** ✓ Production Ready

