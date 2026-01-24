"""
START LINE Backend Server
Handles race start and RFID hits at the start line with start-time correction
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import (
    db, Race, RaceEntry,
    get_current_timestamp, get_current_date, format_date, calculate_time_diff,
    RACE_STATE_IDLE, RACE_STATE_STARTED,
    RACER_STATE_GRACE, RACER_STATUS_RUNNING,
    START_TIME_CORRECTION_THRESHOLD
)

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "start-line"}), 200


@app.route('/rfid/hit', methods=['POST'])
def rfid_hit():
    """
    Handle RFID hit at start line
    
    Logic:
    - If race is IDLE: save entry in GRACE state, no start time
    - If race is STARTED:
        - New RFID: create entry with current time as start_time, state = RUNNING
        - Existing RFID: apply 10-second rule for start-time correction
    """
    try:
        data = request.get_json()
        rfid = data.get('rfid')
        
        if not rfid:
            return jsonify({"error": "RFID is required"}), 400
        
        # Get today's race
        today = format_date(get_current_date())
        race = Race.get_by_date(today)
        
        if not race:
            return jsonify({"error": "No race scheduled for today"}), 404
        
        race_id = race['race_id']
        race_status = race['status']
        current_time = get_current_timestamp()
        
        # Ensure race entries table exists
        RaceEntry.create_table(race_id)
        
        # Check if RFID already exists
        existing_entry = RaceEntry.get_by_rfid(race_id, rfid)
        
        if race_status == RACE_STATUS_IDLE:
            # Race not started - save in grace status
            if not existing_entry:
                entry_id = RaceEntry.insert(
                    race_id=race_id,
                    rfid=rfid,
                    status=RACER_STATUS_GRACE,
                    start_time=None
                )
                return jsonify({
                    "message": "RFID registered in grace period",
                    "entry_id": entry_id,
                    "rfid": rfid,
                    "state": RACER_STATE_GRACE
                }), 201
            else:
                return jsonify({
                    "message": "RFID already registered",
                    "rfid": rfid,
                    "status": existing_entry['status']
                }), 200
        
        elif race_status == RACE_STATUS_STARTED:
            # Race is running
            if not existing_entry:
                # New RFID - create entry with start time
                entry_id = RaceEntry.insert(
                    race_id=race_id,
                    rfid=rfid,
                    status=RACER_STATUS_RUNNING,
                    start_time=current_time
                )
                return jsonify({
                    "message": "New racer started",
                    "entry_id": entry_id,
                    "rfid": rfid,
                    "start_time": current_time.isoformat(),
                    "status": RACER_STATUS_RUNNING
                }), 201
            else:
                # Existing RFID - apply 10-second rule
                if existing_entry['start_time'] is None:
                    # No start time yet - set it now
                    RaceEntry.update_start_time(race_id, rfid, current_time)
                    return jsonify({
                        "message": "Start time set",
                        "rfid": rfid,
                        "start_time": current_time.isoformat(),
                        "status": RACER_STATUS_RUNNING
                    }), 200
                else:
                    # Calculate time difference from race start
                    # We need to get when the race was actually started
                    # For simplicity, we'll use the existing start_time as reference
                    time_diff = calculate_time_diff(current_time, existing_entry['start_time'])
                    
                    if time_diff > START_TIME_CORRECTION_THRESHOLD:
                        # Update start time (late start correction)
                        RaceEntry.update_start_time(race_id, rfid, current_time)
                        return jsonify({
                            "message": "Start time corrected (late start)",
                            "rfid": rfid,
                            "start_time": current_time.isoformat(),
                            "previous_start_time": existing_entry['start_time'].isoformat(),
                            "status": RACER_STATUS_RUNNING
                        }), 200
                    else:
                        # Ignore - within 10-second window
                        return jsonify({
                            "message": "Scan ignored (within 10-second window)",
                            "rfid": rfid,
                            "start_time": existing_entry['start_time'].isoformat(),
                            "status": existing_entry['status']
                        }), 200
        
        return jsonify({"error": "Invalid race state"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/race/start', methods=['POST'])
def start_race():
    """
    Start the race
    
    Logic:
    - Set race state to STARTED
    - Update all existing grace entries to RUNNING with current time
    """
    try:
        data = request.get_json()
        race_id = data.get('race_id')
        
        if not race_id:
            # Try to get today's race
            today = format_date(get_current_date())
            race = Race.get_by_date(today)
            if not race:
                return jsonify({"error": "No race found"}), 404
            race_id = race['race_id']
        
        # Get race
        race = Race.get_by_id(race_id)
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        if race['state'] == RACE_STATE_STARTED:
            return jsonify({"error": "Race already started"}), 400
        
        current_time = get_current_timestamp()
        
        # Update race state
        Race.update_state(race_id, RACE_STATE_STARTED)
        
        # Update all grace entries to running
        updated_count = RaceEntry.bulk_update_start_time(race_id, current_time)
        
        return jsonify({
            "message": "Race started successfully",
            "race_id": race_id,
            "start_time": current_time.isoformat(),
            "racers_started": updated_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/race/today', methods=['GET'])
def get_today_race():
    """Get today's race information"""
    try:
        today = format_date(get_current_date())
        race = Race.get_by_date(today)
        
        if not race:
            return jsonify({"error": "No race scheduled for today"}), 404
        
        # Convert datetime objects to strings for JSON serialization
        race_data = dict(race)
        if race_data.get('race_date'):
            race_data['race_date'] = str(race_data['race_date'])
        if race_data.get('created_at'):
            race_data['created_at'] = race_data['created_at'].isoformat()
        
        return jsonify(race_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/race/<int:race_id>/entries', methods=['GET'])
def get_race_entries(race_id):
    """Get all entries for a race"""
    try:
        entries = RaceEntry.get_all_entries(race_id)
        
        # Convert datetime objects to strings
        entries_data = []
        for entry in entries:
            entry_data = dict(entry)
            if entry_data.get('start_time'):
                entry_data['start_time'] = entry_data['start_time'].isoformat()
            if entry_data.get('end_time'):
                entry_data['end_time'] = entry_data['end_time'].isoformat()
            if entry_data.get('created_at'):
                entry_data['created_at'] = entry_data['created_at'].isoformat()
            entries_data.append(entry_data)
        
        return jsonify(entries_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Initialize database tables
    try:
        Race.create_table()
        print("✓ Database tables initialized")
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
    
    # Run server
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
