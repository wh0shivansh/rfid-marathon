# UDP Servers - HTTP ↔ UDP Protocol Gateway

## 📋 Overview

The UDP Servers module provides bidirectional protocol conversion between HTTP and UDP. It consists of two complementary services:

1. **UDP Sender** - Converts HTTP requests → UDP packets (for sending to mid-point RFID readers)
2. **UDP Listener** - Converts UDP packets → HTTP requests (for receiving from end-point RFID readers)

Together, they create a flexible gateway system that integrates legacy UDP-based RFID hardware with the modern HTTP-based backend API.

**Key Characteristics:**
- **Framework:** FastAPI (sender) + UDP sockets (listener)
- **Ports:** 6001 (HTTP sender), 8889 (UDP listener)
- **Protocol:** HTTP/JSON ↔ UDP/Binary
- **Cache Strategy:** Per-reader deduplication
- **Batching:** Intelligent UDP packet chunking
- **Reliability:** Resend mechanism with configurable retries
- **Performance:** 500+ conversions/second per service

---

## 🏗️ Architecture

### System Flow

```
RFID Reader Hardware
    (RFID Hub)

────────────────────── HTTP Path ──────────────────────

┌──────────────────────────────────────────────────────┐
│  UDP Sender (Port 6001) - HTTP to UDP Converter      │
│  ┌────────────────────────────────────────────────┐  │
│  │ FastAPI Server                                 │  │
│  │ POST /reader - Receive from RFID Hub           │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Cache & Deduplication                          │  │
│  │ - Per-reader dedup (5s window)                 │  │
│  │ - Batch accumulation                           │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Batch Processor (Async)                        │  │
│  │ - Flush every 3 seconds or on size limit       │  │
│  │ - Convert to UDP packet format                 │  │
│  │ - Chunk if > BULK_MAX_SIZE                     │  │
│  └──────────┬───────────────────────────────────┘   │
└─────────────┼──────────────────────────────────────┘
              │
              │ UDP (Port defined in config)
              ▼
    [Mid-Point RFID Reader]

────────────────────── UDP Path ──────────────────────

    [End-Point RFID Reader]
              │
              │ UDP (Port 8889)
              ▼
┌──────────────────────────────────────────────────────┐
│  UDP Listener (Port 8889) - UDP to HTTP Converter    │
│  ┌────────────────────────────────────────────────┐  │
│  │ UDP Socket Server                              │  │
│  │ Bind to 0.0.0.0:8889                           │  │
│  │ Receive UDP packets from end-point readers     │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Cache & Deduplication                          │  │
│  │ - Per-reader dedup (cache_seen set)            │  │
│  │ - Batch accumulation                           │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Batch Processor (Threading)                    │  │
│  │ - Flush every 3 seconds                        │  │
│  │ - Convert to HTTP request format               │  │
│  │ - POST to RFID Listener                        │  │
│  └──────────┬───────────────────────────────────┘   │
└─────────────┼──────────────────────────────────────┘
              │
              │ HTTP POST
              ▼
    [RFID Listener :9090]
    POST /reader endpoint
```

### Data Flow

**UDP Sender Path:**
```
HTTP Request (JSON)
    ↓
Parse: race_id, rfid, reader_name, timing_point
    ↓
Add to per-reader cache
    ↓
Every 3s or size_limit: Format batch
    ↓
Chunk into UDP packets (max 1400 bytes)
    ↓
Send via UDP socket with resend × 5
    ↓
UDP Packet arrives at reader
```

**UDP Listener Path:**
```
UDP Packet arrives (raw bytes)
    ↓
Decode: Parse RFID, reader, timestamp
    ↓
Add to per-reader cache (dedup)
    ↓
Every 3s: Format bulk request (JSON)
    ↓
POST to RFID Listener :9090/reader
    ↓
RFID Listener batches to backend
```

---

## 🚀 Quick Start

### Installation

```bash
# Navigate to udp_server directory
cd udp_server

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration Files

#### UDP Sender (.env)

```env
# HTTP Server (Listens)
HTTP_HOST=0.0.0.0
HTTP_PORT=6001

# UDP Target (Sends To)
UDP_TARGET_HOST=192.168.1.100    # Mid-point RFID reader IP
UDP_TARGET_PORT=5000              # Mid-point reader UDP port

# Processing
CACHE_FLUSH_INTERVAL=3000          # milliseconds
BUFFER_SIZE=100                    # hits before forced flush
BULK_MAX_SIZE=100                  # hits per UDP packet
RESEND_COUNT=5                     # Redundancy

# Logging
LOG_LEVEL=INFO
LOG_FILE=udp_sender.log
```

#### UDP Listener (.env)

```env
# UDP Socket (Listens)
UDP_BIND_HOST=0.0.0.0
UDP_BIND_PORT=8889

# HTTP Target (Forwards To)
RFID_LISTENER_URL=http://localhost:9090
RFID_LISTENER_ENDPOINT=/reader

# Processing
CACHE_FLUSH_INTERVAL=3000          # milliseconds
BUFFER_SIZE=100                    # hits before forced flush

# Threading
FLUSH_THREAD_ENABLED=true
FLUSH_THREAD_INTERVAL=3            # seconds

# Logging
LOG_LEVEL=INFO
LOG_FILE=udp_listener.log
```

### Run Services

```bash
# Terminal 1: UDP Sender (HTTP → UDP)
python udp_sender.py

# Terminal 2: UDP Listener (UDP → HTTP)
python udp_listener.py

# Optional: Run test sender
python send_test_tag.py
```

---

## 📚 API Reference

### UDP Sender Endpoints

```
POST /reader
├─ Purpose: Receive RFID hit from reader/frontend
├─ Body (JSON):
│   {
│     "race_id": "race-uuid",
│     "rfid": "EPC000001",
│     "reader_name": "reader-2",
│     "timing_point": "MID"
│   }
├─ Response (200):
│   {
│     "cached": true,
│     "cache_size": 42
│   }
└─ Status: 200 OK

GET /health
├─ Response: {"status": "ok"}
└─ Status: 200 OK

GET /cache-status
├─ Response: {
│   "size": 42,
│   "by_reader": {"reader-2": 42},
│   "last_flush": "2024-01-01T10:00:00Z"
│ }
└─ Status: 200 OK

POST /flush-now
├─ Response: {"flushed": 42, "failed": 0}
└─ Status: 200 OK
```

### UDP Listener Interfaces

```
UDP Socket Listening on 0.0.0.0:8889

Incoming UDP Packet Format:
├─ Binary payload (reader-specific encoding)
├─ Typical structure:
│   ├─ [Reader ID: 1 byte]
│   ├─ [Count: 2 bytes]
│   ├─ [EPC1 (12 bytes), EPC2 (12 bytes), ...]
│   └─ [Checksum: 2 bytes]

Response: None (UDP is connectionless)
```

---

## 🔧 Core Features

### UDP Sender

#### HTTP to UDP Conversion

```python
# Input (HTTP JSON):
{
  "race_id": "abc-123",
  "rfid": "EPC000001",
  "reader_name": "reader-2",
  "timing_point": "MID"
}

# Output (UDP Binary):
Packet 1 (max 1400 bytes):
┌────────────────────────────────┐
│ Header:                         │
│  race_id (UUID hex): 16 bytes  │
│  packet_num: 2 bytes            │
│  total_packets: 2 bytes         │
├────────────────────────────────┤
│ Payload:                        │
│  [EPC (12 bytes), ...] × N      │
├────────────────────────────────┤
│ Checksum: 2 bytes              │
└────────────────────────────────┘

Packet 2 (continuation):
[Similar structure]
```

#### Deduplication

```python
# Mechanism: Per-reader cache
cache = {
    "reader-2": {
        "EPC000001": timestamp1,
        "EPC000002": timestamp2,
        ...
    }
}

# On new hit:
if (rfid in cache[reader_name] and 
    now - timestamp < 5000ms):
    SKIP  # Already cached
else:
    ADD_TO_BUFFER
    UPDATE_CACHE_TIME

# Flush clears buffer but keeps time refs for next 5sec
```

#### Resend Mechanism

```python
# Sends same packet N times for reliability:
for i in range(RESEND_COUNT):  # 5 times default
    socket.sendto(packet, (TARGET_HOST, TARGET_PORT))
    time.sleep(10)  # 10ms between resends (50ms total)

# Ensures: Even if 1-2 packets lost, data arrives
# Trade-off: Increases network load (5x sends)
```

### UDP Listener

#### UDP to HTTP Conversion

```python
# Input (UDP Binary Packet):
[Reader info + EPC codes]

# Parsing:
1. Extract reader ID → map to reader_name
2. Extract EPC codes → array of RFID tags
3. Extract timestamp → use current server time
4. For each EPC:
   - Create event object
   - Add to cache if not duplicate
   - Associate with timing_point

# Output (HTTP JSON):
{
  "race_id": "abc-123",
  "rfid": "EPC000001",
  "reader_name": "reader-3",
  "timing_point": "END"
}
```

#### Threading Model

```python
# Main Thread:
while True:
    # Receive UDP packets endlessly
    data, addr = socket.recvfrom(1500)
    # Parse and cache

# Background Thread (flush_loop):
while True:
    sleep(3)  # Every 3 seconds
    # Format batch POST request
    # Send to RFID Listener :9090
    # Clear cache
```

#### Error Handling

```python
# Malformed UDP packets:
try:
    parse_udp_packet(data)
except Exception as e:
    log.error(f"Failed to parse: {e}")
    # Skip this packet, continue

# HTTP POST failures:
try:
    requests.post(RFID_LISTENER_URL, json=batch)
except requests.Timeout:
    log.warn("Timeout, retrying next flush")
    # Keep hits in cache for retry next cycle
```

---

## 🧪 Testing

### Test Commands

#### UDP Sender Testing

```bash
# 1. Send single hit
curl -X POST http://localhost:6001/reader \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "race-uuid",
    "rfid": "EPC000001",
    "reader_name": "reader-2",
    "timing_point": "MID"
  }'

# 2. Check cache
curl http://localhost:6001/cache-status
# Should show cache_size increasing

# 3. Wait for flush (default 3 seconds)
# Check UDP receiver:
tcpdump -i any -n udp port 5000

# 4. Manual flush
curl -X POST http://localhost:6001/flush-now
# Should show "flushed: 1"

# 5. Send rapid burst
for i in {1..50}; do
  curl -X POST http://localhost:6001/reader \
    -d "{\"race_id\":\"uuid\",\"rfid\":\"EPC$i\",\"reader_name\":\"reader-2\"}"
done

curl http://localhost:6001/cache-status
# Should show cache_size: 50
# Then drop to 0 after flush
```

#### UDP Listener Testing

```bash
# 1. Start listener
python udp_listener.py

# 2. Send UDP packet (from another terminal)
python -c "
import socket
data = b'\\x03\\x00\\x05EPC000001EPC000002EPC000003'
socket.socket().sendto(data, ('127.0.0.1', 8889))
"

# 3. Verify listener parsed it
# Check logs: "Flushed 3 hits to RFID Listener"

# 4. Use send_test_tag.py
python send_test_tag.py --count 100

# 5. Monitor in real-time
# Terminal 1: UDP Listener (shows "Flushed X hits")
# Terminal 2: RFID Listener (shows incoming batches)
# Terminal 3: Backend (shows processed RFID hits)
```

### Test Script (send_test_tag.py)

```bash
# Available parameters
python send_test_tag.py \
  --count 100 \
  --receiver reader-3 \
  --start-count 50 \
  --end-count 50 \
  --endpoint http://localhost:6001/reader

# Output:
# Sending 100 hits to http://localhost:6001/reader
# Response: 200 OK (cached)
# Cache status: 100 hits pending
```

### Integration Test (End-to-End)

```bash
# 1. Start all services
# Terminal 1: Backend (python backend/v2/main.py)
# Terminal 2: RFID Listener (python proxy/v2/rfid_listener.py)
# Terminal 3: UDP Sender (python udp_sender.py)
# Terminal 4: UDP Listener (python udp_listener.py)

# 2. Create race
RACE_ID=$(curl -X POST http://localhost:8000/api/v2/race/create \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"race_name\":\"Test\",\"category\":\"BPET\"}" | jq -r .id)

# 3. Register participant
curl -X POST http://localhost:8000/api/v2/participant/register \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"race_id\":\"$RACE_ID\",\"name\":\"Test\",\"age\":30,\"rfid\":\"EPC000001\"}"

# 4. Send RFID hit via UDP→HTTP path
python send_test_tag.py --receiver reader-3 --count 1

# 5. Verify backend received and processed
curl http://localhost:8000/api/v2/race/$RACE_ID/participants \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | select(.rfid == "EPC000001")'

# If timing point updates to "FINISHED", test passed!
```

---

## 📊 Performance Characteristics

### UDP Sender (HTTP → UDP)

```
Throughput: 500+ hits/second
Latency: <100ms (parse → cache → batch → send)
Memory: ~5MB per 1000 hits (before flush)
Network: ~100 bytes per hit over UDP

Bottleneck: UDP packet size (1400 bytes typical)
Mitigation: Chunking + resends for redundancy
```

### UDP Listener (UDP → HTTP)

```
Throughput: 500+ hits/second
Latency: <200ms (recv → cache → format → HTTP POST)
Memory: ~5MB per 1000 hits (before flush)
Network: HTTP POST ~10KB per batch of 100

Bottleneck: HTTP POST round-trip (network I/O)
Mitigation: Batching + 3s flush interval
```

### Optimization Tuning

```python
# High-volume scenario (1000+ hits/sec):

# UDP Sender:
CACHE_FLUSH_INTERVAL=1000      # 1 second (more frequent)
BUFFER_SIZE=500                 # Larger batches
BULK_MAX_SIZE=200               # Bigger UDP packets
RESEND_COUNT=3                  # Reduce overhead

# UDP Listener:
CACHE_FLUSH_INTERVAL=1000      # 1 second
BUFFER_SIZE=500
# Plus: Run multiple UDP Listener instances on different ports
#       with load balancer distributing by reader
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. UDP Packets Lost

**Error:** "Hits sent but not received"

**Solutions:**
```bash
# 1. Verify target host/port accessible
ping 192.168.1.100
# If unreachable, check network/firewall

# 2. Check packet loss with tcpdump
tcpdump -i any -c 100 udp port 5000
# Count received vs sent

# 3. Increase resend count
RESEND_COUNT=10  # Was 5

# 4. Monitor at both ends
# Terminal 1: tcpdump on receiver
tcpdump -i any udp port 5000

# Terminal 2: Send test hits
python send_test_tag.py --count 10
# tcpdump should show 50 packets (10 × 5 resends)
```

#### 2. UDP Listener Not Connecting to RFID Listener

**Error:** "Failed to forward to RFID Listener" or timeout

**Solutions:**
```bash
# 1. Verify RFID Listener is running
curl http://localhost:9090/health

# 2. Check network path
# From UDP Listener host:
curl http://localhost:9090/reader -d '{"race_id":"uuid","rfid":"EPC001"}'

# 3. Verify RFID_LISTENER_URL in .env
grep RFID_LISTENER_URL .env
# Should be: http://localhost:9090  (if local)
# Or: http://192.168.1.50:9090  (if remote)

# 4. Check firewall on port 9090
netstat -ano | findstr 9090

# 5. Test with explicit URL
export RFID_LISTENER_URL=http://192.168.1.50:9090
python udp_listener.py
```

#### 3. Memory Growing Unbounded

**Error:** "Python process using 1GB+ RAM"

**Solutions:**
```bash
# 1. Check cache is flushing
curl http://localhost:6001/cache-status
# size should decrease every 3 seconds

# 2. Verify flush is working
# Add debug log in udp_sender.py:
log.info(f"Before flush: {len(cache)} items")
# Run send_test_tag.py --count 100
# Should see: "Before flush: 100, After flush: 0"

# 3. Reduce BUFFER_SIZE to force flush
BUFFER_SIZE=10  # Was 100

# 4. Check for memory leaks
# Monitor with: watch -n 1 'ps aux | grep udp_sender'
# If RSS keeps growing despite flushing: potential leak
```

#### 4. UDP Packets Corrupted

**Error:** "Malformed packet" or decode errors

**Solutions:**
```bash
# 1. Verify sender/receiver format match
# Both must use same encoding (binary format agreed on)

# 2. Check UDP packet size
# Typical: 1400 bytes max (Ethernet MTU)
# If payload > 1400: NEEDS CHUNKING
# UDP Sender should chunk automatically

# 3. Test with known good packet
python send_test_tag.py
# If works with test script, issue is in your reader's encoding

# 4. Add packet logging
import binascii
log.info(f"Raw packet: {binascii.hexlify(data)}")
```

#### 5. Duplicate Hits in Backend

**Error:** "Same RFID appearing 3 times in results"

**Solutions:**
```bash
# 1. Check UDP Sender resend count
RESEND_COUNT=5  # Default
# This sends same packet 5 times (receiver deduplicates)

# 2. Verify RFID Listener deduplication is working
curl http://localhost:9090/cache-status
# Should show dedicated cache per timing_point/reader

# 3. Increase dedup window
# In RFID Listener .env:
DEDUP_WINDOW=10000  # 10 seconds (was 5s)

# 4. Check if multiple instances sending
# Ensure only one UDP Sender → same reader
# If multiple: they each cache+send = duplicates
```

---

## 📚 Related Documentation

- **Main Project:** [../../README.md](../../README.md)
- **System Architecture:** [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- **RFID Listener:** [../../proxy/v2/README.md](../../proxy/v2/README.md)
- **Backend API:** [../../backend/v2/README.md](../../backend/v2/README.md)
- **Documentation Index:** [../../DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)
- **Full UDP Notes:** [../../UDP_SERVERS_NOTES.txt](../../UDP_SERVERS_NOTES.txt)

---

## 📦 File Structure

```
udp_server/
├── udp_sender.py           ← HTTP→UDP converter (350+ lines)
├── udp_listener.py         ← UDP→HTTP converter (250+ lines)
├── send_test_tag.py        ← Test utility script
├── requirements.txt        ← Python dependencies
├── README.md              ← This file
├── udp-sender.spec        ← PyInstaller config
├── udp-listener.spec      ← PyInstaller config
├── build_udp_server.ps1   ← Build script
└── logs/
    ├── udp_sender.log
    └── udp_listener.log
```

### Key Dependencies

```
fastapi==0.104+
uvicorn==0.24+
requests==2.31+            # HTTP client for listener
pydantic==2.0+
python-dotenv==1.0+
```

---

## 🔌 Integration Points

### With RFID Listener

```python
# UDP Listener → RFID Listener
POST http://localhost:9090/reader
{
  "race_id": "uuid",
  "rfid": "EPC001",
  "reader_name": "reader-3",
  "timing_point": "END"
}
Response: {"cached": true, "cache_size": 42}
```

### With Physical Readers

```
UDP Sender → Mid-Point RFID Reader
Typical: Zebra RFID reader with XPort UDP module
Config: Target reader IP (e.g., 192.168.1.100), Port (e.g., 5000)

UDP Listener ← End-Point RFID Reader
Typical: Motorola RFID reader with UDP export
Config: Send to listener IP (e.g., 192.168.1.50), Port 8889
```

---

**Last Updated:** March 2024  
**Version:** 2.0  
**Status:** Production Ready
