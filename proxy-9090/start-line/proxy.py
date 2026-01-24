"""
START LINE RFID Proxy Server (Port 9090)
Receives RFID scans from hardware and forwards to start-line backend

Vendor API Specification:
- Hub POSTs to /reader endpoint
- Event types: tag_read, tag_coming, heart_beat, gpi_changed, reader_exception
- Tag format: EPC (Electronic Product Code) with metadata
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configure logging with detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Backend URL
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
logger.info(f"[CONFIG] Proxy initialized with BACKEND_URL: {BACKEND_URL}")

# Hub state tracking
hub_state = {
    "heartbeat_count": 0,
    "gpi_states": "",
    "device_state": "OK",
    "last_heartbeat": None
}


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.debug("[HEALTH] Health check requested")
    return jsonify({
        "status": "ok", 
        "service": "start-line-proxy",
        "hub_state": hub_state
    }), 200


@app.route('/reader', methods=['POST'])
def receive_from_hub():
    """
    Receive data from RFID hub following vendor API specification.
    
    Vendor payload format:
    {
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
    """
    try:
        logger.debug(f"[READER] Incoming request from {request.remote_addr}")
        logger.debug(f"[READER] Headers: {dict(request.headers)}")
        
        data = request.get_json()
        logger.debug(f"[READER] Raw payload: {data}")
        
        event_type = data.get('event_type')
        event_data = data.get('event_data', [])
        
        logger.info(f"[READER] Received from hub: event_type={event_type}, data_count={len(event_data) if isinstance(event_data, list) else 'N/A'}")
        
        # Handle different event types
        if event_type in ['tag_read', 'tag_coming']:
            # Process RFID tag scans
            logger.info(f"[READER] Processing tag events: {len(event_data) if isinstance(event_data, list) else 0} tags")
            return handle_tag_events(event_data)
        
        elif event_type == 'heart_beat':
            # Update heartbeat
            hub_state['heartbeat_count'] = event_data
            hub_state['last_heartbeat'] = datetime.now().isoformat()
            hub_state['device_state'] = 'OK'
            logger.debug(f"[HEARTBEAT] Hub heartbeat #{event_data}, state: OK")
            return jsonify({"status": "ok", "heartbeat_received": True}), 200
        
        elif event_type == 'gpi_changed':
            # Update GPIO states
            if isinstance(event_data, list) and len(event_data) > 0:
                states = ''.join([str(gpi.get('state', '0')) for gpi in event_data])
                hub_state['gpi_states'] = states
                logger.info(f"[GPIO] GPIO state changed: {states}")
            else:
                logger.warning(f"[GPIO] Invalid GPI data: {event_data}")
            return jsonify({"status": "ok", "gpi_updated": True}), 200
        
        elif event_type == 'reader_exception':
            # Handle hub errors
            err_code = event_data.get('err_code') if isinstance(event_data, dict) else None
            err_string = event_data.get('err_string') if isinstance(event_data, dict) else str(event_data)
            hub_state['device_state'] = f"ERROR: {err_code} - {err_string}"
            logger.error(f"[HUB_ERROR] Hub error: code={err_code}, message={err_string}")
            logger.error(f"[HUB_ERROR] Full error data: {event_data}")
            return jsonify({"status": "error", "error_code": err_code}), 200
        
        else:
            logger.warning(f"[READER] Unknown event type: {event_type}")
            logger.debug(f"[READER] Unknown event data: {event_data}")
            return jsonify({"status": "unknown_event", "event_type": event_type}), 200
        
    except Exception as e:
        logger.error(f"[READER] Error processing hub data: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def handle_tag_events(tags):
    """
    Process tag scan events from hub.
    
    Args:
        tags: List of tag objects from hub
        
    Returns:
        JSON response
    """
    logger.debug(f"[TAG_HANDLER] Received tags data: type={type(tags)}, content={tags}")
    
    if not isinstance(tags, list) or len(tags) == 0:
        logger.warning(f"[TAG_HANDLER] No valid tags to process (type: {type(tags)})")
        return jsonify({"status": "ok", "tags_processed": 0}), 200
    
    logger.info(f"[TAG_HANDLER] Processing {len(tags)} tag(s)")
    processed_count = 0
    errors = []
    
    for idx, tag in enumerate(tags):
        try:
            logger.debug(f"[TAG_HANDLER] Processing tag #{idx+1}: {tag}")
            
            # Extract RFID from either 'ep' or 'epc' field
            rfid = tag.get('ep') or tag.get('epc')
            
            if not rfid:
                logger.warning(f"[TAG_HANDLER] Tag #{idx+1} received without ep or epc field: {tag}")
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
            
            logger.info(f"[TAG_HANDLER] Processing RFID: {rfid} (antenna={antenna}, signal={signal_strength}, reads={read_count})")
            logger.debug(f"[TAG_HANDLER] Full tag metadata: antenna={antenna}, rc={read_count}, ri={signal_strength}, ft={first_seen}, lt={last_seen}, protocol={protocol}")
            
            # Forward to backend
            forward_to_backend(
                rfid=rfid,
                antenna=antenna,
                read_count=read_count,
                signal_strength=signal_strength,
                first_seen=first_seen,
                last_seen=last_seen,
                bank_data=bank_data,
                protocol=protocol
            )
            
            processed_count += 1
            logger.debug(f"[TAG_HANDLER] Tag #{idx+1} processed successfully")
            
        except Exception as e:
            logger.error(f"[TAG_HANDLER] Error processing tag #{idx+1}: {e}", exc_info=True)
            errors.append({"error": str(e), "tag": tag})
    
    response = {
        "status": "ok",
        "tags_processed": processed_count,
        "tags_total": len(tags)
    }
    
    if errors:
        response["errors"] = errors
        logger.warning(f"[TAG_HANDLER] Completed with {len(errors)} error(s)")
    
    logger.info(f"[TAG_HANDLER] Processing complete: {processed_count}/{len(tags)} tags successfully processed")
    return jsonify(response), 200


def forward_to_backend(
    rfid,
    antenna=0,
    read_count=1,
    signal_strength=0,
    first_seen=None,
    last_seen=None,
    bank_data='',
    protocol='EPC'
):
    """
    Forward RFID scan to backend server.
    
    Args:
        rfid: RFID tag ID
        antenna: Antenna number
        read_count: Number of reads
        signal_strength: RSSI
        first_seen: First detection timestamp
        last_seen: Last detection timestamp
        bank_data: Bank data
        protocol: Protocol used
    """
    try:
        # Capture current timestamp when forwarding (for accurate timing despite request queuing)
        from zoneinfo import ZoneInfo
        hit_timestamp = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        
        payload = {
            "rfid": rfid,
            "hit_timestamp": hit_timestamp,  # Timestamp from proxy
            "antenna": antenna,
            "read_count": read_count,
            "signal_strength": signal_strength,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "bank_data": bank_data,
            "protocol": protocol
        }
        
        backend_endpoint = f"{BACKEND_URL}/rfid/hit"
        logger.debug(f"[FORWARD] Forwarding to backend: {backend_endpoint}")
        logger.debug(f"[FORWARD] Payload: {payload}")
        
        response = requests.post(
            backend_endpoint,
            json=payload,
            timeout=5
        )
        
        logger.debug(f"[FORWARD] Backend response: status={response.status_code}, body={response.text}")
        
        if response.status_code not in [200, 201]:
            logger.warning(f"[FORWARD] Backend returned {response.status_code} for {rfid}")
            logger.warning(f"[FORWARD] Response body: {response.text}")
        else:
            logger.info(f"[FORWARD] Successfully forwarded {rfid} to backend (status: {response.status_code})")
            
    except requests.exceptions.Timeout as e:
        logger.error(f"[FORWARD] Timeout forwarding to backend: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[FORWARD] Connection error to backend: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[FORWARD] Request failed to backend: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[FORWARD] Unexpected error forwarding to backend: {e}", exc_info=True)


@app.route('/test', methods=['POST'])
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
        data = request.get_json()
        rfid = data.get('rfid', 'TEST123456')
        antenna = data.get('antenna', 1)
        
        logger.info(f"[TEST] Test scan initiated: {rfid} on antenna {antenna}")
        logger.debug(f"[TEST] Test request data: {data}")
        
        # Simulate hub payload format
        hub_payload = {
            "event_type": "tag_read",
            "event_data": [
                {
                    "ep": rfid,
                    "at": antenna,
                    "rc": 1,
                    "pt": "EPC",
                    "ri": -65,
                    "ft": int(datetime.now().timestamp()),
                    "lt": int(datetime.now().timestamp())
                }
            ]
        }
        
        # Process through normal handler
        logger.debug(f"[TEST] Sending to backend: {BACKEND_URL}/rfid/hit")
        response = requests.post(
            f"{BACKEND_URL}/rfid/hit",
            json={"rfid": rfid},
            timeout=5
        )
        
        logger.info(f"[TEST] Backend responded with status: {response.status_code}")
        
        return jsonify({
            "test": True,
            "rfid": rfid,
            "antenna": antenna,
            "backend_status": response.status_code,
            "backend_response": response.json() if response.ok else None
        }), 200
        
    except Exception as e:
        logger.error(f"[TEST] Test scan failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 9090))
    logger.info("="*60)
    logger.info("START LINE RFID PROXY SERVER")
    logger.info("="*60)
    logger.info(f"[STARTUP] Port: {port}")
    logger.info(f"[STARTUP] Backend URL: {BACKEND_URL}")
    logger.info(f"[STARTUP] Debug Mode: True")
    logger.info(f"[STARTUP] Logging Level: DEBUG")
    logger.info("="*60)
    app.run(host='0.0.0.0', port=port, debug=True)
