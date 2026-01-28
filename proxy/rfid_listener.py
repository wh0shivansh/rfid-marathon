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
    END = "end"


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
LISTENER_PORT = int(os.getenv("LISTENER_PORT", 9090))

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
    "end": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "END LINE",
    },
}


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
        if "start" in path:
            return TimingPoint.START

    if reader_name:
        if "reader 2" in reader_name or "reader2" in reader_name or "end" in reader_name:
            return TimingPoint.END
        if "reader 1" in reader_name or "reader1" in reader_name or "start" in reader_name:
            return TimingPoint.START

    return TimingPoint.START


def get_hub_state(timing_point: TimingPoint) -> Dict[str, Any]:
    return hub_states.get(timing_point.value, hub_states["start"])


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


@app.post("/reader")
@app.post("/reader/start")
@app.post("/reader/end")
async def receive_from_hub(request: Request):
    hit_timestamp = getattr(request.state, "hit_timestamp", current_ts())
    try:
        data = await request.json()
    except Exception as exc:
        logger.error(f"[READER] Failed to parse JSON: {exc}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    timing_point = get_timing_point_from_request(request, data)
    hub_state = get_hub_state(timing_point)
    reader_label = "Reader 1 (START)" if timing_point == TimingPoint.START else "Reader 2 (END)"

    # logger.debug(f"[READER-{timing_point.value.upper()}] {reader_label} - Incoming request from {request.client.host if request.client else 'unknown'}")
    # logger.debug(f"[READER-{timing_point.value.upper()}] Headers: {dict(request.headers)}")
    # logger.debug(f"[READER-{timing_point.value.upper()}] Raw payload: {data}")

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
            rfid = tag.get("ep") or tag.get("epc")

            if not rfid:
                # logger.warning(f"[TAG_HANDLER-{tp_label}] Tag #{idx + 1} missing RFID field: {tag}")
                errors.append({"error": "Missing RFID field", "tag": tag})
                continue

            payload = build_payload(
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

            launch_forward_task(payload, tp_label)
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
        "timing_point": timing_point.value,
        "hit_timestamp": hit_timestamp,
        "antenna": antenna,
        "read_count": read_count,
        "signal_strength": signal_strength,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "bank_data": bank_data,
        "protocol": protocol,
    }


def launch_forward_task(payload: Dict[str, Any], tp_label: str) -> None:
    async def _send():
        await forward_to_backend_async(payload, tp_label)

    task = asyncio.create_task(_send())

    def _log_result(task_obj: asyncio.Task):
        if task_obj.cancelled():
            # logger.warning(f"[FORWARD-{tp_label}] Task cancelled")
            return
        exc = task_obj.exception()
        if exc:
            logger.error(f"[FORWARD-{tp_label}] Task failed: {exc}", exc_info=True)

    task.add_done_callback(_log_result)


async def forward_to_backend_async(payload: Dict[str, Any], tp_label: str) -> None:
    backend_endpoint = f"{BACKEND_URL}/api/v1/rfid/hit"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(backend_endpoint, json=payload)
            # logger.debug(f"[FORWARD-{tp_label}] Backend response: status={response.status_code}, body={response.text}")
            if response.status_code not in (200, 201):
                logger.warning(f"[FORWARD-{tp_label}] Backend returned {response.status_code} for {payload.get('rfid')}")
    except httpx.TimeoutException as exc:
        logger.error(f"[FORWARD-{tp_label}] Timeout forwarding to backend: {exc}")
    except httpx.RequestError as exc:
        logger.error(f"[FORWARD-{tp_label}] Request error to backend: {exc}")
    except Exception as exc:
        logger.error(f"[FORWARD-{tp_label}] Unexpected error forwarding to backend: {exc}", exc_info=True)


@app.post("/test")
@app.post("/test/start")
@app.post("/test/end")
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

    payload = build_payload(
        rfid=rfid,
        timing_point=timing_point,
        hit_timestamp=hit_timestamp,
        antenna=antenna,
    )

    launch_forward_task(payload, tp_label)

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
