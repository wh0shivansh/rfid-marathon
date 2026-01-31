# RFID Marathon Management System - Frontend (Electron)

Secure, offline-first Electron desktop app for RFID-based marathon management.

## 🎯 Core Capabilities

- **Authentication**: Username/password → JWT from backend.
- **Race Selection**: Chosen once per session; locked to prevent context switching.
- **Registration Loop**: Continuous RFID scanning without screen switching (400+ entrants).
- **Encryption**: Backend responses (names) arrive RSA-encrypted; decrypted locally with private key.
- **Timing Devices**: Device 1 records start, Device 2 records end.
- **Offline Mode**: All actions cached in SQLite; sync queue with handshake confirmation.
- **States**: Registered / Started / Finished / Pending Sync / Synced.

---

## 🏗️ Architecture

### Layers

```
┌─────────────────────────────────────┐
│    Frontend (Electron + React)      │
│    • User interface                 │
│    • Offline SQLite cache           │
│    • RSA decryption                 │
│    • Sync queue management          │
└──────────────┬──────────────────────┘
               │ HTTPS + JWT
               ▼
┌─────────────────────────────────────┐
│    Backend (FastAPI - 8001)         │
│    • State management               │
│    • Database operations            │
│    • Encryption                     │
└──────────────┬──────────────────────┘
               │ SSL
               ▼
┌─────────────────────────────────────┐
│    Supabase PostgreSQL              │
│    • races                          │
│    • participants_{race_id}         │
│    • users                          │
└─────────────────────────────────────┘

     NOTE: RFID Listener (9090)
      is SEPARATE from Frontend
    (runs on race management server)
    Frontend DOES NOT interact with it
```

### Frontend vs. Backend vs. Listener

| Component | Role | Storage | State |
|-----------|------|---------|-------|
| **Frontend** (Electron) | User interface | SQLite local | Race selection, queue |
| **Backend** (Port 8001) | API, state management | PostgreSQL | race_state.json |
| **RFID Listener** (Port 9090) | Hub interface | **NONE** | Stateless proxy |

**Important**: The RFID Listener (9090) has **ZERO local storage**. It's a stateless proxy that only forwards hits to the backend. The frontend does NOT interact with the listener.

---

## 🔧 Environment Setup

1. Copy `.env.template` to `.env` and fill values:
   - `VITE_API_BASE_URL`: Backend URL (e.g., `http://localhost:8001/api/v1`). **NOT listener 9090.**
   - `RFID_USERNAME` / `RFID_PASSWORD`: Login credentials (hashed server-side on backend).
   - `FRONTEND_RSA_PRIVATE_KEY_PATH`: Local private key for decrypting participant names.

2. Install dependencies:

```bash
cd frontend
npm install
```

3. Run in dev:

```bash
npm run dev
```

4. Build:

```bash
npm run build
```

---

## 💾 Offline-First Workflow

### Cache System

- **Local DB**: SQLite `rfid_offline.db` with tables for participants, timings, sync queue.
- **Stored Data**:
  - Registrations (rfid_tag, name)
  - Timing events (start_time, end_time)
  - Sync queue (what needs to be sent to backend)

### Recording (Online & Offline)

```
Online Mode:
  1. RFID scan → POST /participant/register → Backend encrypts & stores → Returns encrypted name
  2. Decrypt locally → Display confirmation → Update local SQLite

Offline Mode:
  1. RFID scan → Insert into sync_queue table (action="register")
  2. Local SQLite stores encrypted data + metadata
  3. Display confirmation (cached or new)

Sync Process (When Online):
  1. Background job detects connectivity
  2. POST sync_queue items to backend
  3. Backend validates & stores
  4. Receive confirmation IDs
  5. POST /sync/handshake with IDs
  6. Delete confirmed records from sync_queue
  7. Update local participants table
```

### Queue Table Schema

```sql
CREATE TABLE sync_queue (
  id TEXT PRIMARY KEY,
  action TEXT,              -- "register", "timing_start", "timing_end"
  race_id TEXT NOT NULL,
  rfid_tag TEXT,
  name TEXT,                -- for registrations
  timestamp TIMESTAMPTZ,    -- for timing events
  device_id INTEGER,        -- 1=start, 2=end
  created_at TIMESTAMPTZ DEFAULT NOW(),
  synced_at TIMESTAMPTZ,
  synced BOOLEAN DEFAULT FALSE
);
```

### Idempotency

- Backend rejects duplicates via unique constraints
- Frontend retains original timestamps (no tampering on retry)
- Sync handshake ensures "exactly once" semantics

---

## 🔐 Security Boundaries

### What Stays Local

- **Private RSA Key**: Never sent to backend. Used locally to decrypt participant names.
- **JWT Token**: Stored in memory (not disk) during session.
- **SQLite Database**: Local device only. Contains queue of syncs + cached data.

### What Goes to Backend (Over HTTPS)

- **Registrations**: {race_id, rfid_tag, name, ...}
- **Timing Events**: {race_id, rfid_tag, timestamp, device_id}
- **Sync Handshake**: {confirmed_ids, failed_ids}

### What Never Touches Network

- **Participant Names** (decryption): Local only. Backend sends RSA-encrypted; frontend decrypts.
- **SQLite Data**: Never uploaded raw. Only sync_queue items sent.

### Backend Security

- All requests carry `Authorization: Bearer <token>`, `X-Timestamp`, `X-Nonce`
- Rate limiting: 60 requests/minute per IP
- Database stores Fernet-encrypted names; RFID tags plaintext
- Backend enforces unique constraints to prevent duplicates

---

## 📱 UI Flow

```
1. Login
   ├─ Enter username/password
   ├─ POST /auth/login
   ├─ Store JWT in memory
   └─ Proceed if successful

2. Select Race (One Time)
   ├─ Display race list (GET /race)
   ├─ User selects race
   ├─ Lock race_id for session
   └─ Proceed to registration

3. Registration Loop (Continuous)
   ├─ RFID scan
   ├─ Prompt for name (if new)
   ├─ POST /participant/register (online) or insert sync_queue (offline)
   ├─ Display encrypted name or cached entry
   ├─ Mark as "Registered"
   └─ Return to scan (no screen change)

4. Start Timing (Official Call)
   ├─ Backend calls POST /api/v1/timing/start
   ├─ Grace period initialized (120 seconds)
   ├─ Frontend displays "Timing Started"

5. Record Timing
   ├─ Device 1 (RFID at start): Listener forwards to /api/v1/rfid/record-start
   ├─ Device 2 (RFID at finish): Listener forwards to /api/v1/rfid/record-end
   ├─ Backend updates start_time/end_time in participant table
   ├─ Frontend polls /api/v1/dashboard-data for updates
   └─ Display "Finished" + duration

6. Results Dashboard
   ├─ Decrypt cached names locally
   ├─ Display standings (race_id-specific participant table)
   └─ Show sync status
```

---

## 🔄 Sync Handshake

### Process

```
1. Frontend detects connectivity
2. Builds batch of sync_queue records
3. POST batch to backend
   Example: [
     {action: "register", race_id: 1, rfid_tag: "A123", name: "John"},
     {action: "timing_start", race_id: 1, rfid_tag: "B456", timestamp: "2026-01-22T15:00:01Z"}
   ]
4. Backend processes & stores (returns IDs)
5. Frontend calls POST /sync/handshake {record_ids: ["id1", "id2", ...]}
6. Backend confirms sync status
7. Frontend deletes confirmed records from sync_queue
```

### Retry Logic

- If network fails mid-sync: Records remain in queue
- Automatic retry on next connectivity check
- Exponential backoff (1s, 2s, 4s, 8s...)
- User sees "Pending Sync" status until confirmed

---

## 🔑 Key Management

### Generate RSA Keys

```bash
# Generate 4096-bit private key
openssl genrsa -out keys/frontend_private.pem 4096

# Extract public key (for sharing)
openssl rsa -in keys/frontend_private.pem -pubout -out keys/frontend_public.pem

# Show key info
openssl rsa -in keys/frontend_private.pem -text -noout | head -5
```

### Key Placement

- **Private Key** (`frontend_private.pem`): Keep locally in frontend app directory
- **Public Key**: Can be shared with backend (not needed for current design)
- **Env Path**: Set `FRONTEND_RSA_PRIVATE_KEY_PATH=./keys/frontend_private.pem` in `.env`

### Key Rotation

- **When**: Annually or after security incident
- **How**: Generate new keys, update `.env`, restart frontend
- **Note**: Old encrypted names still work if old public key is on backend

---

## 📱 Component Structure

```
frontend/
├── src/
│   ├── main.js                     # Electron main process
│   ├── preload.js                  # Preload script (context isolation)
│   ├── renderer/
│   │   ├── app.js                  # Root React component
│   │   ├── views/
│   │   │   ├── Login.js            # Authentication
│   │   │   ├── RaceSelect.js       # Race picker (one-time)
│   │   │   ├── Registration.js     # Continuous RFID scanning
│   │   │   ├── Timing.js           # Start/end timing display
│   │   │   └── Results.js          # Standings + sync status
│   │   │
│   │   └── utils/
│   │       ├── API.js              # Backend communication
│   │       ├── Database.js         # SQLite operations
│   │       ├── Encryption.js       # RSA decryption
│   │       └── SyncQueue.js        # Queue management
│   │
│   └── services/
│       ├── ApiService.js           # API client (retry logic)
│       ├── DatabaseService.js      # SQLite abstraction
│       ├── EncryptionService.js    # RSA operations
│       └── SyncService.js          # Sync queue processor
│
└── database/
    └── schema.sql                  # SQLite schema (local)
```

---

## 🧪 Testing (Frontend)

```bash
# Unit tests for encryption helper
npm test -- Encryption

# Sync queue tests
npm test -- SyncQueue

# Manual test scenario:
# 1. Start frontend (offline)
# 2. Register participant → check sync_queue table
# 3. Go online
# 4. Verify auto-sync → check handshake success
```

---

## ⚠️ Known Limitations & TODOs

- [ ] UI components not yet implemented (Vite + React setup only)
- [ ] RFID hardware integration pending
- [ ] Token refresh on expiry (currently 15 min)
- [ ] Biometric authentication
- [ ] Multi-language support
- [ ] Real-time WebSocket updates (polling only)

---

## 🚀 Deployment

### Development

```bash
npm run dev
```

### Production Build

```bash
npm run build
npm start
```

### Electron Packaging

```bash
npm run pack           # Build app
npm run make          # Create installer
```

---

## 📝 Important Notes

**The RFID Listener (Port 9090) is NOT part of the frontend.** It's a separate server-side component that:
- Receives RFID hits from hardware hubs
- Forwards them to the backend (port 8001)
- Has ZERO local storage
- Does NOT interact with this Electron app

Frontend ONLY communicates with Backend (port 8001) for:
- Authentication
- Participant registration
- Timing queries
- Results

---

**Last Updated**: January 22, 2026  
**Version**: 1.0.0-alpha  
**Status**: UI Components Pending
