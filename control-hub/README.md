Control Hub (Exe Orchestrator)

This utility starts and stops the packaged exe services directly (no Docker).

Placement:
- Put control_hub.exe inside RFID-Marathon-Automation.

Build to a single exe (Windows):
- pip install pyinstaller
- pyinstaller --onefile control_hub.py

Config:
- RFID-Marathon-Automation/config.json

Example config:
{
	"services": [
		{"name": "rfid-backend", "path": "rfid-backend/rfid-backend.exe"},
		{"name": "udp-listener", "path": "udp-listener/udp-listener.exe"}
	]
}
