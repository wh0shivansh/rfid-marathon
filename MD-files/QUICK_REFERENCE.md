# RFID Marathon - Quick Reference Card

## 🚀 Quick Commands

### Start Services (Windows)
```bash
start-all-services.bat          # Start everything
init-database.bat               # Initialize database
run-start-line.bat              # Start line only
run-end-line.bat                # End line only
run-registration.bat            # Registration only
```

### Test System
```bash
python test_system.py           # Full integration test
```

---

## 🔌 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| START LINE Backend | http://localhost:8000 | Race start & start line logic |
| START LINE Proxy | http://localhost:9090 | RFID ingestion (start) |
| END LINE Backend | http://localhost:8002 | Finish line logic |
| END LINE Proxy | http://localhost:9090 | RFID ingestion (end) |
| REGISTRATION Backend | http://localhost:8003 | Registration & reporting |

---

## 📡 API Cheat Sheet

### Create Race
```bash
POST http://localhost:8003/races
{
  "race_name": "Marathon 2026",
  "race_date": "2026-01-24"
}
```

### Register Racer
```bash
POST http://localhost:8003/races/1/register
{
  "rfid": "ABC123",
  "racer_name": "John Doe",
  "bib_number": "101"
}
```

### Start Race
```bash
POST http://localhost:8000/race/start
{
  "race_id": 1
}
```

### Simulate RFID Scan (Start)
```bash
POST http://localhost:9090/rfid/scan
{
  "rfid": "ABC123"
}
```

### Simulate RFID Scan (End)
```bash
POST http://localhost:9090/rfid/scan
{
  "rfid": "ABC123"
}
```

### Get Results
```bash
GET http://localhost:8003/races/1/results
```

---

## 🎯 Race State Flow

```
IDLE → START RACE → STARTED
```

## 🏃 Racer State Flow

```
GRACE → RACE STARTS → RUNNING → FINISH SCAN → FINISHED
```

---

## ⏱️ 10-Second Rule

When racer scans RFID at start line after race has started:

```
Time Difference       Action
─────────────────────────────────────
< 10 seconds     →   Ignore (duplicate)
> 10 seconds     →   Update start time
```

---

## 🔄 Typical Race Day Timeline

```
T-60m    Create race & register racers
T-5m     Racers check-in at start line
T=0      START RACE (all grace → running)
T+0-60m  Racers finish (end line scans)
T+60m    View results & rankings
```

---

## 📊 Database Tables

### races
```
race_id | race_name | race_date | state | created_at
```

### race_1_entries (dynamic)
```
entry_id | rfid | racer_name | bib_number | state | start_time | end_time
```

---

## 🚨 Common Issues

### Port Already in Use
```bash
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

### Database Connection Failed
```bash
sc query postgresql
createdb rfid_marathon
```

### Services Not Starting
```bash
cd backend/shared
pip install -r requirements.txt
```

---

## 🧪 Health Checks

```bash
curl http://localhost:8000/health   # Start line
curl http://localhost:8002/health   # End line
curl http://localhost:8003/health   # Registration
curl http://localhost:9090/health   # Start proxy
curl http://localhost:9090/health   # End proxy
```

All should return: `{"status": "ok"}`

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| README.md | Main documentation |
| QUICKSTART.md | Setup guide |
| BACKEND_README.md | API documentation |
| ARCHITECTURE.md | System design |
| DEPLOYMENT_CHECKLIST.md | Pre-deployment |

---

## 🎓 Key Rules

1. **No Shared Runtime**: Each laptop runs independent services
2. **Proxy Layer**: RFID hub → Proxy → Backend
3. **State Validation**: End line only processes `running` racers
4. **Dynamic Tables**: Each race gets own entries table
5. **10-Second Rule**: Prevents duplicate start scans

---

## 💡 Pro Tips

✅ Always start database before backends  
✅ Use `start-all-services.bat` for quick setup  
✅ Run `test_system.py` to verify everything works  
✅ Check logs if scans not processing  
✅ Backup database before race day  

---

## 📞 Emergency Contacts

| Role | Name | Phone |
|------|------|-------|
| System Admin | _____ | _____ |
| Database Admin | _____ | _____ |
| Technical Support | _____ | _____ |

---

**Print this card and keep it at each laptop station!** 📋
