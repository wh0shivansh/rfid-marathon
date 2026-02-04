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

HOST = os.getenv("TEST_HOST", "192.168.1.11")
PORT = int(os.getenv("TEST_PORT", "6000"))
HOST = "127.0.0.1"
PORT = 6000

payload = {
    "epc": "315354010100000000000014",
    "at": 1,
    "rc": 1,
    "ri": -57,
    "ft": int(time.time()*1000),
    "lt": int(time.time()*1000)
}

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
msg = json.dumps(payload).encode('utf-8')
# print(f"Sending test tag to {HOST}:{PORT}: {payload}")
s.sendto(msg, (HOST, PORT))
print("Sent")
s.close()
