# Frontend - Electron Desktop Application

## 📋 Overview

The Frontend is a modern Electron-based desktop application for managing RFID Marathon races. It provides a comprehensive user interface for race setup, participant registration, real-time race monitoring, and results visualization/export.

**Key Characteristics:**
- **Framework:** Electron 40.0.0 with Vanilla JavaScript
- **UI Architecture:** Modular view system (7 distinct views)
- **HTTP Client:** axios with JWT interceptors  
- **State Management:** Global reactive state object
- **File Support:** XLSX, CSV, DOCX, TXT
- **Target Platform:** Windows (x64)
- **Performance:** Optimized for 3000+ concurrent participants
- **Latest Update:** March 17, 2026

---

## 🏗️ Architecture

### Application Structure

```
┌─────────────────────────────────────────┐
│   Electron Main Process                 │
│   (app.js - Window Management)          │
└─────────────┬─────────────────────────┘
              │
              │ IPC
              ▼
┌─────────────────────────────────────────┐
│   Renderer Process                      │
│   (app.js - Global State Management)    │
│   ┌───────────────────────────────────┐ │
│   │  Views Layer                      │ │
│   │  ├─ Dashboard                     │ │
│   │  ├─ Candidate Registration        │ │
│   │  ├─ Race Start                    │ │
│   │  ├─ Scoreboard                    │ │
│   │  ├─ Settings                      │ │
│   │  └─ Monitoring                    │ │
│   └───────────────────────────────────┘ │
│   ┌───────────────────────────────────┐ │
│   │  Services Layer (Business Logic)  │ │
│   │  ├─ CandidateRegistration        │ │
│   │  ├─ RaceStart                    │ │
│   │  ├─ RaceScoreboard               │ │
│   │  ├─ Dashboard                    │ │
│   │  └─ Settings                     │ │
│   └───────────────────────────────────┘ │
└─────────────┬─────────────────────────┘
              │
              │ HTTP/HTTPS
              ▼
    ┌─────────────────────────┐
    │  Backend API (Port 8000)│
    │  FastAPI Service        │
    └─────────────────────────┘
```

---

## 🚀 Quick Start

### Installation & Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Configure backend URL (edit package.json or .env)
VITE_API_BASE_URL=http://localhost:8000/api/v2

# Start development server
npm run dev
```

### Development Environment

```bash
# Required: Node.js 16+ and npm 8+
node --version  # >= 16.0.0
npm --version   # >= 8.0.0

# Install project dependencies
npm install

# Available npm scripts:
npm run dev      # Launch development app in watch mode
npm start        # Launch development app
npm run build    # Build for production
npm run pack     # Package application
npm run dist     # Create installer
```

### Build for Production

```bash
# Create Windows executable (x64)
npm run build

# Output location: dist/marathon-win32-x64/
# Creates standalone executable (no installer)
# Can also create NSIS installer via: npm run dist
```

---

## 📚 Current Features & Mode Support

### Core Functionality

- ✅ Login against backend API with JWT token management
- ✅ Create and edit races from desktop UI
- ✅ Configure race category qualifying thresholds
- ✅ Configure RFID placement mode per race
- ✅ Start races with frontend-selected start times
- ✅ View live race-start progress and statistics
- ✅ View and export scoreboard results
- ✅ Support for multiple file formats (CSV, XLSX, DOCX)

### RFID Placement Modes

The frontend supports two race timing modes that affect RFID reader configuration:

**Mode 1: `mid_end_reader_diff`** (Default)
- Runners hit both mid and end readers
- Requires 3 timing points: START, MID, END
- UI displays all three timing columns
- Race requires finish at END reader

**Mode 2: `end_intersection`**
- Runners evaluated without mid checkpoint
- Only START and END timing points
- Mid Time column hidden in UI
- Useful for point-to-point races

**Mode Impact:**
- **Create Race View** - Includes RFID mode selector
- **Race Edit** - Mode changeable only while race status is CREATED
- **Race Start View** - Mode label with edit button (disabled after start)
- **Race Statistics** - Hides mid-point section for `end_intersection`
- **Scoreboard View** - Hides Mid Time column for `end_intersection`
- **Excel/Word/PDF Exports** - Omit Mid Time column for `end_intersection`

---

## 📋 Views & Features Documentation

### 1. Dashboard View

Central hub showing all active races and statistics.

**Features:**
- Real-time race status display
- Quick statistics (registered, started, finished)
- Average completion time tracking
- One-click navigation to each race
- Create new race button

### 2. Create Race / Race Management

Race creation and configuration interface.

**Configuration Options:**
- Race name and category (BPET, CPT, PPT)
- **RFID Mode Selection** - Choose `mid_end_reader_diff` or `end_intersection`
- Age-based category thresholds
- Race date and scheduled start time
- Capacity configuration

**Race Lifecycle:**
```
CREATED → STARTED → COMPLETED
  ↑         ↑              ↓
  └─ Edit allowed    No edits    Mark Done
```

**Behavior Notes:**
- RFID mode editable only in CREATED status
- Selected start time combines with race date without UTC shifting
- Frontend sends `scheduled_date` in start request
- Backend updates stored date if incoming date differs

### 3. Candidate Registration

Multi-step participant registration workflow.

**Step 1: Select Race**
- Choose target race
- Display mode and capacity info

**Step 2: Upload File**
- Supports CSV, XLSX, DOCX formats
- Auto-file format detection
- Shows record count before upload

**Step 3: Confirm & Register**
- Preview participants
- Automatic RFID assignment
- Bulk POST to backend

**File Format Support:**
```
CSV:  name,age,bib_number,gender
XLSX: First sheet, columns A-D (name, age, bib, gender)
DOCX: Table rows extracted
TXT:  One name per line (auto-assign bib numbers)
```

**Error Handling:**
- Field-level validation messages
- Backend error codes displayed in UI
- Partial success indicated with count

### 4. Race Start View

Real-time race monitoring with live timing.

**Display Elements:**
- **Duration Clock** - Continuously incrementing race timer
- **Participant List** - Live updates every 2-5 seconds
- **Status Tracking** - REGISTERED → STARTED → MID → FINISHED
- **Timing Data** - Start time, mid time, end time per participant
- **Statistics** - Running counts by status

**Mode-Aware Behavior:**
- For `mid_end_reader_diff`: Shows START, MID, END columns
- For `end_intersection`: Hides MID time data
- Mode editable before race starts (button enabled in CREATED status)
- Mode edit disabled after race STARTED

**Polling Mechanism:**
```javascript
Interval: 2-5 seconds
GET /api/v2/race/{race_id}/participants
Updates: participant status, timing data, statistics
```

### 5. Scoreboard View

Final results display with export capabilities.

**Features:**
- Leaderboard sorted by finish time
- Status summary (total, finished, DNF)
- Average/min/max race times
- Three export formats:
  - **Excel** via `buildXlsx` - Spreadsheet with sorting
  - **Word** via `buildDocx` - Formatted table with wrap
  - **PDF** via `buildPdf` - Landscape table with wrap

**Export Behavior:**
- **Column Handling** - Follows active race mode
- **Long Names** - Wrapped in Word/PDF, not spilling
- **Word Tables** - Fixed column widths, landscape layout
- **PDF Tables** - Measured text wrapping, landscape layout
- **Mid Time** - Omitted if race in `end_intersection` mode

**Export Example:**
```bash
Frontend: [Export as Excel] button
→ buildXlsx() function
→ XLSX.utils.book_new()
→ Populate with sorted results
→ Download: results.xlsx
```

### 6. Settings View

Application configuration and preferences.

**Configuration Options:**
- Backend API base URL
- API request timeout
- Polling intervals (dashboard, race monitor, scoreboard)
- Race category definitions
- RFID deduplication window

---

## 🔐 Security & Authentication

### JWT Token Flow

```
1. User enters credentials
2. POST /api/v2/auth/login
3. Backend validates password (bcrypt)
4. JWT token returned (HS256, 15-min expiry)
5. Store in state.auth.token
6. Include in all requests: Authorization: Bearer {token}
7. Token expiry handled with automatic re-login redirect
```

### HTTP Client Configuration

```javascript
// Axios instance with interceptors
const secureApi = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

// Request Interceptor: Add JWT
secureApi.interceptors.request.use(config => {
  if (state.auth.token) {
    config.headers.Authorization = `Bearer ${state.auth.token}`;
  }
  return config;
});

// Response Interceptor: Handle 401
secureApi.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      state.auth.isAuthenticated = false;
      window.location.hash = '#login';
    }
    return Promise.reject(error);
  }
);
```

### Validation & Error Handling

The renderer surfaces backend validation clearly:

- **API Helpers** - Normalize backend error payloads
- **Field-Level Messages** - Request validation with specific errors
- **Error Codes** - Backend codes included in UI toasts
- **Coverage** - Race creation/update, candidate registration/update/delete, bulk upload

---

## 🧪 Testing & Verification

### Manual Test Checklist

#### Race Mode Testing

1. **Create race in `mid_end_reader_diff`**
   - [ ] Race Start shows Mid Time column
   - [ ] Scoreboard shows Mid Time column
   - [ ] Exports include Mid Time

2. **Create race in `end_intersection`**
   - [ ] Race Start hides Mid Time column
   - [ ] Scoreboard hides Mid Time column  
   - [ ] Exports omit Mid Time

3. **Edit race mode**
   - [ ] Mode changeable in CREATED status
   - [ ] Mode edit disabled after START
   - [ ] Changes persist after save

#### Race Start Date Sync

1. **Edit scheduled date**
2. **Start race with frontend time**
3. **Verify:**
   - [ ] Duration starts from correct date
   - [ ] Backend stores updated date
   - [ ] No 24-hour offset issues

#### Candidate Registration

1. **Bulk upload CSV**
   - [ ] Parse correctly
   - [ ] Assign RFID tags
   - [ ] Show success count

2. **Bulk upload XLSX**
   - [ ] Extract from first sheet
   - [ ] Validate columns
   - [ ] Insert to database

3. **Bulk upload DOCX**
   - [ ] Extract table rows
   - [ ] Handle merged cells
   - [ ] Associate with race

#### Exports

1. **Export as Excel**
   - [ ] Opens file dialog
   - [ ] Creates .xlsx
   - [ ] Correct columns per mode
   - [ ] Sortable by time

2. **Export as Word**
   - [ ] Creates .docx
   - [ ] Table with fixed widths
   - [ ] Landscape layout
   - [ ] Names wrapped, not spilling

3. **Export as PDF**
   - [ ] Creates .pdf
   - [ ] Landscape layout
   - [ ] Text measured + wrapped
   - [ ] Readable formatting

### Bulk RFID Test Sender

For backend timing tests, use [backend/v2/send_test_tag.py](../backend/v2/send_test_tag.py).

**What it does:**
- Builds RFID tag-read payloads (same shape as listener)
- Converts to bulk request: `/api/v2/rfid/bulk`
- Infers `reader_id` from `READER_NAME`
- Prints timing point before posting

**Configuration:**
```python
START_COUNT = 50          # Number of START hits to send
END_COUNT = 50            # Number of END hits to send
READER_NAME = "Reader 3"  # Maps to reader_id
BULK_ENDPOINT_URL = "http://localhost:8000/api/v2/rfid/bulk"
DRY_RUN = False           # Set True to preview without sending
```

**Common Reader Mapping:**
- `Reader 2` → MID timing → `reader_id = 2`
- `Reader 3` → END timing → `reader_id = 3`

**Test Steps:**
1. Configure [send_test_tag.py](../backend/v2/send_test_tag.py)
2. Run: `python send_test_tag.py`
3. Confirm printed `reader_id` matches timing point
4. Check backend logs for same `reader_id`
5. Verify frontend updates with hits

---

## 🔧 Configuration Reference

### Environment Configuration

```bash
# .env or package.json environment section:
VITE_API_BASE_URL=http://localhost:8000/api/v2
VITE_API_TIMEOUT=30000          # milliseconds
VITE_LOG_LEVEL=info
```

### Key Frontend Files

```
src/renderer/app.js
├─ Global state object
├─ API request helpers
├─ Error handling/parsing
├─ View routing (hash-based)
└─ Authentication interceptors

src/renderer/services/
├─ CandidateRegistration.js   - File upload, participant registration
├─ RaceStart.js               - Date sync, mode-aware polling, edit
├─ RaceScoreboard.js          - Export builders (XLSX, DOCX, PDF)
├─ Dashboard.js               - Race list, statistics
└─ Settings.js                - Configuration UI

src/renderer/views/
├─ CreateRace.js              - Mode selector, form validation
├─ Scoreboard.js              - Mode-aware column display
├─ RaceStart.js               - Live participant table
├─ CandidateRegistration.js   - Upload wizard
└─ Dashboard.js               - Race listing
```

### Polling Intervals

```javascript
POLLING_INTERVALS = {
  dashboard: 5000,       // 5 seconds (race list refresh)
  raceMonitor: 2000,     // 2 seconds (live timing)
  scoreboard: 1000       // 1 second (results)
}
```

### RFID Configuration

```javascript
RFID_DEDUP_WINDOW = 5000;      // 5 seconds (deduplication)
RFID_READER_NAMES = [
  "reader-1",   // START timing point
  "reader-2",   // MID timing point
  "reader-3"    // END timing point
];
```

---

## 🐛 Troubleshooting

### Common Issues

#### API Connection Failed

**Error:** "Failed to connect to backend API"

**Solutions:**
```bash
# 1. Verify backend is running
curl http://localhost:8000/api/v2/health

# 2. Check firewall allows port 8000
netstat -ano | findstr 8000

# 3. Test different API URL in Settings
VITE_API_BASE_URL=http://192.168.1.100:8000

# 4. Check browser console (F12 → Console)
# Look for CORS or connection errors
```

#### Token Expired

**Error:** "Authentication failed" during registration

**Solutions:**
```bash
# 1. Logout and re-login
# Click Login button → enter credentials → submit

# 2. Check token expiry (15 minutes default)
# Decode JWT from state
const decoded = jwt_decode(state.auth.token);
console.log(decoded.exp);  // Unix timestamp

# 3. Verify token in requests (F12 → Network)
# Should see: Authorization: Bearer {token}
```

#### File Upload Issues

**Error:** "Failed to parse file" or "No records found"

**Solutions:**
```bash
# 1. Verify CSV format
name,age,bib_number,gender
John Doe,28,001,M
Jane Smith,30,002,F

# 2. For XLSX - Ensure headers in first row
# Column A: name, B: age, C: bib, D: gender

# 3. For DOCX - Use simple table format (2-4 cols)
# Not nested tables or complex formatting

# 4. Check file size < 10MB
# Supported columns: name, age, bib_number, gender, category

# 5. Check browser console for parse errors
Press F12 → Console → Look for red errors
```

#### Real-time Updates Not Showing

**Error:** "Participant list stuck, no updates"

**Solutions:**
```bash
# 1. Verify API endpoint works
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v2/race/{race_id}/participants

# 2. Check polling configuration
// In app.js:
const pollingIntervals = { raceMonitor: 2000 };  // 2 seconds

# 3. Check browser Network tab (F12)
// Should see GET requests every 2-5 seconds
// Look for successful 200 responses

# 4. Check backend is returning data
# Response should have: {"participants": [...]}
```

#### RFID Integration Not Working

**Error:** "RFID hits not updating participant status"

**Solutions:**
```bash
# 1. Verify RFID Listener is running
curl http://localhost:9090/health

# 2. Test manual RFID hit
curl -X POST http://localhost:9090/reader \
  -H "X-TimingPoint: START" \
  -d '{"rfid":"EPC000001"}'

# 3. Check participant RFID mapping
console.log(state.perRaceRFIDMap)
// Should show: {race_id -> {rfid -> participant_id}}

# 4. Verify backend logs
// Should show RFID hit processing for each tag

# 5. Check timing point configuration
// Race should have START, MID (if mid_end_reader_diff), END
```

---

## 📚 Related Documentation

- **Main Project:** [../../README.md](../../README.md)
- **System Architecture:** [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Backend API:** [../backend/v2/README.md](../backend/v2/README.md)
- **Documentation Index:** [../../DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)
- **Full Frontend Notes:** [../../FRONTEND_NOTES.txt](../../FRONTEND_NOTES.txt)

---

## 📦 File Structure

```
frontend/
├── package.json           ← Dependencies and scripts
├── forge.config.js        ← Electron configuration
├── README.md              ← This file
├── public/
│   ├── app.js            ← Main process (window mgmt)
│   ├── index.html        ← Entry HTML
│   ├── preload.js        ← Process isolation/IPC
│   └── assets/           ← Images, CSS, fonts
├── src/
│   ├── index.html        ← Renderer template
│   ├── index.js          ← Renderer entry point
│   ├── index.css         ← Global styles
│   ├── main/
│   │   └── preload.js    ← Secure IPC bridge
│   ├── renderer/
│   │   ├── app.js        ← Global state + routing
│   │   ├── services/     ← Business logic
│   │   │   ├── CandidateRegistration.js
│   │   │   ├── RaceStart.js
│   │   │   ├── RaceScoreboard.js
│   │   │   ├── Dashboard.js
│   │   │   └── Settings.js
│   │   └── views/        ← UI components
│   │       ├── CreateRace.js
│   │       ├── CandidateRegistration.js
│   │       ├── RaceStart.js
│   │       ├── Scoreboard.js
│   │       ├── Dashboard.js
│   │       └── Monitoring.js
│   └── preload.js
└── dist/                 ← Build output
    └── marathon-win32-x64/
```

---

## 📊 Implementation Status

✅ **Completed:**
- Electron app with IPC
- Global state management
- JWT authentication
- Race CRUD operations
- Participant registration (single & bulk)
- File upload (CSV, XLSX, DOCX)
- Real-time race monitoring
- Mode-aware UI (mid_end_reader_diff, end_intersection)
- Export to Excel, Word, PDF
- Error handling with validation messages
- Race start date synchronization

**Last Updated:** March 17, 2026  
**Version:** 2.0.0  
**Status:** Production Ready
