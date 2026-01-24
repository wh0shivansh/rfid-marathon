"""
RFID Marathon Management System - Unified RFID Listener
Single listener service for both START LINE and END LINE RFID hubs
Runs on each laptop and forwards all RFID events to the central backend

This service:
- Listens on port 9090 for both start-line and end-line hubs
- Identifies timing point by reader name (Reader 1 = start, Reader 2 = end)
- Processes vendor API events (tag_read, tag_coming, heart_beat, gpi_changed, reader_exception)
- Forwards RFID hits to unified backend with timing_point metadata
- Maintains separate hub state for each reader

Hub Configuration:
- Reader 1: Start Line (name: "Reader 1" in POST header or payload)
- Reader 2: End Line (name: "Reader 2" in POST header or payload)

Vendor API Specification:
- Hub POSTs to /reader endpoint with reader_name field or header
- Event types: tag_read, tag_coming, heart_beat, gpi_changed, reader_exception
- Tag format: EPC (Electronic Product Code) with metadata
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

app = Flask(__name__)
CORS(app)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class TimingPoint(Enum):
    """Enum for timing points"""
    START = "start"
    END = "end"


# Get configuration from environment
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
LISTENER_PORT = int(os.getenv('LISTENER_PORT', 9090))

logger.info(f"[CONFIG] Backend URL: {BACKEND_URL}")
logger.info(f"[CONFIG] Listener Port: {LISTENER_PORT}")
logger.info(f"[CONFIG] Reader 1 (Start Line) - identified by 'Reader 1' name")
logger.info(f"[CONFIG] Reader 2 (End Line) - identified by 'Reader 2' name")

# Hub state tracking per timing point
hub_states: Dict[str, Dict[str, Any]] = {
    "start": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "START LINE"
    },
    "end": {
        "heartbeat_count": 0,
        "gpi_states": "",
        "device_state": "OK",
        "last_heartbeat": None,
        "label": "END LINE"
    }
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_timing_point_from_request() -> TimingPoint:
    """
    Determine timing point from reader name in request.
    
    Strategy:
    1. Check custom header 'X-Reader-Name'
    2. Check 'reader_name' field in JSON payload
    3. Check request path for 'start' or 'end'
    4. Default to START if cannot determine
    
    Reader name mapping:
    - "Reader 1" → START
    - "Reader 2" → END
    - Any name containing "start" → START
    - Any name containing "end" → END
    
    Returns:
        TimingPoint: START or END, defaults to START
    """
    reader_name = ""
    
    # Check custom header first
    reader_name = request.headers.get('X-Reader-Name', '').lower()
    
    # Check JSON payload reader_name field
    if not reader_name:
        try:
            data = request.get_json(force=True, silent=True)
            if data and isinstance(data, dict):
                reader_name = str(data.get('reader_name', '')).lower()
        except:
            pass
    
    # Check request path
    if not reader_name:
        path = request.path.lower()
        if 'end' in path:
            return TimingPoint.END
        elif 'start' in path:
            return TimingPoint.START
    
    # Parse reader name
    if reader_name:
        if 'reader 2' in reader_name or 'reader2' in reader_name or 'end' in reader_name:
            return TimingPoint.END
        elif 'reader 1' in reader_name or 'reader1' in reader_name or 'start' in reader_name:
            return TimingPoint.START
    
    # Default to START (never returns None)
    return TimingPoint.START


def get_hub_state(timing_point: TimingPoint) -> Dict[str, Any]:
    """Get hub state for a specific timing point"""
    return hub_states.get(timing_point.value, hub_states["start"])


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================


@app.route('/health', methods=['GET'])
def health_check():
    """Overall health check for the listener service"""
    logger.debug("[HEALTH] Health check requested")
    return jsonify({
        "status": "ok",
        "service": "unified-rfid-listener",
        "start_line": hub_states["start"],
        "end_line": hub_states["end"]
    }), 200


@app.route('/health/start', methods=['GET'])
def health_check_start():
    """Health check for start line"""
    logger.debug("[HEALTH] Start line health check requested")
    return jsonify({
        "status": "ok",
        "service": "unified-rfid-listener-start-line",
        "hub_state": hub_states["start"]
    }), 200


@app.route('/health/end', methods=['GET'])
def health_check_end():
    """Health check for end line"""
    logger.debug("[HEALTH] End line health check requested")
    return jsonify({
        "status": "ok",
        "service": "unified-rfid-listener-end-line",
        "hub_state": hub_states["end"]
    }), 200


# ============================================================================
# MAIN RFID READER ENDPOINTS (Both start and end line)
# ============================================================================


@app.route('/reader', methods=['POST'])
@app.route('/reader/start', methods=['POST'])
@app.route('/reader/end', methods=['POST'])
def receive_from_hub():
    """
    Receive data from RFID hub following vendor API specification.
    
    Supports both direct /reader calls (determines timing point by reader_name) 
    and path-specific /reader/start or /reader/end calls.
    
    Vendor payload format:
    {
        "reader_name": "Reader 1" or "Reader 2",  // IMPORTANT: Identifies timing point
        "event_type": "tag_read" | "tag_coming" | "heart_beat" | "gpi_changed" | "reader_exception",
        "event_data": [
            {
                "ep": "ABC123456",      // EPC (tag ID)
                "epc": "ABC123456",     // Alternative tag ID field
                "at": 1,                // Antenna
                "rc": 1,                // Read count
                "bd": "bank_data",      // Bank data
                "pt": "protocol",       // Protocol
                "ri": -65,              // RSSI (signal strength)
                "ft": 1234567890,       // First seen timestamp
                "lt": 1234567890        // Last seen timestamp
            }
        ]
    }
    
    Reader mapping:
    - Reader 1: Start Line RFID Hub
    - Reader 2: End Line RFID Hub
    """
    try:
        # Determine timing point from reader name
        timing_point = get_timing_point_from_request()
        hub_state = get_hub_state(timing_point)
        reader_label = "Reader 1 (START)" if timing_point == TimingPoint.START else "Reader 2 (END)"
        
        logger.debug(f"[READER-{timing_point.value.upper()}] {reader_label} - Incoming request from {request.remote_addr}")
        logger.debug(f"[READER-{timing_point.value.upper()}] Headers: {dict(request.headers)}")
        
        data = request.get_json()
        reader_name = data.get('reader_name', 'Unknown')
        logger.debug(f"[READER-{timing_point.value.upper()}] Reader Name: {reader_name}")
        logger.debug(f"[READER-{timing_point.value.upper()}] Raw payload: {data}")
        
        event_type = data.get('event_type')
        event_data = data.get('event_data', [])
        
        logger.info(f"[READER-{timing_point.value.upper()}] {reader_label} - event_type={event_type}, data_count={len(event_data) if isinstance(event_data, list) else 'N/A'}")
        
        # Handle different event types
        if event_type in ['tag_read', 'tag_coming']:
            # Process RFID tag scans
            logger.info(f"[READER-{timing_point.value.upper()}] Processing tag events: {len(event_data) if isinstance(event_data, list) else 0} tags")
            return handle_tag_events(event_data, timing_point)
        
        elif event_type == 'heart_beat':
            # Update heartbeat
            hub_state['heartbeat_count'] = event_data
            hub_state['last_heartbeat'] = datetime.now().isoformat()
            hub_state['device_state'] = 'OK'
            logger.debug(f"[HEARTBEAT-{timing_point.value.upper()}] Hub heartbeat #{event_data}, state: OK")
            return jsonify({"status": "ok", "heartbeat_received": True}), 200
        
        elif event_type == 'gpi_changed':
            # Update GPIO states
            if isinstance(event_data, list) and len(event_data) > 0:
                states = ''.join([str(gpi.get('state', '0')) for gpi in event_data])
                hub_state['gpi_states'] = states
                logger.info(f"[GPIO-{timing_point.value.upper()}] GPIO state changed: {states}")
            else:
                logger.warning(f"[GPIO-{timing_point.value.upper()}] Invalid GPI data: {event_data}")
            return jsonify({"status": "ok", "gpi_updated": True}), 200
        
        elif event_type == 'reader_exception':
            # Handle hub errors
            err_code = event_data.get('err_code') if isinstance(event_data, dict) else None
            err_string = event_data.get('err_string') if isinstance(event_data, dict) else str(event_data)
            hub_state['device_state'] = f"ERROR: {err_code} - {err_string}"
            logger.error(f"[HUB_ERROR-{timing_point.value.upper()}] Hub error: code={err_code}, message={err_string}")
            logger.error(f"[HUB_ERROR-{timing_point.value.upper()}] Full error data: {event_data}")
            return jsonify({"status": "error", "error_code": err_code}), 200
        
        else:
            logger.warning(f"[READER-{timing_point.value.upper()}] Unknown event type: {event_type}")
            logger.debug(f"[READER-{timing_point.value.upper()}] Unknown event data: {event_data}")
            return jsonify({"status": "unknown_event", "event_type": event_type}), 200
        
    except Exception as e:
        timing_point = get_timing_point_from_request()
        logger.error(f"[READER-{timing_point.value.upper()}] Error processing hub data: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# TAG EVENT HANDLING
# ============================================================================


def handle_tag_events(tags: List[Dict[str, Any]], timing_point: TimingPoint) -> tuple:
    """
    Process tag scan events from hub.
    
    Args:
        tags: List of tag objects from hub
        timing_point: START or END timing point
        
    Returns:
        Tuple of (JSON response, HTTP status code)
    """
    tp_label = timing_point.value.upper()
    logger.debug(f"[TAG_HANDLER-{tp_label}] Received tags data: type={type(tags)}, content={tags}")
    
    if not isinstance(tags, list) or len(tags) == 0:
        logger.warning(f"[TAG_HANDLER-{tp_label}] No valid tags to process (type: {type(tags)})")
        return jsonify({"status": "ok", "tags_processed": 0}), 200
    
    logger.info(f"[TAG_HANDLER-{tp_label}] Processing {len(tags)} tag(s)")
    processed_count = 0
    errors = []
    
    for idx, tag in enumerate(tags):
        try:
            logger.debug(f"[TAG_HANDLER-{tp_label}] Processing tag #{idx+1}: {tag}")
            
            # Extract RFID from either 'ep' or 'epc' field
            rfid = tag.get('ep') or tag.get('epc')
            
            if not rfid:
                logger.warning(f"[TAG_HANDLER-{tp_label}] Tag #{idx+1} received without ep or epc field: {tag}")
                errors.append({"error": "Missing RFID field", "tag": tag})
                continue
            
            # Extract metadata
            antenna = tag.get('at', 0)
            read_count = tag.get('rc', 1)
            signal_strength = tag.get('ri', 0)
            first_seen = tag.get('ft')
            last_seen = tag.get('lt')
            bank_data = tag.get('bd', '')
            protocol = tag.get('pt', 'EPC')
            
            logger.info(f"[TAG_HANDLER-{tp_label}] Processing RFID: {rfid} (antenna={antenna}, signal={signal_strength}, reads={read_count})")
            logger.debug(f"[TAG_HANDLER-{tp_label}] Full tag metadata: antenna={antenna}, rc={read_count}, ri={signal_strength}, ft={first_seen}, lt={last_seen}, protocol={protocol}")
            
            # Forward to backend with timing point
            forward_to_backend(
                rfid=rfid,
                timing_point=timing_point,
                antenna=antenna,
                read_count=read_count,
                signal_strength=signal_strength,
                first_seen=first_seen,
                last_seen=last_seen,
                bank_data=bank_data,
                protocol=protocol
            )
            
            processed_count += 1
            logger.debug(f"[TAG_HANDLER-{tp_label}] Tag #{idx+1} processed successfully")
            
        except Exception as e:
            logger.error(f"[TAG_HANDLER-{tp_label}] Error processing tag #{idx+1}: {e}", exc_info=True)
            errors.append({"error": str(e), "tag": tag})
    
    response = {
        "status": "ok",
        "tags_processed": processed_count,
        "tags_total": len(tags),
        "timing_point": timing_point.value
    }
    
    if errors:
        response["errors"] = errors
        logger.warning(f"[TAG_HANDLER-{tp_label}] Completed with {len(errors)} error(s)")
    
    logger.info(f"[TAG_HANDLER-{tp_label}] Processing complete: {processed_count}/{len(tags)} tags successfully processed")
    return jsonify(response), 200


# ============================================================================
# BACKEND FORWARDING
# ============================================================================


def forward_to_backend(
    rfid: str,
    timing_point: TimingPoint,
    antenna: int = 0,
    read_count: int = 1,
    signal_strength: int = 0,
    first_seen: Optional[int] = None,
    last_seen: Optional[int] = None,
    bank_data: str = '',
    protocol: str = 'EPC'
) -> None:
    """
    Forward RFID scan to unified backend server.
    
    Args:
        rfid: RFID tag ID
        timing_point: START or END timing point
        antenna: Antenna number
        read_count: Number of reads
        signal_strength: RSSI
        first_seen: First detection timestamp
        last_seen: Last detection timestamp
        bank_data: Bank data
        protocol: Protocol used
    """
    tp_label = timing_point.value.upper()
    
    try:
        # Capture current timestamp when forwarding (for accurate timing despite request queuing)
        from zoneinfo import ZoneInfo
        hit_timestamp = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        
        # Build payload with timing_point metadata
        payload = {
            "rfid": rfid,
            "timing_point": timing_point.value,  # 'start' or 'end'
            "hit_timestamp": hit_timestamp,  # Timestamp from proxy/listener
            "antenna": antenna,
            "read_count": read_count,
            "signal_strength": signal_strength,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "bank_data": bank_data,
            "protocol": protocol
        }
        
        backend_endpoint = f"{BACKEND_URL}/api/v1/rfid/hit"
        logger.debug(f"[FORWARD-{tp_label}] Forwarding to backend: {backend_endpoint}")
        logger.debug(f"[FORWARD-{tp_label}] Payload: {payload}")
        
        response = requests.post(
            backend_endpoint,
            json=payload,
            timeout=5
        )
        
        logger.debug(f"[FORWARD-{tp_label}] Backend response: status={response.status_code}, body={response.text}")
        
        if response.status_code not in [200, 201]:
            logger.warning(f"[FORWARD-{tp_label}] Backend returned {response.status_code} for {rfid}")
            logger.warning(f"[FORWARD-{tp_label}] Response body: {response.text}")
        else:
            logger.info(f"[FORWARD-{tp_label}] Successfully forwarded {rfid} to backend (status: {response.status_code})")
            
    except requests.exceptions.Timeout as e:
        logger.error(f"[FORWARD-{tp_label}] Timeout forwarding to backend: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[FORWARD-{tp_label}] Connection error to backend: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[FORWARD-{tp_label}] Request failed to backend: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[FORWARD-{tp_label}] Unexpected error forwarding to backend: {e}", exc_info=True)


# ============================================================================
# TEST ENDPOINTS
# ============================================================================


@app.route('/test', methods=['POST'])
@app.route('/test/start', methods=['POST'])
@app.route('/test/end', methods=['POST'])
def test_scan():
    """
    Test endpoint to simulate RFID hub scans.
    
    Request format:
    {
        "rfid": "TEST123456",
        "antenna": 1
    }
    """
    try:
        timing_point = get_timing_point_from_request()
        tp_label = timing_point.value.upper()
        
        data = request.get_json()
        rfid = data.get('rfid', 'TEST123456')
        antenna = data.get('antenna', 1)
        
        logger.info(f"[TEST-{tp_label}] Test scan initiated: {rfid} on antenna {antenna}")
        logger.debug(f"[TEST-{tp_label}] Test request data: {data}")
        
        # Forward test scan to backend
        logger.debug(f"[TEST-{tp_label}] Sending to backend: {BACKEND_URL}/api/v1/rfid/hit")
        response = requests.post(
            f"{BACKEND_URL}/api/v1/rfid/hit",
            json={
                "rfid": rfid,
                "timing_point": timing_point.value
            },
            timeout=5
        )
        
        logger.info(f"[TEST-{tp_label}] Backend responded with status: {response.status_code}")
        
        return jsonify({
            "test": True,
            "rfid": rfid,
            "antenna": antenna,
            "timing_point": timing_point.value,
            "backend_status": response.status_code,
            "backend_response": response.json() if response.ok else None
        }), 200
        
    except Exception as e:
        timing_point = get_timing_point_from_request()
        logger.error(f"[TEST-{timing_point.value.upper()}] Test scan failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# STARTUP AND SHUTDOWN
# ============================================================================


@app.before_request
def log_request_info():
    """Log incoming request details"""
    logger.debug(f"[REQUEST] {request.method} {request.path} from {request.remote_addr}")


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("UNIFIED RFID LISTENER - START & END LINE HUB RECEIVER")
    logger.info("="*70)
    logger.info(f"[STARTUP] Listener Port: {LISTENER_PORT}")
    logger.info(f"[STARTUP] Backend URL: {BACKEND_URL}")
    logger.info(f"[STARTUP] Debug Mode: True")
    logger.info(f"[STARTUP] Logging Level: DEBUG")
    # logger.info("[STARTUP] Reader Configuration:")
    # logger.info("  - Reader 1: Start Line RFID Hub")
    # logger.info("  - Reader 2: End Line RFID Hub")
    # logger.info("[STARTUP] Endpoints:")
    # logger.info("  - POST /reader               → Auto-detect reader (by reader_name)")
    # logger.info("  - POST /reader/start         → Start line (legacy path support)")
    # logger.info("  - POST /reader/end           → End line (legacy path support)")
    # logger.info("  - POST /test                 → Test scan (auto-detect)")
    # logger.info("  - POST /test/start           → Test scan (start line)")
    # logger.info("  - POST /test/end             → Test scan (end line)")
    # logger.info("  - GET  /health               → Overall health check")
    # logger.info("  - GET  /health/start         → Start line health check")
    # logger.info("  - GET  /health/end           → End line health check")
    # logger.info("[STARTUP] Expected Request Format:")
    # logger.info("  POST /reader")
    # logger.info("  {")
    # logger.info('    "reader_name": "Reader 1",  # or "Reader 2"')
    # logger.info('    "event_type": "tag_read",')
    # logger.info('    "event_data": [...]')
    # logger.info("  }")
    logger.info("="*70)
    
    app.run(host='0.0.0.0', port=LISTENER_PORT, debug=True)
