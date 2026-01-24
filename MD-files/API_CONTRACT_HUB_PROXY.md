# RFID Hub ↔ Proxy API Contract

**Last Updated:** January 24, 2026  
**API Version:** 1.0  
**Vendor:** RFID Hub Tag Server

---

## Overview

This document specifies the exact API contract between the RFID hub (vendor) and our proxy servers. Both proxies implement the same interface.

```
RFID Hub                  Proxy (9090/9090)         Backend (8000/8002)
   │                            │                          │
   │ HTTP POST /reader          │                          │
   │ (vendor payload)           │                          │
   ├───────────────────────────>│                          │
   │                            │ HTTP POST /rfid/hit      │
   │                            │ (processed payload)      │
   │                            ├─────────────────────────>│
   │                            │                          │
   │                            │   HTTP 200/201 OK        │
   │                            │<─────────────────────────┤
   │                            │                          │
   │   HTTP 200 OK              │                          │
   │<───────────────────────────┤                          │
```

---

## Endpoint: POST /reader

**Port:** 9090 (start line) or 9090 (end line)  
**Method:** POST  
**Content-Type:** application/json  
**Authentication:** None (local network only)

### Request Format

#### Header
```
POST /reader HTTP/1.1
Host: localhost:9090
Content-Type: application/json
Content-Length: [varies]

[JSON body]
```

#### Body - Tag Detection

```json
{
  "event_type": "tag_read",
  "event_data": [
    {
      "ep": "E280114B2017AF3900019C5C",
      "epc": "E280114B2017AF3900019C5C",
      "at": 1,
      "rc": 1,
      "bd": "optional_bank_data",
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    }
  ]
}
```

#### Body - Tag Coming (Continuous Detection)

```json
{
  "event_type": "tag_coming",
  "event_data": [
    {
      "ep": "E280114B2017AF3900019C5C",
      "epc": "E280114B2017AF3900019C5C",
      "at": 1,
      "rc": 5,
      "pt": "EPC",
      "ri": -62,
      "ft": 1703419200,
      "lt": 1703419205
    }
  ]
}
```

#### Body - Heartbeat

```json
{
  "event_type": "heart_beat",
  "event_data": 42
}
```

#### Body - GPIO Changed

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

#### Body - Reader Exception

```json
{
  "event_type": "reader_exception",
  "event_data": {
    "err_code": 1001,
    "err_string": "Antenna 1 disconnected"
  }
}
```

### Request Field Definitions

| Field | Type | Required | Values | Example |
|-------|------|----------|--------|---------|
| `event_type` | String | YES | `tag_read`, `tag_coming`, `heart_beat`, `gpi_changed`, `reader_exception` | `"tag_read"` |
| `event_data` | Array/Object | YES | Depends on event_type | `[{...}]` or `42` |

### Tag Object Field Definitions

| Field | Name | Type | Required | Range | Example | Notes |
|-------|------|------|----------|-------|---------|-------|
| `ep` | EPC | String | NO* | Any | `"E280114B..."` | Primary tag ID (*one of ep/epc required) |
| `epc` | EPC Alternate | String | NO* | Any | `"E280114B..."` | Alternate tag ID (*one of ep/epc required) |
| `at` | Antenna | Integer | NO | 1-4+ | `1` | Which antenna detected tag |
| `rc` | Read Count | Integer | NO | 1+ | `1` | Number of detections |
| `bd` | Bank Data | String | NO | Any | `""` | User-defined data |
| `pt` | Protocol | String | NO | Any | `"EPC"` | RFID protocol |
| `ri` | RSSI | Integer | NO | -120 to 0 | `-65` | Signal strength (dBm) |
| `ft` | First Seen | Unix Timestamp | NO | Any | `1703419200` | When detected (seconds) |
| `lt` | Last Seen | Unix Timestamp | NO | Any | `1703419200` | Last detection (seconds) |

### Response Format

#### Success - 200 OK

```json
{
  "status": "ok",
  "tags_processed": 1,
  "tags_total": 1
}
```

#### Success with Errors - 200 OK

```json
{
  "status": "ok",
  "tags_processed": 1,
  "tags_total": 2,
  "errors": [
    {
      "error": "Missing RFID field",
      "tag": { "at": 1, "rc": 1 }
    }
  ]
}
```

#### Heartbeat Success - 200 OK

```json
{
  "status": "ok",
  "heartbeat_received": true
}
```

#### Exception Success - 200 OK

```json
{
  "status": "error",
  "error_code": 1001
}
```

#### Invalid JSON - 500 Internal Server Error

```json
{
  "error": "Invalid JSON"
}
```

### Response Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | All event types (success or graceful failure) |
| 400 | Bad Request | Invalid JSON, missing event_type |
| 500 | Server Error | Unhandled exception in proxy |

**Note:** Proxy always returns 200 for valid event_type, even if individual tags fail processing.

---

## Endpoint: GET /health

**Port:** 9090 (start line) or 9090 (end line)  
**Method:** GET  
**Content-Type:** application/json

### Request

```
GET /health HTTP/1.1
Host: localhost:9090
```

### Response - 200 OK

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

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | String | "ok" = proxy running |
| `service` | String | "start-line-proxy" or "end-line-proxy" |
| `hub_state.heartbeat_count` | Integer | Latest heartbeat count from hub |
| `hub_state.gpi_states` | String | GPIO state string (e.g., "1010") |
| `hub_state.device_state` | String | Device state (OK or ERROR message) |
| `hub_state.last_heartbeat` | String | ISO 8601 timestamp of last heartbeat |

---

## Processing Rules

### Tag Detection (tag_read, tag_coming)

1. **Parse Incoming**
   - Extract `event_data` array
   - For each tag object:
     - Extract RFID: `tag.get('ep') or tag.get('epc')`
     - If RFID missing, skip tag with error

2. **Forward to Backend**
   - POST to `http://localhost:8000/rfid/hit` (start line)
   - POST to `http://localhost:8002/rfid/hit` (end line)
   - Include all metadata fields

3. **Handle Response**
   - 200/201: Continue (log success)
   - Other: Log warning, continue (graceful failure)
   - Never return error to hub for tag failures

4. **Collect Results**
   - Count tags_processed successfully
   - Count tags_total received
   - If any errors, include errors array

### Heartbeat (heart_beat)

1. **Receive** `event_data` (integer count)
2. **Store** in `hub_state['heartbeat_count']`
3. **Update** `hub_state['last_heartbeat']` = now
4. **Update** `hub_state['device_state']` = "OK"
5. **Return** 200 OK

### GPIO Change (gpi_changed)

1. **Parse** `event_data` array of GPIO objects
2. **Extract** state from each: `gpi.get('state', '0')`
3. **Combine** all states: `''.join([s for gpi in event_data])`
4. **Store** in `hub_state['gpi_states']`
5. **Return** 200 OK

### Exception (reader_exception)

1. **Extract** error info from event_data
   - `err_code`: error code
   - `err_string`: error message
2. **Update** `hub_state['device_state']` = formatted error
3. **Log** error at ERROR level
4. **Return** 200 OK (acknowledge)

---

## Data Flow: Complete Example

### Hub Sends Multiple Tags

```json
POST /reader HTTP/1.1
Content-Type: application/json

{
  "event_type": "tag_read",
  "event_data": [
    {
      "ep": "RACER_001",
      "epc": "RACER_001",
      "at": 1,
      "rc": 1,
      "pt": "EPC",
      "ri": -65,
      "ft": 1703419200,
      "lt": 1703419200
    },
    {
      "ep": "RACER_002",
      "epc": "RACER_002",
      "at": 1,
      "rc": 1,
      "pt": "EPC",
      "ri": -68,
      "ft": 1703419201,
      "lt": 1703419201
    }
  ]
}
```

### Proxy Processing

```python
# Step 1: Parse
event_type = "tag_read"
tags = event_data  # List of 2 objects

# Step 2: Process each tag
processed = 0
for tag in tags:
    rfid = tag.get('ep') or tag.get('epc')  # "RACER_001", "RACER_002"
    antenna = tag.get('at', 0)              # 1, 1
    signal = tag.get('ri', 0)               # -65, -68
    
    # Step 3: Forward to backend
    response = requests.post(
        "http://localhost:8000/rfid/hit",
        json={
            "rfid": rfid,
            "antenna": antenna,
            "signal_strength": signal,
            # ... other fields
        }
    )
    
    if response.status_code in [200, 201]:
        processed += 1

# Step 4: Return summary
return {
    "status": "ok",
    "tags_processed": 2,
    "tags_total": 2
}
```

### Proxy Response

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "ok",
  "tags_processed": 2,
  "tags_total": 2
}
```

### Backend Processing (8000/8002)

```python
# Backend /rfid/hit endpoint receives:
{
    "rfid": "RACER_001",
    "antenna": 1,
    "signal_strength": -65,
    "first_seen": 1703419200,
    "last_seen": 1703419200,
    # ... other fields
}

# Backend:
# 1. Gets active race
# 2. Looks up entry by RFID
# 3. If NEW: create entry with start_time
# 4. If EXISTS: check 10-second rule
#    - If within 10s: skip
#    - If beyond 10s: update start_time
# 5. Return success
```

---

## Implementation Notes

### Proxy Library Code

**Receive from Hub:**
```python
@app.route('/reader', methods=['POST'])
def receive_from_hub():
    data = request.get_json()
    event_type = data.get('event_type')
    event_data = data.get('event_data', [])
    
    if event_type in ['tag_read', 'tag_coming']:
        return handle_tag_events(event_data)
    elif event_type == 'heart_beat':
        # Process heartbeat
    # ... etc
```

**Extract RFID:**
```python
# Both 'ep' and 'epc' are valid, use either
rfid = tag.get('ep') or tag.get('epc')

# If neither present, skip this tag
if not rfid:
    errors.append({"error": "Missing RFID field"})
    continue
```

**Forward to Backend:**
```python
payload = {
    "rfid": rfid,
    "antenna": tag.get('at', 0),
    "read_count": tag.get('rc', 1),
    "signal_strength": tag.get('ri', 0),
    "first_seen": tag.get('ft'),
    "last_seen": tag.get('lt'),
    "bank_data": tag.get('bd', ''),
    "protocol": tag.get('pt', 'EPC')
}

response = requests.post(
    f"{BACKEND_URL}/rfid/hit",
    json=payload,
    timeout=5
)
```

**Handle Backend Response:**
```python
if response.status_code not in [200, 201]:
    logger.warning(f"Backend returned {response.status_code}")
else:
    logger.info(f"Successfully forwarded {rfid}")
    processed_count += 1
```

---

## Compliance Checklist

### Proxy Implementation

- [ ] Accepts POST to `/reader` endpoint
- [ ] Parses `event_type` field
- [ ] Parses `event_data` field
- [ ] Handles `tag_read` event type
- [ ] Handles `tag_coming` event type
- [ ] Handles `heart_beat` event type
- [ ] Handles `gpi_changed` event type
- [ ] Handles `reader_exception` event type
- [ ] Extracts RFID from `ep` OR `epc`
- [ ] Forwards to backend `/rfid/hit`
- [ ] Returns 200 OK for all event types
- [ ] Returns proper error details
- [ ] Logs all events
- [ ] Tracks hub state

### Hub Configuration

- [ ] Event posting enabled
- [ ] Target URL set correctly
- [ ] Method set to POST
- [ ] Content-Type set to application/json
- [ ] Sending tag_read events
- [ ] Sending heartbeat events (optional but recommended)
- [ ] Not sending excessive tag_coming (causes duplicates)

### Network

- [ ] Hub can reach proxy port
- [ ] Proxy can reach backend port
- [ ] Network latency < 500ms (ideal)
- [ ] No packet loss
- [ ] Firewall allows ports 9090, 9090, 8000, 8002

---

## Testing Commands

### Send Tag Read Event

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

### Send Heartbeat

```bash
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "heart_beat",
    "event_data": 123
  }'
```

### Send Exception

```bash
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "reader_exception",
    "event_data": {
      "err_code": 1001,
      "err_string": "Test error"
    }
  }'
```

### Check Health

```bash
curl http://localhost:9090/health
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-24 | Initial API specification based on vendor tag_server.js |

---

## References

- **Vendor File:** `tag_server.js` (provided by hub vendor)
- **Proxy Implementation:** `proxy-9090/start-line/proxy.py`, `proxy-9090/end-line/proxy.py`
- **Backend Implementation:** `backend/start-line/app.py`, `backend/end-line/app.py`
- **Integration Guide:** `RFID_HUB_INTEGRATION.md`
- **Checklist:** `HUB_INTEGRATION_CHECKLIST.md`

