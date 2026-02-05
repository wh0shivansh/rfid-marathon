Control Hub (Docker Orchestrator)

This utility controls the backend/proxy/UDP services using Docker Compose.

Commands:
- up: Start services (docker compose up -d)
- down: Stop and remove services (docker compose down)
- start: Start stopped services
- stop: Stop running services
- restart: Restart services
- status: Show service status
- logs: Tail logs

Example:
- control_hub.exe up
- control_hub.exe stop --services rfid-proxy,udp-listener

Build to a single exe (Windows):
- pip install pyinstaller
- pyinstaller --onefile control_hub.py

Config:
- control-hub/config.json
