"""
Mid-line HTTP -> UDP forwarder

This service exposes a small FastAPI HTTP endpoint (`/reader`) which accepts JSON
payloads from RFID hubs (which use TCP/HTTP). The forwarder normalizes the payload
and forwards it over UDP to an end-line UDP server (default localhost:6000).

Usage:
  python udp_sender.py
  OR run with uvicorn: `uvicorn udp_sender:app --host 0.0.0.0 --port 6001`

Environment variables:
    END_HOST              - hostname/ip of end-line UDP server (default: 127.0.0.1)
    END_PORT              - port of end-line UDP server (default: 6000)
    BIND_HOST             - host to bind FastAPI (uvicorn can override)
    BIND_PORT             - port to bind FastAPI (uvicorn can override)
    UDP_SEND_INTERVAL_SECONDS - seconds between UDP sends (default: 2)
    UDP_SEND_REPEATS      - number of times to resend the same cache (default: 5)
    UDP_BULK_MAX_SIZE     - max RFIDs per UDP batch (default: 100)
"""

import os
import socket
import json
import logging
import asyncio
import sys
from pathlib import Path
from multiprocessing import freeze_support
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple, cast

from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format='%(asctime)s [mid-server] %(levelname)s: %(message)s')
logger = logging.getLogger('udp_sender')

from dotenv import load_dotenv

END_HOST = os.getenv('END_HOST', '192.168.1.10')
END_PORT = int(os.getenv('END_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))
UDP_SEND_INTERVAL_SECONDS = int(os.getenv('UDP_SEND_INTERVAL_SECONDS', '2'))
UDP_SEND_REPEATS = int(os.getenv('UDP_SEND_REPEATS', '5'))
UDP_BULK_MAX_SIZE = int(os.getenv('UDP_BULK_MAX_SIZE', '100'))


app = FastAPI(title='Mid-line HTTP->UDP forwarder')


cache_lock = asyncio.Lock()
cache_send: Dict[str, Dict[str, Dict[str, Any]]] = {}
cache_next: Dict[str, Dict[str, Dict[str, Any]]] = {}
flush_task: Optional[asyncio.Task] = None


def current_ts() -> str:
    try:
        return datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()
    except Exception:
        return datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()


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


def extract_rfid(tag: Dict[str, Any]) -> Optional[str]:
    for key in ('rfid', 'epc', 'ep', 'tid', 'id', 'tag_id', 'rfid_tag'):
        value = tag.get(key)
        if value:
            return str(value)
    return None


def extract_timestamp(tag: Dict[str, Any]) -> str:
    for key in ('timestamp', 'ts', 'time'):
        value = tag.get(key)
        if value:
            return str(value)
    return current_ts()


def normalize_reader_name(request: Request, payload: Any) -> str:
    reader_name = (request.headers.get('X-Reader-Name', '') or '').lower().strip()
    if not reader_name and isinstance(payload, dict):
        reader_name = str(payload.get('reader_name', '') or '').lower().strip()
    return reader_name


def send_udp_message(data: bytes, host: str = END_HOST, port: int = END_PORT) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (host, port))
        logger.info(f"Sent UDP packet to {host}:{port} ({len(data)} bytes)")
    finally:
        sock.close()


def chunk_list(items: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    if chunk_size <= 0:
        return [items]
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


async def add_to_cache(entries: List[Dict[str, Any]], reader_name: str) -> int:
    async with cache_lock:
        bucket = cache_next.setdefault(reader_name, {})
        for entry in entries:
            rfid = entry.get('rfid')
            if rfid:
                bucket[rfid] = entry
        total_cached = sum(len(items) for items in cache_next.values())
        return total_cached


async def flush_cache_periodically() -> None:
    while True:
        async with cache_lock:
            if not cache_send and cache_next:
                cache_send.update(cache_next)
                cache_next.clear()
            batch_by_reader = {key: list(items.values()) for key, items in cache_send.items()}

        if not batch_by_reader:
            await asyncio.sleep(1)
            continue

        total_sent = 0
        for _ in range(max(1, UDP_SEND_REPEATS)):
            for reader_name, entries in batch_by_reader.items():
                for chunk in chunk_list(entries, UDP_BULK_MAX_SIZE):
                    payload = {"event_type": "tag_read", "event_data": chunk}
                    if reader_name:
                        payload["reader_name"] = reader_name
                    packet = json.dumps(payload).encode('utf-8')
                    send_udp_message(packet)
                    total_sent += len(chunk)
            await asyncio.sleep(max(1, UDP_SEND_INTERVAL_SECONDS))

        async with cache_lock:
            cache_send.clear()
            if cache_next:
                cache_send.update(cache_next)
                cache_next.clear()

        if total_sent:
            logger.info(f"Sent {total_sent} RFID(s) via UDP across {UDP_SEND_REPEATS} repeats")


@app.on_event('startup')
async def start_flush_task() -> None:
    global flush_task
    flush_task = asyncio.create_task(flush_cache_periodically())


@app.on_event('shutdown')
async def stop_flush_task() -> None:
    global flush_task
    if flush_task:
        flush_task.cancel()
        flush_task = None


@app.post('/reader')
async def receive_reader(request: Request, payload: dict):
    """Receive JSON from RFID hub and forward over UDP to end-line server."""
    try:
        event_data = normalize_event_data(payload)
        if not event_data:
            return {"success": False, "message": "No tag data extracted", "processed": 0}

        reader_name = normalize_reader_name(request, payload)

        entries: List[Dict[str, Any]] = []
        for tag in event_data:
            if not isinstance(tag, dict):
                continue
            rfid = extract_rfid(tag)
            if not rfid:
                continue
            entries.append({"rfid": rfid, "timestamp": extract_timestamp(tag)})

        if not entries:
            return {"success": False, "message": "No valid RFID entries", "processed": 0}

        cache_size = await add_to_cache(entries, reader_name)
        return {
            "success": True,
            "message": "Queued for UDP send cycle",
            "processed": len(entries),
            "cached_unique": cache_size,
        }
    except Exception as e:
        logger.exception(f"Failed to handle incoming payload: {e}")
        return {"success": False, "message": str(e)}


if __name__ == '__main__':
    import uvicorn

    def _set_working_directory() -> None:
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent
        os.chdir(base_dir)

    def main() -> None:
        freeze_support()
        _set_working_directory()
        load_dotenv()

        host = os.getenv("BIND_HOST", "0.0.0.0")
        port = int(os.getenv("BIND_PORT", "6001"))

        uvicorn.run(app, host=host, port=port, log_level="info")

    main()
