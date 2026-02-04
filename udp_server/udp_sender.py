"""
Mid-line HTTP -> UDP forwarder

This service exposes a small FastAPI HTTP endpoint (`/reader`) which accepts JSON
payloads from RFID hubs (which use TCP/HTTP). The forwarder normalizes the payload
and forwards it over UDP to an end-line UDP server (default localhost:6000).

Usage:
  python udp_sender.py
  OR run with uvicorn: `uvicorn udp_sender:app --host 0.0.0.0 --port 6001`

Environment variables:
  END_HOST   - hostname/ip of end-line UDP server (default: 127.0.0.1)
  END_PORT   - port of end-line UDP server (default: 6000)
  BIND_HOST  - host to bind FastAPI (uvicorn can override)
  BIND_PORT  - port to bind FastAPI (uvicorn can override)
"""

import os
import socket
import json
import logging
from typing import Any, List, cast

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s [mid-server] %(levelname)s: %(message)s')
logger = logging.getLogger('udp_sender')

END_HOST = os.getenv('END_HOST', '127.0.0.1')
END_PORT = int(os.getenv('END_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))


app = FastAPI(title='Mid-line HTTP->UDP forwarder')


def normalize_event_data(payload: Any) -> List[dict]:
    """Return a list of tag dicts extracted from payload."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    if payload.get('event_type') in ('tag_read', 'tag_coming') and isinstance(payload.get('event_data'), list):
        return cast(List[dict], payload.get('event_data', []))

    tag_keys = ('epc', 'ep', 'tid', 'id', 'tag_id', 'rfid', 'rfid_tag')
    for k in tag_keys:
        if k in payload:
            return [payload]

    if 'tags' in payload and isinstance(payload.get('tags'), list):
        return cast(List[dict], payload.get('tags', []))
    if 'data' in payload and isinstance(payload.get('data'), list):
        return cast(List[dict], payload.get('data', []))

    possible = []
    for v in payload.values():
        if isinstance(v, dict) and any(k in v for k in tag_keys):
            possible.append(v)
    if possible:
        return possible

    return []


def send_udp_message(data: bytes, host: str = END_HOST, port: int = END_PORT) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (host, port))
        logger.info(f"Sent UDP packet to {host}:{port} ({len(data)} bytes)")
    finally:
        sock.close()


@app.post('/reader')
async def receive_reader(payload: dict):
    """Receive JSON from RFID hub and forward over UDP to end-line server."""
    try:
        event_data = normalize_event_data(payload)
        if not event_data:
            return {"success": False, "message": "No tag data extracted", "processed": 0}

        packet = json.dumps({"event_type": "tag_read", "event_data": event_data}).encode('utf-8')
        send_udp_message(packet)

        return {"success": True, "message": "Forwarded via UDP", "processed": len(event_data)}
    except Exception as e:
        logger.exception(f"Failed to handle incoming payload: {e}")
        return {"success": False, "message": str(e)}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('udp_sender:app', host=os.getenv('BIND_HOST', '0.0.0.0'), port=int(os.getenv('BIND_PORT', '6001')))
