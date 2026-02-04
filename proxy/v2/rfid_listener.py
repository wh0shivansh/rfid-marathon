"""
RFID Marathon Management System - Unified RFID Listener (FastAPI)
- Uses middleware to capture hit timestamps immediately (Asia/Kolkata)
- Prioritizes request acceptance by offloading backend forwarding asynchronously
- Supports both start-line and end-line hubs via a unified listener
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import re

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI(title="RFID Listener", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TimingPoint(Enum):
    START = "start"
    MID = "mid"
    END = "end"


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
BACKEND_BULK_ENDPOINT = os.getenv("BACKEND_BULK_ENDPOINT", "/api/v2/rfid/bulk")
LISTENER_PORT = int(os.getenv("LISTENER_PORT", 9090))
RFID_BULK_FLUSH_SECONDS = int(os.getenv("RFID_BULK_FLUSH_SECONDS", 5))

logger.info(f"[CONFIG] Backend URL: {BACKEND_URL}")
logger.info(f"[CONFIG] Listener Port: {LISTENER_PORT}")


hub_states: Dict[str, Dict[str, Any]] = {
    "start": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "START LINE",
    },
    "mid": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "MID POINT",
    },
    "end": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "END LINE",
    },
}

cache_lock = asyncio.Lock()
rfid_cache: List[Dict[str, Any]] = []
flush_task: Optional[asyncio.Task] = None


def current_ts() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()


@app.middleware("http")
async def capture_timestamp(request: Request, call_next):
    # Capture as early as possible for all requests
    request.state.hit_timestamp = current_ts()
    response = await call_next(request)
    response.headers["X-Hit-Timestamp"] = request.state.hit_timestamp
    return response


def get_timing_point_from_request(request: Request, data: Optional[Dict[str, Any]]) -> TimingPoint:
    reader_name = (request.headers.get("X-Reader-Name", "") or "").lower()

    if not reader_name and data and isinstance(data, dict):
        reader_name = str(data.get("reader_name", "")).lower()

    if not reader_name:
        path = request.url.path.lower()
        if "end" in path:
            return TimingPoint.END
        if "mid" in path:
            return TimingPoint.MID
        if "start" in path:
            return TimingPoint.START

    if reader_name:
        if "reader 3" in reader_name or "reader3" in reader_name or "end" in reader_name:
            return TimingPoint.END
        if "reader 2" in reader_name or "reader2" in reader_name or "mid" in reader_name:
            return TimingPoint.MID
        if "reader 1" in reader_name or "reader1" in reader_name or "start" in reader_name:
            return TimingPoint.START

    return TimingPoint.START


def get_hub_state(timing_point: TimingPoint) -> Dict[str, Any]:
    return hub_states.get(timing_point.value, hub_states["start"])


def reader_id_from_timing_point(timing_point: TimingPoint) -> int:
    if timing_point == TimingPoint.START:
        return 1
    if timing_point == TimingPoint.MID:
        return 2
    return 3


async def add_to_cache(entry: Dict[str, Any]) -> None:
    async with cache_lock:
        rfid_cache.append(entry)


async def flush_cache_once() -> None:
    async with cache_lock:
        if not rfid_cache:
            return
        batch = list(rfid_cache)
        rfid_cache.clear()

    payload = {"entries": batch}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{BACKEND_URL}{BACKEND_BULK_ENDPOINT}", json=payload)
            logger.info(f"[BULK_FLUSH] Successfully sent {len(batch)} entries to backend\n{payload}")
            if response.status_code not in (200, 201):
                raise httpx.HTTPStatusError(
                    f"Unexpected status code: {response.status_code}",
                    request=response.request,
                    response=response
                )
    except Exception as exc:
        logger.error(f"[BULK_FLUSH] Failed to flush {len(batch)} entries: {exc}")
        # Requeue on failure
        async with cache_lock:
            rfid_cache[:0] = batch


async def flush_cache_periodically() -> None:
    while True:
        await asyncio.sleep(RFID_BULK_FLUSH_SECONDS)
        logger.debug("[BULK_FLUSH] Periodic flush triggered")
        await flush_cache_once()


@app.on_event("startup")
async def start_flush_task() -> None:
    global flush_task
    flush_task = asyncio.create_task(flush_cache_periodically())


@app.on_event("shutdown")
async def stop_flush_task() -> None:
    global flush_task
    if flush_task:
        flush_task.cancel()
        flush_task = None


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "unified-rfid-listener",
        "start_line": hub_states["start"],
        "end_line": hub_states["end"],
    }


@app.get("/health/start")
async def health_check_start():
    return {"status": "ok", "service": "unified-rfid-listener-start-line", "hub_state": hub_states["start"]}


@app.get("/health/end")
async def health_check_end():
    return {"status": "ok", "service": "unified-rfid-listener-end-line", "hub_state": hub_states["end"]}


@app.post("/flush")
async def flush_now():
    """Administrative endpoint to force a cache flush immediately (for testing)."""
    try:
        await flush_cache_once()
        return {"status": "ok", "flushed": True}
    except Exception as e:
        logger.error(f"[FLUSH] Forced flush failed: {e}")
        raise HTTPException(status_code=500, detail="Flush failed")


@app.post("/reader")
async def receive_from_hub(request: Request):
    hit_timestamp = getattr(request.state, "hit_timestamp", current_ts())
    try:
        data = await request.json()
    except Exception as exc:
        logger.error(f"[READER] Failed to parse JSON: {exc}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    timing_point = get_timing_point_from_request(request, data)
    hub_state = get_hub_state(timing_point)

    # logger.debug(f"[READER-{timing_point.value.upper()}] {reader_label} - Incoming request from {request.client.host if request.client else 'unknown'}")
    # logger.debug(f"[READER-{timing_point.value.upper()}] Headers: {dict(request.headers)}")
    logger.debug(f"[READER-{timing_point.value.upper()}] Raw payload: {data}")

    event_type = data.get("event_type") if isinstance(data, dict) else None
    event_data = data.get("event_data", []) if isinstance(data, dict) else []

    # logger.info(f"[READER-{timing_point.value.upper()}] {reader_label} - event_type={event_type}, data_count={len(event_data) if isinstance(event_data, list) else 'N/A'}")

    if event_type in ["tag_read", "tag_coming"]:
        return await handle_tag_events(event_data, timing_point, hit_timestamp)

    if event_type == "heart_beat":
        hub_state["heartbeat_count"] = event_data
        hub_state["last_heartbeat"] = hit_timestamp
        hub_state["device_state"] = "OK"
        logger.debug(f"[HEARTBEAT-{timing_point.value.upper()}] Hub heartbeat #{event_data}, state: OK")
        return {"status": "ok", "heartbeat_received": True}

    if event_type == "gpi_changed":
        if isinstance(event_data, list) and event_data:
            states = "".join([str(gpi.get("state", "0")) for gpi in event_data])
            hub_state["gpi_states"] = states
            # logger.info(f"[GPIO-{timing_point.value.upper()}] GPIO state changed: {states}")
        else:
            logger.warning(f"[GPIO-{timing_point.value.upper()}] Invalid GPI data: {event_data}")
        return {"status": "ok", "gpi_updated": True}

    if event_type == "reader_exception":
        err_code = event_data.get("err_code") if isinstance(event_data, dict) else None
        err_string = event_data.get("err_string") if isinstance(event_data, dict) else str(event_data)
        hub_state["device_state"] = f"ERROR: {err_code} - {err_string}"
        logger.error(f"[HUB_ERROR-{timing_point.value.upper()}] Hub error: code={err_code}, message={err_string}")
        logger.error(f"[HUB_ERROR-{timing_point.value.upper()}] Full error data: {event_data}")
        return {"status": "error", "error_code": err_code}

    # logger.debug(f"[READER-{timing_point.value.upper()}] Unknown event data: {event_data}")
    return {"status": "unknown_event", "event_type": event_type}


async def handle_tag_events(tags: List[Dict[str, Any]], timing_point: TimingPoint, hit_timestamp: str):
    tp_label = timing_point.value.upper()
    # logger.debug(f"[TAG_HANDLER-{tp_label}] Received tags data: type={type(tags)}, content={tags}")

    if not isinstance(tags, list) or not tags:
        # logger.warning(f"[TAG_HANDLER-{tp_label}] No valid tags to process (type: {type(tags)})")
        return {"status": "ok", "tags_processed": 0, "timing_point": timing_point.value}

    # logger.info(f"[TAG_HANDLER-{tp_label}] Processing {len(tags)} tag(s)")
    processed_count = 0
    errors: List[Dict[str, Any]] = []

    for idx, tag in enumerate(tags):
        try:
            # logger.debug(f"[TAG_HANDLER-{tp_label}] Processing tag #{idx + 1}: {tag}")
            # Prefer canonical 'epc', then 'ep', then other common keys. Normalize to hex uppercase.
            rfid_raw = tag.get("epc") or tag.get("ep") or tag.get("tid") or tag.get("id") or tag.get("tag_id")

            rfid = None
            if rfid_raw:
                # strip any non-hex characters and uppercase
                cleaned = re.sub(r"[^A-Fa-f0-9]", "", str(rfid_raw))
                rfid = cleaned.upper() if cleaned else None

            # fallback: try bank data (bd) if available
            if not rfid:
                bd = tag.get("bd", "")
                bd_clean = re.sub(r"[^A-Fa-f0-9]", "", str(bd))
                if bd_clean:
                    rfid = bd_clean.upper()

            if not rfid:
                errors.append({"error": "Missing RFID field", "tag": tag})
                continue

            entry = build_payload(
                rfid=rfid,
                timing_point=timing_point,
                hit_timestamp=hit_timestamp,
                antenna=tag.get("at", 0),
                read_count=tag.get("rc", 1),
                signal_strength=tag.get("ri", 0),
                first_seen=tag.get("ft"),
                last_seen=tag.get("lt"),
                bank_data=tag.get("bd", ""),
                protocol=tag.get("pt", "EPC"),
            )

            await add_to_cache(entry)
            processed_count += 1
        except Exception as exc:
            logger.error(f"[TAG_HANDLER-{tp_label}] Error processing tag #{idx + 1}: {exc}", exc_info=True)
            errors.append({"error": str(exc), "tag": tag})

    response: Dict[str, Any] = {
        "status": "ok",
        "tags_processed": processed_count,
        "tags_total": len(tags),
        "timing_point": timing_point.value,
    }

    if errors:
        response["errors"] = errors
        # logger.warning(f"[TAG_HANDLER-{tp_label}] Completed with {len(errors)} error(s)")

    # logger.info(f"[TAG_HANDLER-{tp_label}] Processing complete: {processed_count}/{len(tags)} tags scheduled for forwarding")
    return response


def build_payload(
    rfid: str,
    timing_point: TimingPoint,
    hit_timestamp: str,
    antenna: int = 0,
    read_count: int = 1,
    signal_strength: int = 0,
    first_seen: Optional[int] = None,
    last_seen: Optional[int] = None,
    bank_data: str = "",
    protocol: str = "EPC",
) -> Dict[str, Any]:
    return {
        "rfid": rfid,
        "reader_id": reader_id_from_timing_point(timing_point),
        "timestamp": hit_timestamp,
        "timing_point": timing_point.value,
        "antenna": antenna,
        "read_count": read_count,
        "signal_strength": signal_strength,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "bank_data": bank_data,
        "protocol": protocol,
    }


@app.post("/test")
async def test_scan(request: Request):
    timing_point = get_timing_point_from_request(request, None)
    tp_label = timing_point.value.upper()
    try:
        data = await request.json()
    except Exception:
        data = {}

    rfid = data.get("rfid", "TEST123456") if isinstance(data, dict) else "TEST123456"
    antenna = data.get("antenna", 1) if isinstance(data, dict) else 1
    hit_timestamp = getattr(request.state, "hit_timestamp", current_ts())

    entry = build_payload(
        rfid=rfid,
        timing_point=timing_point,
        hit_timestamp=hit_timestamp,
        antenna=antenna,
    )

    await add_to_cache(entry)

    # logger.info(f"[TEST-{tp_label}] Test scan initiated: {rfid} on antenna {antenna}")

    return {
        "test": True,
        "rfid": rfid,
        "antenna": antenna,
        "timing_point": timing_point.value,
        "scheduled": True,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rfid_listener:app", host="0.0.0.0", port=LISTENER_PORT, reload=False, log_level="debug")
