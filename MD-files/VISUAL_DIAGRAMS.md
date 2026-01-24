# RFID Marathon System - Visual Diagrams

## System Architecture Overview

```
╔════════════════════════════════════════════════════════════════════════╗
║                    RFID MARATHON TRACKING SYSTEM                       ║
║                         3 Laptop Architecture                          ║
╚════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────┐
│                         START LINE LAPTOP                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                      Frontend (Electron)                       │     │
│  │                  ┌──────────────────────────┐                  │     │
│  │                  │  [Start Race] Button     │                  │     │
│  │                  │  Race Status Display     │                  │     │
│  │                  │  Racer Count Monitor     │                  │     │
│  │                  └────────────┬─────────────┘                  │     │
│  └─────────────────────────────┼──────────────────────────────────┘     │
│                                 │                                        │
│                                 │ HTTP                                   │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │              START LINE Backend (Flask)                        │     │
│  │              Port: 8000                                        │     │
│  │                                                                │     │
│  │  Routes:                                                       │     │
│  │    POST /rfid/hit        ← Process RFID scan                  │     │
│  │    POST /race/start      ← Start the race                     │     │
│  │    GET  /race/today      ← Get today's race                   │     │
│  │                                                                │     │
│  │  Logic:                                                        │     │
│  │    • 10-second rule (start-time correction)                   │     │
│  │    • Grace period management                                  │     │
│  │    • Late arrival handling                                    │     │
│  └────────────────────┬───────────────────────────────────────────┘     │
│                       │                                                  │
│                       │ HTTP                                             │
│                       ▲                                                  │
│  ┌────────────────────┴───────────────────────────────────────────┐     │
│  │              START LINE Proxy (Flask)                          │     │
│  │              Port: 9090                                        │     │
│  │                                                                │     │
│  │  Routes:                                                       │     │
│  │    POST /rfid/scan      ← Receive from RFID hub               │     │
│  │    POST /test           ← Test endpoint                       │     │
│  │                                                                │     │
│  │  Function: Forward RFID scans to backend                      │     │
│  └────────────────────▲───────────────────────────────────────────┘     │
│                       │                                                  │
│                       │ HTTP POST                                        │
│  ┌────────────────────┴───────────────────────────────────────────┐     │
│  │                    RFID Hub (Hardware)                         │     │
│  │                  Scans: ABC123, DEF456...                      │     │
│  │                  Sends to: localhost:9090/rfid/scan            │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                          END LINE LAPTOP                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                    ┌──────────────────────┐                             │
│                    │   No Frontend        │                             │
│                    │   (Headless)         │                             │
│                    └──────────────────────┘                             │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │              END LINE Backend (Flask)                          │     │
│  │              Port: 8002                                        │     │
│  │                                                                │     │
│  │  Routes:                                                       │     │
│  │    POST /rfid/hit        ← Process finish line scan           │     │
│  │    GET  /race/active     ← Get active race                    │     │
│  │    GET  /race/{id}/      ← Get finished racers                │     │
│  │         finished                                               │     │
│  │                                                                │     │
│  │  Logic:                                                        │     │
│  │    • Validate: state = running                                │     │
│  │    • Validate: start_time exists                              │     │
│  │    • Record end_time                                          │     │
│  │    • Skip invalid entries                                     │     │
│  └────────────────────┬───────────────────────────────────────────┘     │
│                       │                                                  │
│                       │ HTTP                                             │
│                       ▲                                                  │
│  ┌────────────────────┴───────────────────────────────────────────┐     │
│  │              END LINE Proxy (Flask)                            │     │
│  │              Port: 9090                                        │     │
│  │                                                                │     │
│  │  Routes:                                                       │     │
│  │    POST /rfid/scan      ← Receive from RFID hub               │     │
│  │    POST /test           ← Test endpoint                       │     │
│  │                                                                │     │
│  │  Function: Forward RFID scans to backend                      │     │
│  └────────────────────▲───────────────────────────────────────────┘     │
│                       │                                                  │
│                       │ HTTP POST                                        │
│  ┌────────────────────┴───────────────────────────────────────────┐     │
│  │                    RFID Hub (Hardware)                         │     │
│  │                  Scans: ABC123, DEF456...                      │     │
│  │                  Sends to: localhost:9090/rfid/scan            │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                       REGISTRATION LAPTOP                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                      Frontend (Electron)                       │     │
│  │                                                                │     │
│  │  Views:                                                        │     │
│  │    • Dashboard                                                 │     │
│  │    • Create Race                                               │     │
│  │    • Candidate Registration                                    │     │
│  │    • Results & Rankings                                        │     │
│  │    • Statistics                                                │     │
│  │                                                                │     │
│  └─────────────────────────────┬──────────────────────────────────┘     │
│                                │                                         │
│                                │ HTTP                                    │
│                                ▼                                         │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │            REGISTRATION Backend (Flask)                        │     │
│  │            Port: 8003                                          │     │
│  │                                                                │     │
│  │  Routes:                                                       │     │
│  │    GET  /races              ← Get all races                   │     │
│  │    POST /races              ← Create new race                 │     │
│  │    GET  /races/{id}         ← Get race by ID                  │     │
│  │    POST /races/{id}/        ← Register racer                  │     │
│  │         register                                               │     │
│  │    GET  /races/{id}/        ← Get all racers                  │     │
│  │         racers                                                 │     │
│  │    GET  /races/{id}/        ← Get results & rankings          │     │
│  │         results                                                │     │
│  │    GET  /races/{id}/stats   ← Get statistics                  │     │
│  │    GET  /dashboard          ← Dashboard overview              │     │
│  │                                                                │     │
│  │  Logic:                                                        │     │
│  │    • Race CRUD operations                                     │     │
│  │    • Racer registration                                       │     │
│  │    • Results calculation                                      │     │
│  │    • Ranking generation                                       │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│                    ┌──────────────────────┐                             │
│                    │   No RFID Hub        │                             │
│                    │   No Proxy           │                             │
│                    └──────────────────────┘                             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘


                                   │
                                   │ TCP/IP
                                   │
                    ┌──────────────▼──────────────┐
                    │                             │
                    │    PostgreSQL Database      │
                    │    Port: 5432               │
                    │                             │
                    │  Tables:                    │
                    │    • races                  │
                    │    • race_1_entries         │
                    │    • race_2_entries         │
                    │    • ...                    │
                    │                             │
                    └─────────────────────────────┘
```

---

## Data Flow Diagram

```
╔════════════════════════════════════════════════════════════════════╗
║                        RFID SCAN PROCESSING                        ║
╚════════════════════════════════════════════════════════════════════╝


START LINE FLOW (BEFORE RACE):
─────────────────────────────────

  RFID Hub          Proxy           Backend         Database
     │               │                │                │
     │  Scan ABC123  │                │                │
     ├──────────────>│                │                │
     │               │  POST          │                │
     │               │  /rfid/hit     │                │
     │               ├───────────────>│                │
     │               │                │  Get race      │
     │               │                │  (state=idle)  │
     │               │                ├───────────────>│
     │               │                │                │
     │               │                │  INSERT entry  │
     │               │                │  (grace, NULL) │
     │               │                ├───────────────>│
     │               │                │                │
     │               │  200 OK        │                │
     │               │  Registered    │                │
     │               │<───────────────┤                │
     │               │                │                │


START LINE FLOW (AFTER RACE STARTS):
────────────────────────────────────

  RFID Hub          Proxy           Backend         Database
     │               │                │                │
     │  Scan XYZ999  │                │                │
     │  (new racer)  │                │                │
     ├──────────────>│                │                │
     │               │  POST          │                │
     │               │  /rfid/hit     │                │
     │               ├───────────────>│                │
     │               │                │  Get race      │
     │               │                │  (started)     │
     │               │                ├───────────────>│
     │               │                │                │
     │               │                │  INSERT entry  │
     │               │                │  (running,NOW)│
     │               │                ├───────────────>│
     │               │                │                │
     │               │  201 Created   │                │
     │               │  Late start    │                │
     │               │<───────────────┤                │
     │               │                │                │


END LINE FLOW:
──────────────

  RFID Hub          Proxy           Backend         Database
     │               │                │                │
     │  Scan ABC123  │                │                │
     ├──────────────>│                │                │
     │               │  POST          │                │
     │               │  /rfid/hit     │                │
     │               ├───────────────>│                │
     │               │                │  Get active    │
     │               │                │  race          │
     │               │                ├───────────────>│
     │               │                │                │
     │               │                │  Get entry     │
     │               │                │  by RFID       │
     │               │                ├───────────────>│
     │               │                │                │
     │               │                │  Validate:     │
     │               │                │  ✓ running     │
     │               │                │  ✓ has start   │
     │               │                │                │
     │               │                │  UPDATE        │
     │               │                │  end_time=NOW  │
     │               │                ├───────────────>│
     │               │                │                │
     │               │  200 OK        │                │
     │               │  Finished!     │                │
     │               │  30:05         │                │
     │               │<───────────────┤                │
     │               │                │                │
```

---

## State Machine Diagram

```
╔════════════════════════════════════════════════════════════════════╗
║                         RACE STATE MACHINE                         ║
╚════════════════════════════════════════════════════════════════════╝

              ┌─────────────────┐
              │                 │
              │      IDLE       │
              │                 │
              │  • Just created │
              │  • Not started  │
              │                 │
              └────────┬────────┘
                       │
                       │ POST /race/start
                       │ (Frontend button click)
                       │
                       ▼
              ┌─────────────────┐
              │                 │
              │    STARTED      │
              │                 │
              │  • Race running │
              │  • Accept scans │
              │                 │
              └─────────────────┘


╔════════════════════════════════════════════════════════════════════╗
║                        RACER STATE MACHINE                         ║
╚════════════════════════════════════════════════════════════════════╝

         ┌─────────────────┐
         │                 │
         │     GRACE       │
         │                 │
         │  • Pre-race     │
         │  • No start time│
         │                 │
         └────────┬────────┘
                  │
                  │ Race starts OR
                  │ Late arrival after race started
                  │
                  ▼
         ┌─────────────────┐
         │                 │
         │    RUNNING      │
         │                 │
         │  • Has start    │
         │  • Racing       │
         │                 │
         └────────┬────────┘
                  │
                  │ RFID scan at finish line
                  │
                  ▼
         ┌─────────────────┐
         │                 │
         │    FINISHED     │
         │                 │
         │  • Has end time │
         │  • Completed    │
         │                 │
         └─────────────────┘
```

---

## Network Topology

```
╔════════════════════════════════════════════════════════════════════╗
║                         NETWORK TOPOLOGY                           ║
╚════════════════════════════════════════════════════════════════════╝

                    ┌─────────────────────┐
                    │  Local Network      │
                    │  192.168.1.x        │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          │                    │                    │
    ┌─────▼─────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │ START LINE│        │  END LINE │       │REGISTRATION│
    │  LAPTOP   │        │  LAPTOP   │       │  LAPTOP   │
    │           │        │           │       │           │
    │ :8000     │        │ :8002     │       │ :8003     │
    │ :9090     │        │ :9090     │       │           │
    └─────┬─────┘        └─────┬─────┘       └─────┬─────┘
          │                    │                    │
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                               │
                      ┌────────▼────────┐
                      │   PostgreSQL    │
                      │   :5432         │
                      │                 │
                      │  rfid_marathon  │
                      └─────────────────┘
```

---

**Visual Reference Version**: 1.0.0  
**Last Updated**: January 24, 2026
