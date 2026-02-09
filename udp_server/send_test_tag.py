"""
Simple test sender to simulate a mid-line reader sending JSON via UDP.
Usage:
  python send_test_tag.py

It reads HOST and PORT from .env and sends a single JSON tag payload.
"""

import os
import socket
import json
import time

from dotenv import load_dotenv
load_dotenv()

HOST = "127.0.0.1"
PORT = 6000
READER_NAME = os.getenv('READER_NAME', 'Reader 2')

payload = {
    "epc": "315354010100000000000014",
    "at": 1,
    "rc": 1,
    "ri": -57,
    "ft": int(time.time()*1000),
    "lt": int(time.time()*1000)
}

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# send bulk of tags with timestamps to mimic udp_sender batching
batch = []
now_ms = lambda: int(time.time() * 1000)
for i in range(11, 51):
  batch.append({
    "epc": f"315354010100000000000{str(i).zfill(3)}",
    "ft": now_ms(),
    "lt": now_ms()
  })

bulk_msg = json.dumps({
  "event_type": "tag_read",
  "event_data": batch,
  "reader_name": READER_NAME
}).encode('utf-8')

s.sendto(bulk_msg, (HOST, PORT))
print(f"Sent bulk of {len(batch)} tags to {HOST}:{PORT}")
s.close()