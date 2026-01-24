# RFID Hub Vendor Integration Guide

**Last Updated:** January 24, 2026  
**System Version:** 2.0 (Vendor API Compliant)  
**Vendor:** RFID Hub Hardware (Tag Server)

---

## Table of Contents

1. [Overview](#overview)
2. [Vendor API Specification](#vendor-api-specification)
3. [Event Types](#event-types)
4. [Tag Data Structure](#tag-data-structure)
5. [Full Payload Examples](#full-payload-examples)
6. [Proxy Server Processing](#proxy-server-processing)
7. [Integration Points](#integration-points)
8. [Network Configuration](#network-configuration)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The RFID hub communicates with our proxy servers via **HTTP POST** requests. The vendor provides a Tag Server that sends events to a `/reader` endpoint.

### Key Points:
- **Protocol:** HTTP/HTTPS
- **Method:** POST
- **Endpoint:** `/reader`
- **Content-Type:** `application/json`
- **Port Configuration:**
  - Start Line Hub → Port 9090 (proxy)
  - End Line Hub → Port 9090 (proxy)

---

## Vendor API Specification

The vendor's tag server sends event notifications with this structure:

```json
{
  "event_type": "tag_read|tag_coming|heart_beat|gpi_changed|reader_exception",
  "event_data": [...]
}
```

### Endpoint Details:

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | String | Type of event from hub |
| `event_data` | Array/Object | Event-specific data (see Event Types) |

### Hub Configuration:

Configure your RFID hub (vendor settings) to POST to:

**Start Line:**
```
http://<laptop-ip>:9090/reader
```

**End Line:**
```
http://<laptop-ip>:9090/reader
```

---

## Event Types

### 1. Tag Read / Tag Coming

**Event Type:** `tag_read` or `tag_coming`

Sent when RFID tags are detected by the hub.

```json
{
  "event_type": "tag_read",
  "event_data": [
    {
      "ep": "ABC123456789",
      "epc": "ABC123456789",
      "at": 1,
      "rc": 1,
      "bd": "user_bank_data",
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }
  ]
}
```

| Field | Name | Type | Range | Description |
|-------|------|------|-------|-------------|
| `ep` | EPC | String | Any | Tag Electronic Product Code (primary ID) |
| `epc` | EPC Alt | String | Any | Alternative EPC field (fallback) |
| `at` | Antenna | Int | 1-4+ | Which antenna detected the tag |
| `rc` | Read Count | Int | 1+ | How many times detected in scan |
| `bd` | Bank Data | String | Any | User-defined bank data (optional) |
| `pt` | Protocol | String | EPC, etc | RFID protocol |
| `ri` | RSSI | Int | -120 to 0 | Signal strength (dBm) |
| `ft` | First Seen | Unix Timestamp | Seconds | When tag was first detected |
| `lt` | Last Seen | Unix Timestamp | Seconds | When tag was last detected |

**Processing:**
1. Proxy extracts RFID from `ep` or `epc` (whichever is present)
2. Forwards to backend with full metadata
3. Backend creates race entry with start/end time tracking

---

### 2. Heart Beat

**Event Type:** `heart_beat`

Periodic heartbeat from the hub to verify connectivity.

```json
{
  "event_type": "heart_beat",
  "event_data": 42
}
```

**Processing:**
- `event_data` is the heartbeat count
- Proxy tracks hub connectivity status
- Updates `hub_state` tracking information

---

### 3. GPIO Changed

**Event Type:** `gpi_changed`

GPIO pin state changes (can be used for start signal, etc).

```json
{
  "event_type": "gpi_changed",
  "event_data": [
    {
      "state": "1"
    },
    {
      "state": "0"
    }
  ]
}
```

**Processing:**
- Track GPIO states for external signal integration
- Useful for race start signals or gate sensors

---

### 4. Reader Exception

**Event Type:** `reader_exception`

Hardware errors or exceptions from the hub.

```json
{
  "event_type": "reader_exception",
  "event_data": {
    "err_code": 1001,
    "err_string": "Antenna disconnected"
  }
}
```

**Processing:**
- Log error in proxy
- Update device state
- Alert operators (future enhancement)

---

## Tag Data Structure

### Complete Tag Object

When RFID tags are detected, they arrive in this format:

```json
{
  "ep": "ABC123456789DEF",
  "epc": "ABC123456789DEF",
  "at": 2,
  "rc": 3,
  "bd": "extra_data_here",
  "pt": "EPC Gen2",
  "ri": -68,
  "ft": 1703419200,
  "lt": 1703419201
}
```

### Field Reference:

| Field | Meaning | Usage | Example |
|-------|---------|-------|---------|
| `ep` | Electronic Product Code | Tag ID (primary) | `"ABC123456789DEF"` |
| `epc` | EPC Alternate | Tag ID (fallback) | `"ABC123456789DEF"` |
| `at` | Antenna | Which antenna | `1`, `2`, `3`, `4` |
| `rc` | Read Count | Signal strength indicator | `1`, `5`, `10` |
| `bd` | Bank Data | Custom user data | `"RACER_NAME"` |
| `pt` | Protocol | EPC protocol version | `"EPC"`, `"EPC Gen2"` |
| `ri` | RSSI | Signal (-120 weak, 0 strong) | `-65`, `-100` |
| `ft` | First Seen | Unix timestamp | `1703419200` |
| `lt` | Last Seen | Unix timestamp | `1703419201` |

### RSSI Signal Strength Reference:

| RSSI (dBm) | Interpretation | Action |
|------------|-----------------|--------|
| -30 to -50 | Excellent | Very strong signal |
| -50 to -70 | Good | Normal operation |
| -70 to -90 | Fair | Degraded signal, multiple reads |
| -90 to -110 | Poor | Unreliable detection |
| Below -110 | Lost | No signal |

---

## Full Payload Examples

### Example 1: Single Racer Detection

```json
{
  "event_type": "tag_read",
  "event_data": [
    {
      "ep": "E280114B2017AF3900019C5C",
      "epc": "E280114B2017AF3900019C5C",
      "at": 1,
      "rc": 1,
      "bd": "",
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }
  ]
}
```

**Processing Path:**
1. Proxy `/reader` receives POST
2. Extracts `ep`: `E280114B2017AF3900019C5C`
3. Forwards to backend: `/rfid/hit`
4. Backend creates/updates race entry

---

### Example 2: Multiple Racers (Cluster)

```json
{
  "event_type": "tag_read",
  "event_data": [
    {
      "ep": "E280114B2017AF3900019C5C",
      "epc": "E280114B2017AF3900019C5C",
      "at": 1,
      "rc": 2,
      "pt": "EPC",
      "ri": -62,
      "ft": 1703419200,
      "lt": 1703419201
    },
    {
      "ep": "E280114B2017AF3900019C5D",
      "epc": "E280114B2017AF3900019C5D",
      "at": 1,
      "rc": 1,
      "pt": "EPC",
      "ri": -68,
      "ft": 1703419201,
      "lt": 1703419201
    },
    {
      "ep": "E280114B2017AF3900019C5E",
      "epc": "E280114B2017AF3900019C5E",
      "at": 2,
      "rc": 1,
      "pt": "EPC",
      "ri": -71,
      "ft": 1703419201,
      "lt": 1703419201
    }
  ]
}
```

**Processing:**
- Proxy processes each tag in array sequentially
- Each forwarded independently to backend
- Response: `{"status": "ok", "tags_processed": 3, "tags_total": 3}`

---

### Example 3: Heartbeat

```json
{
  "event_type": "heart_beat",
  "event_data": 12345
}
```

**Proxy Response:**
```json
{
  "status": "ok",
  "heartbeat_received": true
}
```

---

### Example 4: Error Condition

```json
{
  "event_type": "reader_exception",
  "event_data": {
    "err_code": 1005,
    "err_string": "Antenna 2 disconnected"
  }
}
```

**Proxy Action:**
- Updates `hub_state.device_state`: `"ERROR: 1005 - Antenna 2 disconnected"`
- Logs error at ERROR level
- Returns 200 OK (acknowledges receipt)

---

## Proxy Server Processing

### Request Flow Diagram

```
┌─────────────────────┐
│  RFID Hub (Vendor)  │
└──────────┬──────────┘
           │
           │ HTTP POST /reader
           │ (JSON payload)
           │
           ▼
┌─────────────────────────────────┐
│ Proxy Server (Port 9090/9090)   │
│                                 │
│ - Parse JSON                    │
│ - Identify event_type           │
│ - Extract RFID from ep/epc      │
│ - Route to handler              │
└──────────┬──────────────────────┘
           │
    ┌──────┴──────┬────────┬─────────┐
    │             │        │         │
    ▼ tag_read    │        ▼ hb      ▼ error
forward_to_      gpi_     update_   log_error
backend()        changed  state
    │             │        │         │
    └──────┬──────┴────────┴─────────┘
           │
           │ Forward: /rfid/hit
           │
           ▼
┌─────────────────────────────────┐
│ Backend (8000/8002)             │
│                                 │
│ - Validate RFID                 │
│ - Create/Update entry           │
│ - Record timestamp              │
└─────────────────────────────────┘
```

### Proxy Handler Methods

**START LINE PROXY** (`proxy-9090/start-line/proxy.py`):

```python
@app.route('/reader', methods=['POST'])
def receive_from_hub():
    """Main entry point for hub events"""
    
    event_type = data.get('event_type')
    event_data = data.get('event_data', [])
    
    if event_type in ['tag_read', 'tag_coming']:
        return handle_tag_events(event_data)
    elif event_type == 'heart_beat':
        return handle_heartbeat(event_data)
    elif event_type == 'gpi_changed':
        return handle_gpi_change(event_data)
    elif event_type == 'reader_exception':
        return handle_exception(event_data)
```

**Processing Steps for Tag Detection:**

1. **Extract RFID**
   ```python
   rfid = tag.get('ep') or tag.get('epc')
   ```

2. **Extract Metadata**
   ```python
   antenna = tag.get('at', 0)
   read_count = tag.get('rc', 1)
   signal_strength = tag.get('ri', 0)
   first_seen = tag.get('ft')
   last_seen = tag.get('lt')
   ```

3. **Forward to Backend**
   ```python
   POST /rfid/hit
   {
     "rfid": "ABC123456",
     "antenna": 1,
     "read_count": 1,
     "signal_strength": -65,
     "first_seen": 1703419200,
     "last_seen": 1703419200,
     "bank_data": "",
     "protocol": "EPC"
   }
   ```

4. **Handle Response**
   - 200/201 OK: Continue processing
   - Error: Log warning, continue (graceful degradation)

---

## Integration Points

### 1. Hub Configuration

**Vendor Control Panel:**
1. Navigate to Hub Settings
2. Find "Event Posting" or "Webhook" section
3. Set Target URL:
   - Start Line: `http://<start-laptop-ip>:9090/reader`
   - End Line: `http://<end-laptop-ip>:9090/reader`
4. Set Method: POST
5. Set Content-Type: application/json
6. Enable: Yes
7. Save and restart hub

### 2. Proxy to Backend

**Request Format:**

```
POST /rfid/hit HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "rfid": "E280114B2017AF3900019C5C",
  "antenna": 1,
  "read_count": 1,
  "signal_strength": -65,
  "first_seen": 1703419200,
  "last_seen": 1703419200,
  "bank_data": "",
  "protocol": "EPC"
}
```

**Response Format:**

```json
{
  "status": "success",
  "rfid": "E280114B2017AF3900019C5C",
  "created": true,
  "message": "Entry recorded"
}
```

### 3. Hub State Health Check

**Endpoint:**
```
GET http://localhost:9090/health
```

**Response:**
```json
{
  "status": "ok",
  "service": "start-line-proxy",
  "hub_state": {
    "heartbeat_count": 42,
    "gpi_states": "1010",
    "device_state": "OK",
    "last_heartbeat": "2026-01-24T10:30:00.123456"
  }
}
```

---

## Network Configuration

### Port Allocation

| Service | Port | Description |
|---------|------|-------------|
| Start Line Proxy | 9090 | Receives from start line hub |
| End Line Proxy | 9090 | Receives from end line hub |
| Start Line Backend | 8000 | Processes start line scans |
| End Line Backend | 8002 | Processes end line scans |
| Registration | 8003 | Race management & results |

### Network Architecture

```
RFID Hub (Start Line)
    │
    │ HTTP POST
    │ Port 9090
    │
    ▼
Start-Line Laptop
├─ Proxy (9090) ──── Backend (8000)
└─ Local database

RFID Hub (End Line)
    │
    │ HTTP POST
    │ Port 9090
    │
    ▼
End-Line Laptop
├─ Proxy (9090) ──── Backend (8002)
└─ Local database

Registration Laptop
├─ Service (8003)
└─ Central database
```

### Firewall Rules

**Allow Inbound:**
- Hub → Proxy port 9090 (start line)
- Hub → Proxy port 9090 (end line)

**Allow Outbound:**
- Proxy → Backend port 8000/8002
- Proxy → Backend database (5432)

---

## Troubleshooting

### Issue: Hub Not Posting to Proxy

**Symptoms:**
- Proxy logs show no requests from hub
- Hub shows "posting" as enabled

**Diagnosis:**
1. Check hub configuration
   ```bash
   # On hub admin panel, verify target URL
   # Should be: http://<laptop-ip>:9090/reader
   ```

2. Test proxy health
   ```bash
   curl http://localhost:9090/health
   ```

3. Test firewall
   ```bash
   # From hub machine
   telnet <laptop-ip> 9090
   ```

4. Check proxy logs
   ```bash
   # In proxy output, should see:
   # "INFO: Starting START LINE Proxy on port 9090"
   ```

**Fix:**
- Verify IP address (not localhost if hub is external)
- Verify port is not blocked by firewall
- Restart hub service
- Verify proxy is running: `docker ps | grep proxy`

---

### Issue: Tags Not Being Recorded

**Symptoms:**
- Hub sending POST requests
- Proxy logs show reception
- But backend shows no entries

**Diagnosis:**
1. Check proxy logs for errors
   ```
   ERROR processing hub data: [error message]
   ```

2. Verify backend connectivity
   ```bash
   curl http://localhost:8000/health
   ```

3. Check backend logs
   ```bash
   docker logs rfid-marathon-start-line-backend
   ```

**Fix:**
- Verify backend is running: `docker ps`
- Check backend database connection
- Verify backend port is not blocked
- Check backend logs for SQL errors

---

### Issue: Duplicate RFID Entries

**Symptoms:**
- Same RFID recorded multiple times for single pass

**Root Cause:**
- Hub sends both `tag_read` and `tag_coming` events
- Multiple detections from same antenna

**Solution:**
1. In hub configuration, disable `tag_coming` if not needed
2. Or implement deduplication in backend (see start-time correction logic)

**Code Reference:**
Start line backend uses 10-second rule:
```python
# If same RFID detected again within 10 seconds, skip update
if diff > START_TIME_CORRECTION_THRESHOLD:
    update_start_time()
```

---

### Issue: Missing Signal Strength Data

**Symptoms:**
- `signal_strength` field is 0 or null

**Root Cause:**
- Hub not sending RSSI in event_data
- Or vendor uses different field name

**Diagnosis:**
1. Log raw hub payload
2. Check vendor documentation
3. Verify hub supports RSSI

**Workaround:**
- Use antenna number for distance estimation
- Multiple antennas = closer to reader

---

### Issue: Timestamps Are Wrong

**Symptoms:**
- Recorded start/end times don't match actual run time

**Root Cause:**
- Hub sending old/cached timestamps
- Time sync issue between hub and backend

**Fix:**
1. Sync hub system clock: `ntpdate pool.ntp.org` (on hub)
2. Verify hub timestamp fields
3. Backend uses `datetime.now()` for final timestamp

---

## Testing

### Manual Hub Simulation

Send test RFID via curl:

```bash
# Test tag_read event
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

Expected Response:
```json
{
  "status": "ok",
  "tags_processed": 1,
  "tags_total": 1
}
```

### Using Proxy Test Endpoint

```bash
# Test via proxy /test endpoint
curl -X POST http://localhost:9090/test \
  -H "Content-Type: application/json" \
  -d '{
    "rfid": "MANUAL_TEST",
    "antenna": 1
  }'
```

---

## Summary

The RFID hub integration is designed for:
- **Flexibility:** Handles both `ep` and `epc` fields
- **Robustness:** Silent failures, graceful degradation
- **Scalability:** Processes multiple tags in single POST
- **Traceability:** Full metadata captured (antenna, RSSI, timestamps)

The vendor hub POSTs to `/reader` endpoint with structured JSON, and our proxy servers extract the RFID tag ID along with metadata, then forward to appropriate backend for race timing.

