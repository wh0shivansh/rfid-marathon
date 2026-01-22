# RFID Marathon Management System - Frontend (Electron)

Secure, offline-first Electron desktop app for RFID-based marathon management.

## Core Capabilities

- **Authentication**: Username/password from `.env` → JWT from backend.
- **Race Selection**: Chosen once per session; locked to prevent drift.
- **Registration Loop**: Continuous RFID scanning without screen switching (400+ entrants).
- **Encryption**: Backend responses (names) arrive RSA-encrypted; decrypted locally with private key. Local cache encrypted at rest (SQLite pragma + app-level encrypt fields if stored sensitive).
- **Timing Devices**: Device 1 records start, Device 2 records end; immutable once synced.
- **Offline Mode**: All actions cached in SQLite; sync queue with handshake confirmation.
- **States**: Registered / Started / Finished / Pending Sync / Synced.

## Environment Setup

1. Copy `.env.template` to `.env` and fill values:
   - `VITE_API_BASE_URL`: Backend base URL (e.g., `http://localhost:8000/api/v1`).
   - `FRONTEND_USERNAME` / `FRONTEND_PASSWORD`: Credentials used for login (hashed server-side).
   - `FRONTEND_RSA_PRIVATE_KEY_PATH`: Local private key for decrypting participant names.
   - `SQLITE_DB_PATH`: Local offline DB path.

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

## Offline-First Workflow

- **Cache**: Local SQLite `rfid_offline.db` with tables for participants, timings, sync queue.
- **Record**: When offline, writes insert into queue with ISO timestamps and device IDs.
- **Sync**: Background job checks connectivity; on success, POSTs to backend; receives confirmation IDs; deletes confirmed rows.
- **Idempotency**: Backend rejects duplicates via unique constraints; frontend retains original timestamps so no tampering.

## Security Boundaries

- Private RSA key stays on device; never sent to backend.
- Backend only stores Fernet-encrypted names; RFID tags are plaintext by requirement.
- All requests carry `Authorization: Bearer <token>`, `X-Timestamp`, `X-Nonce` (if added in client middleware).
- Rate limiting handled server-side; client should back off on 429.

## UI Flow

1. **Login** → stores JWT in memory (avoid disk) + short-lived.
2. **Select Race** (one time) → locks context.
3. **Register** → RFID scan → name entry → save (local + sync to backend if online).
4. **Start Timing** (Device 1) → record start; show status.
5. **End Timing** (Device 2) → record end; show duration if both present.
6. **Results Dashboard** → decrypt names locally, show standings.

## Sync Handshake

- After posting timing/registration when back online, client calls `/sync/handshake` with record IDs stored on backend.
- Backend responds with `confirmed_ids` and `failed_ids` → delete confirmed from SQLite; retry failed.

## Key Management

- Generate RSA keys (4096):

```bash
openssl genrsa -out keys/frontend_private.pem 4096
openssl rsa -in keys/frontend_private.pem -outform PEM -pubout -out keys/frontend_public.pem
```

- Place public key in backend if needed for response encryption test; backend already exposes `/crypto/public-key` for its key.

## Testing (Frontend)

- Unit tests for encryption helper, API client retry, SQLite sync queue.
- Manual scenarios: offline registration → online sync; duplicate scan handling; token expiry refresh.
