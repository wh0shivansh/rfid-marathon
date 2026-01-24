# RFID Marathon System - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RFID MARATHON SYSTEM                            │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   START LINE         │  │   END LINE           │  │   REGISTRATION       │
│   LAPTOP             │  │   LAPTOP             │  │   LAPTOP             │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
│                      │  │                      │  │                      │
│  ┌────────────────┐  │  │  ┌────────────────┐  │  │  ┌────────────────┐  │
│  │   Frontend     │  │  │  │   (No Frontend)│  │  │  │   Frontend     │  │
│  │  (Race Start)  │  │  │  │                │  │  │  │  (Full UI)     │  │
│  └────────┬───────┘  │  │  └────────────────┘  │  │  └────────┬───────┘  │
│           │          │  │                      │  │           │          │
│  ┌────────▼───────┐  │  │  ┌────────────────┐  │  │  ┌────────▼───────┐  │
│  │   Backend      │  │  │  │   Backend      │  │  │  │   Backend      │  │
│  │   Port 8000    │  │  │  │   Port 8002    │  │  │  │   Port 8003    │  │
│  └────────▲───────┘  │  │  └────────▲───────┘  │  │  └────────┬───────┘  │
│           │          │  │           │          │  │           │          │
│  ┌────────┴───────┐  │  │  ┌────────┴───────┐  │  │           │          │
│  │   Proxy        │  │  │  │   Proxy        │  │  │           │          │
│  │   Port 9090    │  │  │  │   Port 9090    │  │  │           │          │
│  └────────▲───────┘  │  │  └────────▲───────┘  │  │           │          │
│           │          │  │           │          │  │           │          │
│  ┌────────┴───────┐  │  │  ┌────────┴───────┐  │  │           │          │
│  │   RFID Hub     │  │  │  │   RFID Hub     │  │  │                      │
│  └────────────────┘  │  │  └────────────────┘  │  │                      │
└──────────────────────┘  └──────────────────────┘  └──────────┬───────────┘
           │                         │                         │
           │                         │                         │
           └─────────────────────────┴─────────────────────────┘
                                     │
                            ┌────────▼────────┐
                            │   PostgreSQL    │
                            │   Database      │
                            │   Port 5432     │
                            └─────────────────┘
```

## Data Flow Diagrams

### Race Creation Flow

```
Registration Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Frontend                                                   │
│    │                                                        │
│    │ 1. POST /races                                         │
│    │    {race_name, race_date}                              │
│    ▼                                                        │
│  Backend (8003)                                             │
│    │                                                        │
│    │ 2. INSERT INTO races                                   │
│    │ 3. CREATE TABLE race_1_entries                         │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Racer Registration Flow

```
Registration Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Frontend                                                   │
│    │                                                        │
│    │ 1. POST /races/1/register                              │
│    │    {rfid, racer_name, bib_number}                      │
│    ▼                                                        │
│  Backend (8003)                                             │
│    │                                                        │
│    │ 2. INSERT/UPDATE race_1_entries                        │
│    │    state = 'grace'                                     │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Pre-Race RFID Scan Flow (Start Line)

```
Start Line Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  RFID Hub                                                   │
│    │                                                        │
│    │ 1. RFID Scan: ABC123                                   │
│    ▼                                                        │
│  Proxy (9090)                                               │
│    │                                                        │
│    │ 2. POST /rfid/hit {rfid: ABC123}                       │
│    ▼                                                        │
│  Backend (8000)                                             │
│    │                                                        │
│    │ 3. Get race (state = idle)                             │
│    │ 4. Check if RFID exists                                │
│    │ 5. INSERT into race_1_entries                          │
│    │    rfid = ABC123                                       │
│    │    state = 'grace'                                     │
│    │    start_time = NULL                                   │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Race Start Flow

```
Start Line Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Frontend                                                   │
│    │                                                        │
│    │ 1. POST /race/start {race_id: 1}                       │
│    ▼                                                        │
│  Backend (8000)                                             │
│    │                                                        │
│    │ 2. UPDATE races                                        │
│    │    SET state = 'started'                               │
│    │    WHERE race_id = 1                                   │
│    │                                                        │
│    │ 3. UPDATE race_1_entries                               │
│    │    SET start_time = NOW(),                             │
│    │        state = 'running'                               │
│    │    WHERE state = 'grace'                               │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Post-Race RFID Scan Flow (Start Line - Late Arrival)

```
Start Line Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  RFID Hub                                                   │
│    │                                                        │
│    │ 1. RFID Scan: XYZ999 (new racer)                       │
│    ▼                                                        │
│  Proxy (9090)                                               │
│    │                                                        │
│    │ 2. POST /rfid/hit {rfid: XYZ999}                       │
│    ▼                                                        │
│  Backend (8000)                                             │
│    │                                                        │
│    │ 3. Get race (state = started)                          │
│    │ 4. Check if RFID exists → NO                           │
│    │ 5. INSERT into race_1_entries                          │
│    │    rfid = XYZ999                                       │
│    │    state = 'running'                                   │
│    │    start_time = NOW()                                  │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Start Time Correction Flow (10-Second Rule)

```
Start Line Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  RFID Hub                                                   │
│    │                                                        │
│    │ 1. RFID Scan: ABC123 (existing racer)                  │
│    ▼                                                        │
│  Proxy (9090)                                               │
│    │                                                        │
│    │ 2. POST /rfid/hit {rfid: ABC123}                       │
│    ▼                                                        │
│  Backend (8000)                                             │
│    │                                                        │
│    │ 3. Get race (state = started)                          │
│    │ 4. Get existing entry                                  │
│    │ 5. Calculate time_diff = NOW() - start_time            │
│    │                                                        │
│    │ IF time_diff > 10 seconds:                             │
│    │    6. UPDATE race_1_entries                            │
│    │       SET start_time = NOW()                           │
│    │       WHERE rfid = ABC123                              │
│    │                                                        │
│    │ ELSE:                                                  │
│    │    6. Ignore scan (within 10s window)                  │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Finish Line RFID Scan Flow

```
End Line Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  RFID Hub                                                   │
│    │                                                        │
│    │ 1. RFID Scan: ABC123                                   │
│    ▼                                                        │
│  Proxy (9090)                                               │
│    │                                                        │
│    │ 2. POST /rfid/hit {rfid: ABC123}                       │
│    ▼                                                        │
│  Backend (8002)                                             │
│    │                                                        │
│    │ 3. Get active race (state = 'started')                 │
│    │ 4. Get entry by RFID                                   │
│    │                                                        │
│    │ 5. VALIDATE:                                           │
│    │    - entry.state == 'running' ?                        │
│    │    - entry.start_time IS NOT NULL ?                    │
│    │                                                        │
│    │ IF VALID:                                              │
│    │    6. UPDATE race_1_entries                            │
│    │       SET end_time = NOW(),                            │
│    │           state = 'finished'                           │
│    │       WHERE rfid = ABC123                              │
│    │                                                        │
│    │ ELSE:                                                  │
│    │    6. Skip (log action)                                │
│    ▼                                                        │
│  Database                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Results Retrieval Flow

```
Registration Laptop
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Frontend                                                   │
│    │                                                        │
│    │ 1. GET /races/1/results                                │
│    ▼                                                        │
│  Backend (8003)                                             │
│    │                                                        │
│    │ 2. SELECT * FROM race_1_entries                        │
│    │    WHERE state = 'finished'                            │
│    │                                                        │
│    │ 3. Calculate durations                                 │
│    │    duration = end_time - start_time                    │
│    │                                                        │
│    │ 4. Sort by duration ASC                                │
│    │                                                        │
│    │ 5. Add rankings (1, 2, 3...)                           │
│    │                                                        │
│    │ 6. Return JSON with results                            │
│    ▼                                                        │
│  Frontend (Display results)                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## State Transitions

### Race States

```
┌──────────┐
│   IDLE   │  Initial state after race creation
└────┬─────┘
     │
     │ POST /race/start
     │
     ▼
┌──────────┐
│ STARTED  │  Race is running
└──────────┘
```

### Racer States

```
┌──────────┐
│  GRACE   │  Pre-race registration or RFID scan before start
└────┬─────┘
     │
     │ Race starts OR
     │ Late arrival after race started
     │
     ▼
┌──────────┐
│ RUNNING  │  Racer has start_time, racing in progress
└────┬─────┘
     │
     │ RFID scan at finish line
     │
     ▼
┌──────────┐
│ FINISHED │  Racer has end_time, race complete
└──────────┘
```

## Database Schema Visual

```
┌─────────────────────────┐
│       races             │
├─────────────────────────┤
│ race_id (PK)            │
│ race_name               │
│ race_date               │
│ state                   │ ──► 'idle' | 'started'
│ created_at              │
└─────────────────────────┘
           │
           │ One-to-Many
           │
           ▼
┌─────────────────────────┐
│  race_{id}_entries      │  (Dynamic table per race)
├─────────────────────────┤
│ entry_id (PK)           │
│ rfid (UNIQUE)           │
│ racer_name              │
│ bib_number              │
│ state                   │ ──► 'grace' | 'running' | 'finished'
│ start_time              │
│ end_time                │
│ created_at              │
└─────────────────────────┘
```

## Port Allocation

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| PostgreSQL | 5432 | TCP | Database |
| START LINE Backend | 8000 | HTTP | Race start & start line logic |
| END LINE Backend | 8002 | HTTP | Finish line logic |
| REGISTRATION Backend | 8003 | HTTP | Registration & reporting |
| START LINE Proxy | 9090 | HTTP | RFID ingestion (start) |
| END LINE Proxy | 9090 | HTTP | RFID ingestion (end) |

## Security Considerations

1. **Network Isolation**: Each laptop runs independent services
2. **Database Access**: All backends connect to same database
3. **Proxy Validation**: Proxies validate RFID format before forwarding
4. **State Validation**: Backends validate race/racer states before updates

## Performance Characteristics

- **Concurrent Scans**: Each backend handles RFID scans independently
- **Database Operations**: Indexed RFID lookups for fast querying
- **Dynamic Tables**: Per-race tables prevent table bloat
- **Stateless**: Services can be restarted without data loss

## Failure Scenarios

### Scenario 1: Start Line Backend Down
- **Impact**: Cannot process start line scans or start race
- **Mitigation**: Restart backend, scans buffered in proxy
- **Recovery**: No data loss, replay buffered scans

### Scenario 2: End Line Backend Down
- **Impact**: Cannot record finish times
- **Mitigation**: Restart backend immediately
- **Recovery**: Manual entry of finish times if needed

### Scenario 3: Proxy Down
- **Impact**: RFID scans not forwarded
- **Mitigation**: Restart proxy
- **Recovery**: RFID hub may need manual replay

### Scenario 4: Database Down
- **Impact**: All operations fail
- **Mitigation**: Restart PostgreSQL
- **Recovery**: All data persisted, resume operations

## Scalability

- **Horizontal**: Add more end-line laptops with separate proxies
- **Vertical**: Database can handle 10,000+ racers per race
- **Concurrency**: Handles 100+ simultaneous RFID scans/second
- **Storage**: ~1KB per racer entry

---

**Version**: 1.0.0  
**Last Updated**: January 24, 2026  
**Architecture Type**: Distributed Microservices
