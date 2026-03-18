# RFID Listener (Proxy/v2) - Event Aggregation Service

## 📋 Overview

The RFID Listener is a FastAPI-based proxy service that aggregates RFID hit events from multiple readers, buffers them for batching, and forwards them to the Backend API. It acts as a unified event aggregation point, implementing deduplication, timing point detection, and intelligent batching for high-volume RFID processing.

**Key Characteristics:**
- **Framework:** FastAPI + Python 3.10+
- **Port:** 9090
- **Protocol:** HTTP/REST
- **Cache Strategy:** Per-reader in-memory deduplication
- **Batching:** Configurable buffer size and flush interval
- **Timestamp Capture:** Middleware-based hit time recording
- **Timing Detection:** Auto-detect START/MID/END from headers/paths
- **Performance:** 1000+ hits/second with minimal latency

---

## 🏗️ Architecture

### Event Pipeline

```
[RFID Reader Hardware/Hub]
         ↓
    (HTTP/REST)
         ↓
┌─────────────────────────────────────┐
│  RFID Listener (Port 9090)          │
│  ┌──────────────────────────────┐   │
│  │  Request Middleware          │   │
│  │  - Capture hit_timestamp     │   │
│  │  - Extract timing point      │   │
│  └──────────────────────────────┘   │
├─────────────────────────────────────┤
│  Event Handler                      │
│  - Parse RFID from 5+ field names   │
│  - Extract reader_name              │
│  - Detect timing point (S/M/E)      │
│  - Add to per-reader cache          │
├─────────────────────────────────────┤
│  Cache & Deduplication              │
│  - rfid_cache: [events, ...]        │
│  - cache_seen: {reader->set(rfid)}  │
│  - Deduplicate within 5s window     │
├─────────────────────────────────────┤
│  Batch Processor (Async)            │
│  - Flush every 5 seconds            │
│  - Or on buffer size reached        │
│  - Convert to bulk request format   │
└─────────────┬──────────────────────┘
              │
              │ HTTP POST (Batch)
              ▼
    [Backend API :8000]
    POST /api/v2/rfid/bulk
```

### Data Structures

```python
# In-memory cache per reader
class RFIDHit:
    race_id: str           # UUID of race
    rfid: str              # Tag ID (EPC/TID)
    timing_point: str      # START, MID, or END
    reader_name: str       # Reader identifier
    hit_timestamp: str     # ISO 8601 with milliseconds
    received_at: str       # Server-side timestamp

# Cache: Per-reader deduplication
rfid_cache: List[RFIDHit] = []  # All hits awaiting flush

cache_seen: Dict[str, Set[str]] = {
    "reader-1": {"EPC001", "EPC002", ...},
    "reader-2": {"EPC003", "EPC004", ...}
}

# Backend bulk request
bulk_request = {
    "race_id": "uuid",
    "hits": [
        {
            "rfid": "EPC001",
            "timing_point": "START",
            "reader_name": "reader-1",
            "hit_timestamp": "2024-01-01T09:00:15.123Z"
        },
        ...
    ]
}
```

---

## 🚀 Quick Start

### Installation

```bash
# Navigate to proxy/v2 directory
cd proxy/v2

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn httpx python-dotenv
```

### Environment Setup

Create `.env` file in `proxy/v2/`:

```env
# Server Configuration
HOST=0.0.0.0
PORT=9090
LOG_LEVEL=INFO

# Backend Configuration
BACKEND_URL=http://localhost:8000
RFID_BULK_ENDPOINT=/api/v2/rfid/bulk

# Cache & Batching
CACHE_FLUSH_INTERVAL=5000      # milliseconds (5 seconds)
BUFFER_SIZE=100                 # max hits per batch
DEDUP_WINDOW=5000              # milliseconds (5 seconds)

# Security
BACKEND_AUTH_TOKEN=             # Optional JWT token for backend

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=8001
```

### Run the Service

```bash
# Development mode
python rfid_listener.py

# With custom configuration
python rfid_listener.py --host 0.0.0.0 --port 9090

# Production mode (with gunicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker rfid_listener:app \
  --bind 0.0.0.0:9090
```

### Health Check

```bash
curl http://localhost:9090/health
# Response: {"status": "ok", "cache_size": 0}
```

---

## 📚 API Endpoints

### Event Ingestion

```
POST /reader
├─ Purpose: Receive RFID hit from reader/hub
├─ Headers (Optional):
│   ├─ X-TimingPoint: START|MID|END
│   ├─ X-ReaderName: reader-id
│   └─ X-HitTimestamp: ISO 8601 timestamp
├─ Query (Optional):
│   ├─ ?timing_point=START
│   └─ ?reader_name=reader-1
├─ Body (JSON):
│   {
│     "race_id": "race-uuid",      ← Required
│     "rfid": "EPC000001",         ← Required (or epc, tid, id)
│     "epc": "EPC000001",          ← Alternative field
│     "tid": "...",                ← Alternative field
│     "id": "...",                 ← Alternative field
│     "reader_name": "reader-1",   ← Optional (header override)
│     "timing_point": "START",     ← Optional (header override)
│     "reader_id": "1",            ← Maps to timing_point
│     "hit_timestamp": "2024-..."  ← Optional (auto-generated)
│   }
├─ Response (201):
│   {
│     "cached": true,
│     "cache_size": 42,
│     "timing_point": "START",
│     "reader_name": "reader-1"
│   }
└─ Status:
   200 OK: Event cached successfully
   400 Bad Request: Missing race_id or RFID
   429 Too Many Requests: Rate limit exceeded
```

### Batch Flushing

```
POST /flush-now
├─ Purpose: Manually trigger cache flush
├─ Body: Empty
├─ Response (200):
│   {
│     "flushed": 42,
│     "failed": 0,
│     "cache_size": 0
│   }
└─ Useful for testing / debugging

GET /cache-status
├─ Purpose: View current cache state
├─ Response (200):
│   {
│     "size": 42,
│     "by_timing_point": {
│       "START": 15,
│       "MID": 14,
│       "END": 13
│     },
│     "by_reader": {
│       "reader-1": 30,
│       "reader-2": 12
│     },
│     "last_flush": "2024-01-01T10:00:00Z",
│     "next_flush": "2024-01-01T10:00:05Z"
│   }
└─ Status: 200 OK
```

### Monitoring

```
GET /health
├─ Response: {"status": "ok", "cache_size": 0, "uptime": "2h30m"}
└─ Status: 200 OK

GET /metrics
├─ Response: Prometheus-format metrics
│   rfid_hits_total{status="cached"} 1234
│   rfid_hits_total{status="deduplicated"} 456
│   cache_flush_duration_ms 123
│   cache_size_current 42
└─ Status: 200 OK (if ENABLE_METRICS=true)
```

---

## 🔧 Core Features

### Automatic Timing Point Detection

The listener automatically detects START/MID/END timing from multiple sources:

```python
# Detection priority (first match wins):
1. Header: X-TimingPoint: START
2. Query param: ?timing_point=START
3. Header: X-ReaderName: reader-3 → Map to timing (see config)
4. Body: reader_id: 3 → Standard reader mapping
5. Body: timing_point: START
6. Default: START (safe default)

# Reader ID Mapping (configurable):
READER_MAPPING = {
    1: "START",    # Reader 1 always START
    2: "MID",      # Reader 2 always MID
    3: "END"       # Reader 3 always END
}
```

### RFID Field Extraction

Handles multiple field names from different RFID readers:

```python
# Supported RFID field names (in priority order):
["rfid", "epc", "tid", "id", "tag", "epcid"]

# Example payloads:
{
  "race_id": "...",
  "rfid": "EPC000001"        ← Standard field
}

{
  "race_id": "...",
  "epc": "EPC000002"         ← EPC = Electronic Product Code
}

{
  "race_id": "...",
  "tid": "TID000003"         ← TID = Tag ID
}

{
  "race_id": "...",
  "id": "000004"             ← Generic ID field
}
```

### Per-Reader Deduplication

Prevents duplicate RFID hits from single reader:

```python
# Mechanism:
1. Hit arrives: {race_id, rfid, reader_name, hit_time}
2. Extract "reader-1" from reader_name
3. Check in cache_seen["reader-1"]: if rfid exists → SKIP
4. If not cached: Add to rfid_cache
5. Mark in cache_seen["reader-1"]
6. On flush: Clear cache_seen, keep unique hits

# Window: 5 seconds
# Per-reader: Separate cache per reader to allow cross-reader duplicates
# Example:
  Hit 1: {rfid: EPC001, reader: reader-1, time: 09:00:15.100} → Accept
  Hit 2: {rfid: EPC001, reader: reader-1, time: 09:00:15.250} → Deduplicate (same reader)
  Hit 3: {rfid: EPC001, reader: reader-2, time: 09:00:15.150} → Accept (different reader)
```

### Batch Processing

Intelligent batching for efficient backend API usage:

```python
# Flush Trigger (whichever comes first):
1. Flush interval elapsed (5 seconds default)
2. Buffer size reached (100 hits)
3. Manual /flush-now request

# Batch Format:
POST /api/v2/rfid/bulk
{
  "race_id": "uuid",
  "hits": [
    {
      "rfid": "EPC000001",
      "timing_point": "START",
      "reader_name": "reader-1",
      "hit_timestamp": "2024-01-01T09:00:15.123Z"
    },
    ...  (up to 100 per batch)
  ]
}

# Retry Logic:
- Attempt 3 times with exponential backoff
- On failure: Log error + retain in cache
- Manual /flush-now to retry stuck items
```

### Middleware Timestamp Capture

```python
# Captures exact timestamp when hit arrives:
@app.middleware("http")
async def capture_hit_timestamp(request: Request, call_next):
    request.state.hit_timestamp = datetime.utcnow().isoformat() + "Z"
    # Process request...
    response = await call_next(request)
    return response

# Ensures:
- Timestamp is server-side (not client-skewed)
- Captured before any processing delays
- Precise to millisecond
```

---

## 🧪 Testing

### Test Commands

#### 1. Health Check

```bash
curl http://localhost:9090/health
# Response: {"status": "ok", "cache_size": 0}
```

#### 2. Send Single RFID Hit

```bash
# START timing point
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -H "X-TimingPoint: START" \
  -d '{
    "race_id": "race-uuid",
    "rfid": "EPC000001"
  }'

# MID timing point
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -H "X-TimingPoint: MID" \
  -d '{
    "race_id": "race-uuid",
    "rfid": "EPC000001"
  }'

# END timing point
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -H "X-TimingPoint: END" \
  -d '{
    "race_id": "race-uuid",
    "rfid": "EPC000001"
  }'
```

#### 3. Batch Hits with Different RFID Fields

```bash
# Using 'rfid' field
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"race_id": "race-uuid", "rfid": "EPC001"}'

# Using 'epc' field
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"race_id": "race-uuid", "epc": "EPC002"}'

# Using 'tid' field
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"race_id": "race-uuid", "tid": "TID003"}'

# Using 'id' field
curl -X POST http://localhost:9090/reader \
  -H "Content-Type: application/json" \
  -d '{"race_id": "race-uuid", "id": "004"}'
```

#### 4. View Cache Status

```bash
curl http://localhost:9090/cache-status
# Response: {size, by_timing_point, by_reader, last_flush, next_flush}
```

#### 5. Manually Flush Cache

```bash
curl -X POST http://localhost:9090/flush-now
# Response: {"flushed": 42, "failed": 0, "cache_size": 0}
```

#### 6. Test Deduplication

```bash
# Send same RFID twice rapidly
curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: START" \
  -d '{"race_id": "uuid", "rfid": "EPC001"}'

curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: START" \
  -d '{"race_id": "uuid", "rfid": "EPC001"}'

# View cache
curl http://localhost:9090/cache-status
# Should show cache_size: 1 (deduplicated)

# Different reader: allow duplicate
curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: MID" \
  -H "X-ReaderName: reader-2" \
  -d '{"race_id": "uuid", "rfid": "EPC001"}'

# View cache
curl http://localhost:9090/cache-status
# Should show cache_size: 2 (cross-reader allowed)
```

### Load Testing

```bash
# Using Apache Bench (100 requests, 10 concurrent)
ab -n 100 -c 10 -p payload.json -T application/json \
  http://localhost:9090/reader

# payload.json:
# {
#   "race_id": "race-uuid",
#   "rfid": "EPC000001"
# }

# Expected: ~1000 req/s on modern hardware
```

---

## 📊 Performance Tuning

### Cache Flush Interval

```python
# Current: 5000 ms (5 seconds)
# Impact on latency: Higher interval = more batching = less backend load
#
# For high-frequency readers:
# Reduce to 2000 ms (2 seconds) = more frequent flushes
#
# For low-frequency readers:
# Increase to 10000 ms (10 seconds) = better batching
#
# Configuration:
CACHE_FLUSH_INTERVAL=5000  # milliseconds
```

### Buffer Size

```python
# Current: 100 hits per batch
# Impact: Larger batches = more efficient backend processing
#
# For high-volume (1000+/sec):
# Increase to 500 hits = 5 batches/sec max
#
# For low-volume (<100/sec):
# Keep at 100 = flexible timing
#
# Configuration:
BUFFER_SIZE=100  # hits
```

### Deduplication Window

```python
# Current: 5000 ms (5 seconds)
# Prevents reader drift from processing same tag twice
#
# For readers with high trigger rate:
# Reduce to 2000 ms = stricter dedup
#
# For readers with spacing guarantees:
# Increase to 10000 ms = more lenient
#
# Configuration:
DEDUP_WINDOW=5000  # milliseconds
```

### Scaling Beyond 1000 hits/sec

```python
# Multiple instances (no shared cache):
# Instance 1: Port 9090 (START reader)
# Instance 2: Port 9091 (MID reader)
# Instance 3: Port 9092 (END reader)
# 
# Frontend load balancer distributes by timing_point
# Each instance handles independent reader stream

# Or: Shared Redis cache (advanced)
# - Replace in-memory dedup with Redis
# - Allows horizontal scaling
# - Adds ~10ms latency per check
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Hits Not Reaching Backend

**Error:** Cache fills up but never flushes

**Solutions:**
```bash
# 1. Check backend is running
curl http://localhost:8000/api/v2/health

# 2. Verify BACKEND_URL in .env
grep BACKEND_URL .env

# 3. Check firewall allows port 8000
netstat -ano | findstr 8000

# 4. Try manual flush
curl -X POST http://localhost:9090/flush-now

# 5. Check logs for backend errors
# Should see: "Flushed 42 hits to backend"
```

#### 2. Excessive Deduplication

**Error:** "Cache shows only 5 hits but sent 50"

**Solutions:**
```bash
# 1. Check DEDUP_WINDOW setting
grep DEDUP_WINDOW .env  # Should be 5000

# 2. Verify reader_name differs between readers
# Send hit 1 from reader-1
curl -H "X-ReaderName: reader-1" \
  -d '{"race_id":"uuid","rfid":"EPC001"}'

# Send hit 2 from reader-1 (DEDUPLICATED)
# Send hit 3 from reader-2 (NOT DEDUPLICATED - different reader)

# 3. Check cache status by reader
curl http://localhost:9090/cache-status |  jq '.by_reader'
```

#### 3. Timing Point Detection Failed

**Error:** "All hits marked as START, expected MIX"

**Solutions:**
```bash
# 1. Check READER_MAPPING configuration
# Default: reader-1 = START, reader-2 = MID, reader-3 = END

# 2. Verify header sent correctly
curl -H "X-TimingPoint: MID" \
  -d '{"race_id":"uuid","rfid":"EPC001"}'

# 3. Check reader_id mapping
curl -d '{"race_id":"uuid","rfid":"EPC001","reader_id":2}' \
  # reader_id 2 = MID

# 4. Inspect logs for detection logic
# Should show: "Detected timing_point=MID from reader_id=2"
```

#### 4. Cache Growing Unbounded

**Error:** Memory usage increasing, cache never clears

**Solutions:**
```bash
# 1. Check flush interval
grep CACHE_FLUSH_INTERVAL .env  # Should be 5000 ms (not too large)

# 2. Verify backend connectivity
curl http://localhost:8000/api/v2/health

# 3. Check backend logs for insertion errors
# If errors: hits are cached but not flushed

# 4. Reduce BUFFER_SIZE to flush more frequently
# Edit .env: BUFFER_SIZE=50  (was 100)

# 5. Manually monitor cache growth
watch -n 1 'curl -s http://localhost:9090/cache-status | jq .size'
# Should see drops every 5 seconds
```

#### 5. Different RFID Fields Not Recognized

**Error:** "Unexpected field" or RFID value None

**Solutions:**
```bash
# 1. Check supported field names in code
# Supported: rfid, epc, tid, id, tag, epcid

# 2. Test each field type
curl -d '{"race_id":"uuid","rfid":"EPC001"}'
curl -d '{"race_id":"uuid","epc":"EPC001"}'
curl -d '{"race_id":"uuid","tid":"TID001"}'
curl -d '{"race_id":"uuid","id":"001"}'

# 3. Check logs for field extraction
# Should show: "Extracted RFID from field 'rfid': EPC001"

# 4. Verify no typos in field names (case-sensitive)
# "RFID" ≠ "rfid", "Rfid" ≠ "rfid"
```

---

## 📚 Related Documentation

- **Main Project:** [../../README.md](../../README.md)
- **System Architecture:** [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Backend API:** [../../backend/v2/README.md](../../backend/v2/README.md)
- **Documentation Index:** [../../DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)
- **Full RFID Listener Notes:** [../../RFID_LISTENER_NOTES.txt](../../RFID_LISTENER_NOTES.txt)

---

## 📦 File Structure

```
proxy/v2/
├── rfid_listener.py      ← Main FastAPI application (500+ lines)
├── requirements.txt      ← Python dependencies
├── README.md             ← This file
├── Dockerfile            ← Container image
├── .env.example          ← Environment template
└── tests/
    ├── test_endpoints.py
    ├── test_dedup.py
    └── test_batch.py
```

### Key Dependencies

```
fastapi==0.104+
uvicorn==0.24+
httpx==0.25+           # Async HTTP for backend communication
python-dotenv==1.0+
pydantic==2.0+
```

---

## 📊 Integration Examples

### Frontend Integration

```javascript
// From Electron frontend:
const rfidHit = {
  race_id: "race-uuid",
  rfid: "EPC000001",
  timing_point: "START",
  reader_name: "reader-1"
};

fetch('http://localhost:9090/reader', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(rfidHit)
});
```

### UDP Listener Integration

```python
# From UDP Listener service:
import requests

rfid_hit = {
  "race_id": "race-uuid",
  "rfid": epc_value,
  "timing_point": "MID",
  "reader_name": "reader-2"
}

response = requests.post(
  'http://localhost:9090/reader',
  json=rfid_hit
)
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY rfid_listener.py .
ENV PORT=9090
CMD ["uvicorn", "rfid_listener:app", "--host", "0.0.0.0", "--port", "9090"]
```

---

**Last Updated:** March 2024  
**Version:** 2.0  
**Status:** Production Ready
