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
"""

import os
import socket
import json
import logging
import requests
import time
import sys
from pathlib import Path
from multiprocessing import freeze_support
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [end-server] %(levelname)s: %(message)s')
logger = logging.getLogger('end_server')

from dotenv import load_dotenv

PROXY_URL = os.getenv('PROXY_URL', 'http://127.0.0.1:9090/reader')
BIND_HOST = os.getenv('BIND_HOST', '0.0.0.0')
BIND_PORT = int(os.getenv('BIND_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))
PROXY_TIMEOUT = float(os.getenv('PROXY_TIMEOUT', '5'))
PROXY_URL = 'http://127.0.0.1:9090/reader'


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


def start_udp_server():
	logger.info(f"Starting end-line UDP server on {BIND_HOST}:{BIND_PORT}, forwarding to {PROXY_URL}")
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
			# Expecting an object like {"event_type": "tag_read", "event_data": [...]}
			if isinstance(payload, dict) and 'event_type' in payload and isinstance(payload.get('event_data'), list):
				forward_to_proxy(payload, reader_name)
			elif isinstance(payload, dict) and isinstance(payload.get('entries'), list):
				forward_to_proxy({"event_type": "tag_read", "event_data": payload.get('entries', [])}, reader_name)
			else:
				# Try to normalize into event_data list
				event_data = payload if isinstance(payload, list) else [payload]
				forward_to_proxy({"event_type": "tag_read", "event_data": event_data}, reader_name)

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

