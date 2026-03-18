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
START_COUNT: int = 1
END_COUNT: int = 15
READER_NAME: str = os.getenv('READER_NAME', 'Reader 2')
RFID_DEFAULT_PREFIX: str = str(os.getenv("RFID_DEFAULT_PREFIX", "2")).strip().upper()
RFID_DEFAULT_SUFFIX_DIGITS: int = max(1, int(os.getenv("RFID_DEFAULT_SUFFIX_DIGITS", 3)))


def build_test_rfid(sequence: int) -> str:
  return f"{RFID_DEFAULT_PREFIX}{int(sequence):0{RFID_DEFAULT_SUFFIX_DIGITS}d}"

payload = {
  "epc": build_test_rfid(max(1, int(START_COUNT))),
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
start_count = max(1, int(START_COUNT))
end_count = max(start_count, int(END_COUNT))
for seq in range(start_count, end_count + 1):
  batch.append({
    "epc": build_test_rfid(seq),
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
print(
  f"RFID pattern prefix='{RFID_DEFAULT_PREFIX}', suffix_digits={RFID_DEFAULT_SUFFIX_DIGITS}, "
  f"start_count={start_count}, end_count={end_count}"
)
s.close()