"""
End-line UDP listener -> HTTP proxy forwarder

This script listens for UDP packets produced by the mid-line FastAPI forwarder
(`udp_sender.py`). Incoming UDP packets are expected to contain a JSON payload
which will be forwarded to the proxy HTTP endpoint (default: http://127.0.0.1:9090/reader).

Usage:
  python udp_listener.py

Environment variables:
	PROXY_URL  - full URL of the proxy HTTP endpoint (default: http://127.0.0.1:9090/reader)
	BIND_HOST  - host to bind UDP server (default: 0.0.0.0)
	BIND_PORT  - port to bind UDP server (default: 6000)
	BUFFER_SIZE - UDP recv buffer size (default: 8192)
	PROXY_TIMEOUT - HTTP timeout seconds (default: 5)
	LISTENER_FLUSH_SECONDS - seconds between bulk proxy flush (default: 10)
"""

import os
import socket
import json
import logging
import requests
import time
import sys
import threading
from pathlib import Path
from multiprocessing import freeze_support
from typing import Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [end-server] %(levelname)s: %(message)s')
logger = logging.getLogger('end_server')

from dotenv import load_dotenv

PROXY_URL = os.getenv('PROXY_URL', 'http://127.0.0.1:9090/reader')
BIND_HOST = os.getenv('BIND_HOST', '0.0.0.0')
BIND_PORT = int(os.getenv('BIND_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))
PROXY_TIMEOUT = float(os.getenv('PROXY_TIMEOUT', '5'))
LISTENER_FLUSH_SECONDS = int(os.getenv('LISTENER_FLUSH_SECONDS', '10'))
PROXY_URL = 'http://127.0.0.1:9090/reader'

cache_lock = threading.Lock()
cache_seen: Set[str] = set()
cache_entries: List[Dict[str, object]] = []


def extract_reader_name(payload: object) -> str:
	if isinstance(payload, dict):
		return str(payload.get('reader_name', '') or '').lower().strip()
	return ''


def forward_to_proxy(body: dict, reader_name: str) -> Tuple[Optional[int], str]:
	headers = {
		'Content-Type': 'application/json'
	}
	if reader_name:
		headers['X-Reader-Name'] = reader_name
	try:
		resp = requests.post(PROXY_URL, json=body, headers=headers, timeout=PROXY_TIMEOUT)
		logger.info(f"Forwarded {len(body.get('event_data', []))} tag(s) to proxy {PROXY_URL} -> status={resp.status_code}")
		return resp.status_code, resp.text
	except Exception as e:
		logger.exception(f"Failed to forward to proxy {PROXY_URL}: {e}")
		return None, str(e)


def normalize_event_data(payload: object) -> List[dict]:
	if isinstance(payload, dict) and isinstance(payload.get('event_data'), list):
		return payload.get('event_data', [])
	if isinstance(payload, dict) and isinstance(payload.get('entries'), list):
		return payload.get('entries', [])
	if isinstance(payload, list):
		return payload
	return []


def cache_entries_once(entries: List[dict]) -> int:
	with cache_lock:
		added = 0
		for entry in entries:
			if not isinstance(entry, dict):
				continue
			rfid = entry.get('rfid') or entry.get('epc')
			if not rfid:
				continue
			rfid_key = str(rfid)
			if rfid_key in cache_seen:
				continue
			cache_seen.add(rfid_key)
			cache_entries.append(entry)
			added += 1
		return added


def flush_cache_loop() -> None:
	while True:
		time.sleep(max(1, LISTENER_FLUSH_SECONDS))
		with cache_lock:
			if not cache_entries:
				continue
			batch = list(cache_entries)
			cache_entries.clear()
			cache_seen.clear()
		reader_name = ''
		forward_to_proxy({"event_type": "tag_read", "event_data": batch}, reader_name)


def start_udp_server():
	logger.info(f"Starting end-line UDP server on {BIND_HOST}:{BIND_PORT}, forwarding to {PROXY_URL}")
	threading.Thread(target=flush_cache_loop, daemon=True).start()
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sock.bind((BIND_HOST, BIND_PORT))

	while True:
		try:
			data, addr = sock.recvfrom(BUFFER_SIZE)
			logger.debug(f"Received {len(data)} bytes from {addr}")
			try:
				payload = json.loads(data.decode('utf-8'))
			except Exception as e:
				logger.warning(f"Invalid JSON from {addr}: {e}; raw={data!r}")
				continue

			reader_name = extract_reader_name(payload)
			event_data = normalize_event_data(payload)
			if not event_data:
				continue
			added = cache_entries_once(event_data)
			if added:
				logger.info(f"Cached {added} new tag(s) for reader {reader_name or 'unknown'}")

		except KeyboardInterrupt:
			logger.info('Shutting down end-line UDP server')
			break
		except Exception as e:
			logger.exception(f"Unexpected error in UDP loop: {e}")
			time.sleep(1)


if __name__ == '__main__':
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
		start_udp_server()

	main()

