# RFID Marathon - Complete Race Flow Sequences

## Complete Race Day Timeline

### Phase 1: Race Setup (Registration Laptop)

```
Time: T-60 minutes (1 hour before race)

┌──────────┐        ┌──────────┐        ┌──────────┐
│ Frontend │        │ Backend  │        │ Database │
│   UI     │        │  (8003)  │        │          │
└────┬─────┘        └────┬─────┘        └────┬─────┘
     │                   │                    │
     │ 1. Create Race    │                    │
     │ POST /races       │                    │
     ├──────────────────>│                    │
     │                   │ INSERT races       │
     │                   ├───────────────────>│
     │                   │ CREATE race_1_     │
     │                   │ entries table      │
     │                   ├───────────────────>│
     │                   │                    │
     │ ← Race ID: 1 ─────┤                    │
     │                   │                    │
```

---

### Phase 2: Racer Registration (Registration Laptop)

```
Time: T-30 to T-5 minutes

┌──────────┐        ┌──────────┐        ┌──────────┐
│ Frontend │        │ Backend  │        │ Database │
│   UI     │        │  (8003)  │        │          │
└────┬─────┘        └────┬─────┘        └────┬─────┘
     │                   │                    │
     │ 2. Register Racer │                    │
     │ POST /races/1/    │                    │
     │      register     │                    │
     │ {rfid: ABC123,    │                    │
     │  name: John,      │                    │
     │  bib: 101}        │                    │
     ├──────────────────>│                    │
     │                   │ INSERT INTO        │
     │                   │ race_1_entries     │
     │                   │ (rfid, name, bib,  │
     │                   │  state='grace')    │
     │                   ├───────────────────>│
     │                   │                    │
     │ ← Registered ─────┤                    │
     │                   │                    │
     │ [Repeat for each racer...]            │
     │                   │                    │
```

---

### Phase 3: Pre-Race Check-In (Start Line)

```
Time: T-5 to T-0 minutes
Race State: IDLE

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8000)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ 3. Scan     │             │             │
     │ RFID: ABC123│             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get race    │
     │             │             │ (state=idle)│
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Get entry   │
     │             │             │ by RFID     │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Entry exists│
     │             │             │ (registered)│
     │             │             │<────────────┤
     │             │             │             │
     │             │ 200 OK      │             │
     │             │ Already     │             │
     │             │ registered  │             │
     │             │<────────────┤             │
     │             │             │             │
```

**New Racer (Not Pre-Registered)**:
```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8000)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ Scan        │             │             │
     │ RFID: XYZ999│             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get race    │
     │             │             │ (state=idle)│
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Get entry   │
     │             │             │ NOT FOUND   │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ INSERT      │
     │             │             │ (XYZ999,    │
     │             │             │  grace,     │
     │             │             │  NULL time) │
     │             │             ├────────────>│
     │             │             │             │
     │             │ 201 Created │             │
     │             │ Registered  │             │
     │             │<────────────┤             │
```

---

### Phase 4: Race Start (Start Line)

```
Time: T=0 (Race Start Time)

┌──────────┐        ┌──────────┐        ┌──────────┐
│ Frontend │        │ Backend  │        │ Database │
│   UI     │        │  (8000)  │        │          │
└────┬─────┘        └────┬─────┘        └────┬─────┘
     │                   │                    │
     │ 4. START RACE!    │                    │
     │ POST /race/start  │                    │
     │ {race_id: 1}      │                    │
     ├──────────────────>│                    │
     │                   │ UPDATE races       │
     │                   │ SET state=         │
     │                   │ 'started'          │
     │                   ├───────────────────>│
     │                   │                    │
     │                   │ UPDATE race_1_     │
     │                   │ entries SET        │
     │                   │ start_time=NOW(),  │
     │                   │ state='running'    │
     │                   │ WHERE state=       │
     │                   │ 'grace'            │
     │                   ├───────────────────>│
     │                   │                    │
     │ ← Race Started    │                    │
     │   50 racers       │                    │
     │   started         │                    │
     │<──────────────────┤                    │
     │                   │                    │
```

---

### Phase 5: Late Arrival (Start Line)

```
Time: T+2 minutes (2 minutes after race started)
Race State: STARTED

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8000)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ 5. Scan     │             │             │
     │ RFID: LATE1 │             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get race    │
     │             │             │ (started)   │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Get entry   │
     │             │             │ NOT FOUND   │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ INSERT      │
     │             │             │ (LATE1,     │
     │             │             │  running,   │
     │             │             │  NOW())     │
     │             │             ├────────────>│
     │             │             │             │
     │             │ 201 Created │             │
     │             │ Late start  │             │
     │             │ T+2min      │             │
     │             │<────────────┤             │
```

---

### Phase 6: Start Time Correction (Start Line)

```
Time: T+3 seconds (Within 10-second window)

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8000)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ 6a. Scan    │             │             │
     │ RFID: ABC123│             │             │
     │ (duplicate) │             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get entry   │
     │             │             │ (has start) │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Calculate   │
     │             │             │ diff: 3s    │
     │             │             │             │
     │             │             │ 3s < 10s    │
     │             │             │ → IGNORE    │
     │             │             │             │
     │             │ 200 OK      │             │
     │             │ Ignored     │             │
     │             │ (within 10s)│             │
     │             │<────────────┤             │
```

**After 10 seconds**:
```
Time: T+15 seconds (Beyond 10-second window)

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8000)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ 6b. Scan    │             │             │
     │ RFID: ABC123│             │             │
     │ (late start)│             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get entry   │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Calculate   │
     │             │             │ diff: 15s   │
     │             │             │             │
     │             │             │ 15s > 10s   │
     │             │             │ → UPDATE    │
     │             │             │             │
     │             │             │ UPDATE      │
     │             │             │ start_time= │
     │             │             │ NOW()       │
     │             │             ├────────────>│
     │             │             │             │
     │             │ 200 OK      │             │
     │             │ Start time  │             │
     │             │ corrected   │             │
     │             │<────────────┤             │
```

---

### Phase 7: Finish Line Crossing (End Line)

```
Time: T+30 minutes (Racer finishes)

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8002)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ 7. Scan     │             │             │
     │ RFID: ABC123│             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get active  │
     │             │             │ race        │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Get entry   │
     │             │             │ by RFID     │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Validate:   │
     │             │             │ ✓ running   │
     │             │             │ ✓ has start │
     │             │             │             │
     │             │             │ UPDATE      │
     │             │             │ end_time=   │
     │             │             │ NOW(),      │
     │             │             │ state=      │
     │             │             │ 'finished'  │
     │             │             ├────────────>│
     │             │             │             │
     │             │ 200 OK      │             │
     │             │ Finished!   │             │
     │             │ Duration:   │             │
     │             │ 00:30:05    │             │
     │             │<────────────┤             │
```

**Invalid Finish (No Start Time)**:
```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │  Proxy   │  │ Backend  │  │ Database │
│   Hub    │  │  (9090)  │  │  (8002)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     │ Scan        │             │             │
     │ RFID: BAD999│             │             │
     ├────────────>│             │             │
     │             │ POST        │             │
     │             │ /rfid/hit   │             │
     │             ├────────────>│             │
     │             │             │ Get entry   │
     │             │             ├────────────>│
     │             │             │             │
     │             │             │ Validate:   │
     │             │             │ ✗ no start  │
     │             │             │ → SKIP      │
     │             │             │             │
     │             │ 200 OK      │             │
     │             │ Skipped     │             │
     │             │ (no start)  │             │
     │             │<────────────┤             │
```

---

### Phase 8: Results & Reporting (Registration Laptop)

```
Time: Post-Race

┌──────────┐        ┌──────────┐        ┌──────────┐
│ Frontend │        │ Backend  │        │ Database │
│   UI     │        │  (8003)  │        │          │
└────┬─────┘        └────┬─────┘        └────┬─────┘
     │                   │                    │
     │ 8. Get Results    │                    │
     │ GET /races/1/     │                    │
     │     results       │                    │
     ├──────────────────>│                    │
     │                   │ SELECT * FROM      │
     │                   │ race_1_entries     │
     │                   │ WHERE state=       │
     │                   │ 'finished'         │
     │                   ├───────────────────>│
     │                   │                    │
     │                   │ Calculate          │
     │                   │ durations          │
     │                   │                    │
     │                   │ Sort by            │
     │                   │ duration ASC       │
     │                   │                    │
     │                   │ Add rankings       │
     │                   │                    │
     │ ← Results JSON    │                    │
     │   [               │                    │
     │     {rank: 1,     │                    │
     │      name: Alice, │                    │
     │      time: 30:05} │                    │
     │     ...           │                    │
     │   ]               │                    │
     │<──────────────────┤                    │
     │                   │                    │
     │ Display Results   │                    │
     │ on Dashboard      │                    │
     │                   │                    │
```

---

## Error Scenarios

### Scenario 1: Duplicate Finish Scan

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │ Backend  │  │ Database │
│   Hub    │  │  (8002)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     │ Scan ABC123 │             │
     │ (2nd time)  │             │
     ├────────────>│             │
     │             │ Get entry   │
     │             ├────────────>│
     │             │             │
     │             │ Already     │
     │             │ has end_time│
     │             │<────────────┤
     │             │             │
     │ 200 OK      │             │
     │ Already     │             │
     │ finished    │             │
     │<────────────┤             │
```

### Scenario 2: Racer Never Started

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│   RFID   │  │ Backend  │  │ Database │
│   Hub    │  │  (8002)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     │ Scan XYZ789 │             │
     ├────────────>│             │
     │             │ Get entry   │
     │             ├────────────>│
     │             │             │
     │             │ state =     │
     │             │ 'grace'     │
     │             │ (never      │
     │             │  started)   │
     │             │<────────────┤
     │             │             │
     │ 200 OK      │             │
     │ Skipped     │             │
     │ (not running)             │
     │<────────────┤             │
```

---

## Multi-Racer Timeline Example

```
Time  | Event                          | System Action
------|--------------------------------|---------------------------
T-60m | Create race                    | Registration: INSERT race
T-30m | Register Alice (ABC123)        | Registration: INSERT entry (grace)
T-30m | Register Bob (DEF456)          | Registration: INSERT entry (grace)
T-5m  | Alice scans at start line      | Start Line: Already registered
T-3m  | Bob scans at start line        | Start Line: Already registered
T-2m  | Charlie (GHI789) walks up      | Start Line: New entry (grace)
T=0   | ★ RACE STARTS ★                | Start Line: All grace → running
      |                                |   - Alice: start_time = T
      |                                |   - Bob: start_time = T
      |                                |   - Charlie: start_time = T
T+2m  | David (JKL012) late arrival    | Start Line: New entry (running, T+2m)
T+5s  | Alice accidentally re-scans    | Start Line: Ignored (within 10s)
T+15m | Alice re-scans (real late)     | Start Line: Corrected (diff > 10s)
T+28m | Bob finishes (crosses end)     | End Line: end_time = T+28m ✓
T+30m | Alice finishes                 | End Line: end_time = T+30m ✓
T+32m | Charlie finishes               | End Line: end_time = T+32m ✓
T+35m | David finishes                 | End Line: end_time = T+35m (33m race) ✓
T+40m | View results                   | Registration: Display rankings
      |                                |   1. Bob (28:05)
      |                                |   2. Alice (30:12)
      |                                |   3. Charlie (32:45)
      |                                |   4. David (33:01)
```

---

## State Transition Timeline

```
Racer: Alice (RFID: ABC123)

T-30m  │ REGISTRATION
       │ state: grace, start_time: NULL, end_time: NULL
       │
T-5m   │ PRE-RACE SCAN (Start Line)
       │ state: grace, start_time: NULL, end_time: NULL
       │
T=0    │ RACE STARTS
       │ state: running, start_time: T, end_time: NULL
       │
T+5s   │ ACCIDENTAL RE-SCAN (Ignored)
       │ state: running, start_time: T, end_time: NULL
       │
T+15m  │ REAL LATE START (Corrected)
       │ state: running, start_time: T+15m, end_time: NULL
       │
T+45m  │ FINISH LINE
       │ state: finished, start_time: T+15m, end_time: T+45m
       │ Duration: 30 minutes
```

---

**Document Version**: 1.0.0  
**Last Updated**: January 24, 2026  
**Covers**: Complete race day flow with all scenarios
