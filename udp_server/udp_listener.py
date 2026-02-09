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
load_dotenv()

PROXY_URL = os.getenv('PROXY_URL', 'http://127.0.0.1:9090/reader')
END_HOST = os.getenv('BIND_HOST', '0.0.0.0')
END_PORT = int(os.getenv('BIND_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))
PROXY_TIMEOUT = float(os.getenv('PROXY_TIMEOUT', '5'))
LISTENER_FLUSH_SECONDS = int(os.getenv('LISTENER_FLUSH_SECONDS', '10'))

# Default reader name to use when payload doesn't include one (matches send_test_tag.py)
DEFAULT_READER_NAME = os.getenv('READER_NAME', 'Reader 2')

cache_lock = threading.Lock()
# cache_seen keys are composed as "reader|rfid" to dedupe per-reader
cache_seen: Set[str] = set()
# entries are normalized dicts: {'rfid': str, 'timestamp': str, 'reader_name': str}
cache_entries: List[Dict[str, str]] = []


def extract_reader_name(payload: object) -> str:
	if isinstance(payload, dict):
		return str(payload.get('reader_name', '') or '').lower().strip()
	return ''


def normalize_timestamp(value: object) -> str:
	try:
		if value is None:
			raise ValueError
		# numeric (ms or s)
		if isinstance(value, (int, float)):
			v = float(value)
			# heuristic: > 1e10 -> ms, else seconds
			if v > 1e10:
				ts = v / 1000.0
			else:
				ts = v
			return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ts)) + 'Z'
		# string pass-through
		if isinstance(value, str):
			return value
	except Exception:
		pass
	# fallback to ISO-like now in UTC
	return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + 'Z'


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


def cache_entries_once(entries: List[dict], reader_name: str) -> int:
	effective_reader = reader_name or DEFAULT_READER_NAME
	with cache_lock:
		added = 0
		for entry in entries:
			if not isinstance(entry, dict):
				continue
			# find rfid from common keys
			rfid = entry.get('rfid') or entry.get('epc') or entry.get('ep') or entry.get('tid') or entry.get('id')
			if not rfid:
				continue
			rfid_key = str(rfid)
			seen_key = f"{effective_reader}|{rfid_key}"
			if seen_key in cache_seen:
				continue
			cache_seen.add(seen_key)

			# normalize timestamp from known keys
			ts_val = None
			for k in ('timestamp', 'ts', 'time', 'ft', 'lt'):
				if k in entry:
					ts_val = entry.get(k)
					break

			normalized = {
				'rfid': rfid_key,
				'timestamp': normalize_timestamp(ts_val),
				'reader_name': effective_reader,
			}
			cache_entries.append(normalized)
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

		# Group by reader_name and forward per-reader
		by_reader: Dict[str, List[Dict[str, str]]] = {}
		for e in batch:
			rn = str(e.get('reader_name') or DEFAULT_READER_NAME)
			by_reader.setdefault(rn, []).append(e)

		for rn, items in by_reader.items():
			# forward entries (they already include reader_name field)
			forward_to_proxy({"event_type": "tag_read", "event_data": items}, rn)


def start_udp_server():
	logger.info(f"Starting end-line UDP server on {END_HOST}:{END_PORT}, forwarding to {PROXY_URL}")
	threading.Thread(target=flush_cache_loop, daemon=True).start()
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sock.bind((END_HOST, END_PORT))

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
			added = cache_entries_once(event_data, reader_name)
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

