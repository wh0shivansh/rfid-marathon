# Hub Integration - Quick Start (5 Minutes)

**Last Updated:** January 24, 2026  
**For:** RFID Hub Setup Engineers

---

## TL;DR - The Essentials

### What Changed
- Proxy now accepts POST to `/reader` (not `/rfid/scan`)
- Handles vendor's event format with multiple event types
- Fully backward compatible with existing backend

### What to Do

1. **Configure Hub** (admin panel)
   - Set Target URL: `http://<laptop-ip>:9090/reader` (start line)
   - Set Target URL: `http://<laptop-ip>:9090/reader` (end line)
   - Set Method: POST
   - Set Content-Type: application/json
   - Save and restart hub

2. **Verify Connectivity**
   ```bash
   curl http://localhost:9090/health
   curl http://localhost:9090/health
   ```

3. **Test with RFID Tag**
   - Scan at start line
   - Check logs: "Processing RFID: [tag_id]"
   - Tag appears in backend database

---

## 10-Minute Integration Steps

### Step 1: Hub Configuration (3 minutes)

**Access Hub Admin Panel:**
1. Open browser: `http://<hub-ip>:8088` (or vendor port)
2. Login with admin credentials
3. Go to Settings → Event Posting

**Configure Start Line Hub:**
- Target URL: `http://<start-line-laptop-ip>:9090/reader`
- Method: POST
- Content-Type: application/json
- Click: Enable
- Click: Save

**Configure End Line Hub:**
- Target URL: `http://<end-line-laptop-ip>:9090/reader`
- Method: POST
- Content-Type: application/json
- Click: Enable
- Click: Save

**Restart Hub**

### Step 2: Verify Services Running (2 minutes)

**Check All Services:**
```bash
# Start line
curl http://localhost:9090/health
curl http://localhost:8000/health

# End line
curl http://localhost:9090/health
curl http://localhost:8002/health

# Registration
curl http://localhost:8003/health
```

All should return: `{"status": "ok", ...}`

### Step 3: Test with Real Tags (5 minutes)

**At Start Line:**
1. Hold RFID tag near antenna
2. Check proxy logs: should see "Processing RFID: [ID]"
3. Check backend logs: should see "Entry recorded"
4. Tag should appear in database

**At End Line:**
1. Hold same RFID tag near antenna
2. Check proxy logs: should see tag
3. Check backend logs: should see finish recorded
4. Tag should show in results

---

## Vendor API Quick Reference

### What the Hub Sends

```json
{
  "event_type": "tag_read",
  "event_data": [{
    "ep": "TAG_ID_HERE",
    "at": 1,
    "rc": 1,
    "ri": -65,
    "ft": 1703419200,
    "lt": 1703419200
  }]
}
```

### What the Proxy Returns

```json
{
  "status": "ok",
  "tags_processed": 1,
  "tags_total": 1
}
```

### Other Event Types

```json
// Heartbeat
{"event_type": "heart_beat", "event_data": 42}

// GPIO changed
{"event_type": "gpi_changed", "event_data": [{"state": "1"}]}

// Error
{"event_type": "reader_exception", "event_data": {"err_code": 1001, "err_string": "..."}}
```

---

## Quick Troubleshooting

### Hub Not Posting

**Check:**
1. Hub admin panel: is URL correct?
2. Firewall: can hub reach laptop:9090?
3. Proxy: is it running?
4. Test: `telnet <laptop-ip> 9090`

**Fix:**
1. Verify IP (not localhost if hub is external)
2. Check firewall rules
3. Restart hub

### Tags Not Recorded

**Check:**
1. Is hub posting? (check proxy logs)
2. Is backend running? (check backend logs)
3. Is database working? (check for SQL errors)

**Test:**
```bash
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "tag_read",
    "event_data": [{
      "ep": "MANUAL_TEST",
      "at": 1,
      "rc": 1,
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }]
  }'
```

Expected: `{"status": "ok", "tags_processed": 1, "tags_total": 1}`

### Duplicate Entries

**Cause:** Hub sending both `tag_read` and `tag_coming`

**Fix:** In hub admin panel, disable `tag_coming` event

---

## File Organization

```
New Documentation:
├── RFID_HUB_INTEGRATION.md          (Full guide, 6000+ lines)
├── HUB_INTEGRATION_CHECKLIST.md     (Step-by-step, 800 lines)
├── API_CONTRACT_HUB_PROXY.md        (API spec, 1000 lines)
└── VENDOR_API_INTEGRATION_SUMMARY.md (This update, 400 lines)

Updated Files:
├── proxy-9090/start-line/proxy.py   (Now uses /reader endpoint)
├── proxy-9090/end-line/proxy.py     (Now uses /reader endpoint)
└── backend/database/migrations.py   (Added vendor API docs)

```

---

## What Each Proxy Does

### Start Line Proxy (Port 9090)
- Receives POST from hub at `/reader`
- Extracts RFID and metadata
- Forwards to start-line backend (8000)
- Tracks hub health

### End Line Proxy (Port 9090)
- Receives POST from hub at `/reader`
- Extracts RFID and metadata
- Forwards to end-line backend (8002)
- Tracks hub health

Both proxies:
- Accept all 5 event types
- Handle errors gracefully
- Always return 200 OK to hub
- Log all events
- Never duplicate entries (10-second rule)

---

## Network Setup Example

```
        RFID Hub (Start)
              │
              │ POST /reader
              │ Port 9090
              │
              ▼
        Laptop (Start Line)
        ┌─────────────┐
        │Proxy (9090) │
        └──────┬──────┘
               │
               │ HTTP /rfid/hit
               │ Port 8000
               │
               ▼
        Backend (8000)
        
        
        RFID Hub (End)
              │
              │ POST /reader
              │ Port 9090
              │
              ▼
        Laptop (End Line)
        ┌─────────────┐
        │Proxy (9090) │
        └──────┬──────┘
               │
               │ HTTP /rfid/hit
               │ Port 8002
               │
               ▼
        Backend (8002)
```

---

## Key Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Proxy Response Time | < 100ms | Should be fast |
| Hub Heartbeat Interval | 5-10s | Verify connectivity |
| Start-Time Correction Window | 10 seconds | Prevents duplicates |
| Maximum Tags per POST | Unlimited | Tested with 10+ |
| Network Latency | < 500ms | Acceptable |

---

## Common Hub Settings

### Typical Configuration

| Setting | Value |
|---------|-------|
| Event Posting | Enabled |
| Method | POST |
| Content-Type | application/json |
| Target URL | http://[laptop-ip]:9090/reader |
| Timeout | 5-10 seconds |
| Retry | 3 attempts |
| tag_read | Enable |
| tag_coming | Disable (causes duplicates) |
| heart_beat | Enable |
| gpi_changed | As needed |
| reader_exception | Enable |

---

## Commands You'll Need

### Start Services
```bash
cd backend/start-line && python app.py &
cd proxy-9090/start-line && python proxy.py &
```

### Check Health
```bash
curl http://localhost:9090/health
curl http://localhost:8000/health
```

### Manual Test
```bash
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"event_type":"tag_read","event_data":[{"ep":"TEST","at":1,"rc":1,"ri":-65,"ft":1703419200,"lt":1703419200}]}'
```

### Check Logs
```bash
docker logs rfid-marathon-start-proxy
docker logs rfid-marathon-start-backend
```

---

## Documentation Map

**Just Getting Started?**
→ Read this document (5 min)

**Need Setup Instructions?**
→ Read `HUB_INTEGRATION_CHECKLIST.md` (30 min)

**Need Full Details?**
→ Read `RFID_HUB_INTEGRATION.md` (1 hour)

**Need API Specification?**
→ Read `API_CONTRACT_HUB_PROXY.md` (30 min)

**Want Implementation Summary?**
→ Read `VENDOR_API_INTEGRATION_SUMMARY.md` (15 min)

---

## Before You Start

✅ Check: Proxy files exist in `proxy-9090/start-line/` and `proxy-9090/end-line/`  
✅ Check: Backend files exist in `backend/start-line/`, `backend/end-line/`, `backend/registration/`  
✅ Check: Python 3.11+ installed  
✅ Check: Database is running or Docker will start it  
✅ Check: Hub has network access to laptop IPs  
✅ Check: No firewall blocking ports 9090, 9090, 8000, 8002, 8003  

---

## Success Checklist

- [ ] Hub configured to POST to `/reader`
- [ ] Both proxies responding to `/health`
- [ ] Both backends responding to `/health`
- [ ] Manual test RFID scan works
- [ ] Tag appears in database
- [ ] No errors in logs
- [ ] Hub heartbeat being received

If all checked ✅ you're ready for production!

---

## Emergency Contacts

If something breaks:
1. Check proxy logs for errors
2. Check backend logs for errors
3. Test hub connectivity with curl
4. Restart proxy service
5. Restart backend service
6. Check firewall and network

See `RFID_HUB_INTEGRATION.md` Troubleshooting section for detailed help.

---

## Summary

The RFID hub now communicates with the proxy via the vendor-standard `/reader` endpoint. The proxy handles all event types, forwards RFID data to the backend, and tracks hub health. Everything is tested and documented.

**You are ready to integrate!** 🚀

