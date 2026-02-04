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
  READER_NAME - value to send in the X-Reader-Name header
"""

import os
import socket
import json
import logging
import requests
import time
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [end-server] %(levelname)s: %(message)s')
logger = logging.getLogger('end_server')

PROXY_URL = os.getenv('PROXY_URL', 'http://127.0.0.1:9090/reader')
BIND_HOST = os.getenv('BIND_HOST', '0.0.0.0')
BIND_PORT = int(os.getenv('BIND_PORT', '6000'))
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '8192'))
READER_NAME = os.getenv('READER_NAME', 'Reader 3 - END')


def forward_to_proxy(body: dict) -> Tuple[Optional[int], str]:
	headers = {
		'Content-Type': 'application/json',
		'X-Reader-Name': READER_NAME
	}
	try:
		resp = requests.post(PROXY_URL, json=body, headers=headers, timeout=5)
		logger.info(f"Forwarded {len(body.get('event_data', []))} tag(s) to proxy {PROXY_URL} -> status={resp.status_code}")
		return resp.status_code, resp.text
	except Exception as e:
		logger.exception(f"Failed to forward to proxy {PROXY_URL}: {e}")
		return None, str(e)


def start_udp_server():
	logger.info(f"Starting end-line UDP server on {BIND_HOST}:{BIND_PORT}, forwarding to {PROXY_URL}")
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

			# Expecting an object like {"event_type": "tag_read", "event_data": [...]}
			if isinstance(payload, dict) and 'event_type' in payload and isinstance(payload.get('event_data'), list):
				forward_to_proxy(payload)
			else:
				# Try to normalize into event_data list
				event_data = payload if isinstance(payload, list) else [payload]
				forward_to_proxy({"event_type": "tag_read", "event_data": event_data})

		except KeyboardInterrupt:
			logger.info('Shutting down end-line UDP server')
			break
		except Exception as e:
			logger.exception(f"Unexpected error in UDP loop: {e}")
			time.sleep(1)


if __name__ == '__main__':
	start_udp_server()

