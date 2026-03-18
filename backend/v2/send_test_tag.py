"""
Dummy RFID sender for backend bulk endpoint.

Reads/writes JSON payloads in the same tag data style used by UDP sender:
{
  "event_type": "tag_read",
  "event_data": [{"epc": "...", "ft": <ms>, "lt": <ms>}],
  "reader_name": "Reader 3"
}

Then converts each tag into one bulk payload like the listener posts:
{
	"entries": [
		{"rfid": "...", "reader_id": 2, "timestamp": "..."}
	]
}

and sends it in a single request to /api/v2/rfid/bulk.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib import error, request

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Editable test controls (update these directly, no CLI args needed)
# ---------------------------------------------------------------------------
START_COUNT: int = 130
END_COUNT: int = 159
READER_NAME: str = os.getenv("READER_NAME", "Reader 3")
BULK_ENDPOINT_URL: str = os.getenv("BULK_ENDPOINT_URL", "http://127.0.0.1:8000/api/v2/rfid/bulk")
DRY_RUN: bool = False
REQUEST_TIMEOUT_SECONDS: float = 10.0

RFID_DEFAULT_PREFIX: str = str(os.getenv("RFID_DEFAULT_PREFIX", "2")).strip().upper()
RFID_DEFAULT_SUFFIX_DIGITS: int = max(1, int(os.getenv("RFID_DEFAULT_SUFFIX_DIGITS", "3")))

def _now_ms() -> int:
	return int(time.time() * 1000)


def _epoch_ms_to_iso(ms: int) -> str:
	return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _infer_timing_point(reader_name: str) -> str:
	value = (reader_name or "").strip().lower()
	if "reader 3" in value or "reader3" in value or value == "end":
		return "end"
	if "reader 2" in value or "reader2" in value or value == "mid":
		return "mid"
	return "start"


def _reader_id_from_timing_point(timing_point: str) -> int:
	if timing_point == "start":
		return 1
	if timing_point == "mid":
		return 2
	return 3


def _build_test_rfid(sequence: int) -> str:
	return f"{RFID_DEFAULT_PREFIX}{int(sequence):0{RFID_DEFAULT_SUFFIX_DIGITS}d}"


def build_dummy_event_packet(reader_name: str, start_count: int, end_count: int) -> Dict[str, Any]:
	batch: List[Dict[str, Any]] = []
	for seq in range(start_count, end_count + 1):
		ft = _now_ms()
		lt = _now_ms()
		batch.append(
			{
				"epc": _build_test_rfid(seq),
				"ft": ft,
				"lt": lt,
			}
		)

	return {
		"event_type": "tag_read",
		"event_data": batch,
		"reader_name": reader_name,
	}


def build_bulk_entries(packet: Dict[str, Any]) -> List[Dict[str, Any]]:
	reader_name = str(packet.get("reader_name") or "Reader 3")
	timing_point = _infer_timing_point(reader_name)
	reader_id = _reader_id_from_timing_point(timing_point)
	tags = packet.get("event_data") or []

	entries: List[Dict[str, Any]] = []
	for tag in tags:
		epc = str(tag.get("epc") or "").upper().strip()
		if not epc:
			continue

		lt = int(tag.get("lt") or _now_ms())
		entries.append(
			{
				"rfid": epc,
				"reader_id": reader_id,
				"timestamp": _epoch_ms_to_iso(lt),
			}
		)

	return entries


def post_json(url: str, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
	body = json.dumps(payload).encode("utf-8")
	req = request.Request(
		url,
		data=body,
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with request.urlopen(req, timeout=timeout) as resp:
		raw = resp.read().decode("utf-8")
		try:
			return json.loads(raw)
		except json.JSONDecodeError:
			return {"raw": raw, "status": resp.status}


def main() -> None:
	start_count = max(1, int(START_COUNT))
	end_count = max(start_count, int(END_COUNT))
	reader_name = READER_NAME
	url = BULK_ENDPOINT_URL

	packet = build_dummy_event_packet(reader_name=reader_name, start_count=start_count, end_count=end_count)
	timing_point = _infer_timing_point(reader_name)
	reader_id = _reader_id_from_timing_point(timing_point)
	entries = build_bulk_entries(packet)

	print(f"Built packet with {len(entries)} tags from reader '{reader_name}'")
	print(f"Resolved timing_point='{timing_point}', reader_id={reader_id}")
	print(
		f"RFID pattern prefix='{RFID_DEFAULT_PREFIX}', suffix_digits={RFID_DEFAULT_SUFFIX_DIGITS}, "
		f"start_count={start_count}, end_count={end_count}"
	)
	if not entries:
		print("No valid payloads to send")
		return

	bulk_payload = {"entries": entries}

	if DRY_RUN:
		print(json.dumps({"event_packet": packet, "bulk_payload": bulk_payload}, indent=2))
		return

	try:
		response = post_json(url, bulk_payload, timeout=REQUEST_TIMEOUT_SECONDS)
		status_msg = response.get("message") or response.get("data", {}).get("message")
		print(f"Bulk OK entries={len(entries)} -> {status_msg}")
	except error.HTTPError as exc:
		try:
			err_body = exc.read().decode("utf-8")
		except Exception:
			err_body = ""
		print(f"Bulk HTTP {exc.code} entries={len(entries)} -> {err_body}")
	except Exception as exc:
		print(f"Bulk ERROR entries={len(entries)} -> {exc}")

	print(f"Done. entries={len(entries)}, url={url}")


if __name__ == "__main__":
	main()

