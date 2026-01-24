"""
END LINE Backend Server
Handles RFID hits at the end line - only records end times for valid running racers
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import (
    db, Race, RaceEntry,
    get_current_timestamp,
    RACE_STATUS_STARTED,
    RACER_STATUS_RUNNING, RACER_STATUS_FINISHED
)

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "end-line"}), 200


@app.route('/rfid/hit', methods=['POST'])
def rfid_hit():
    """
    Handle RFID hit at end line
    
    Logic:
    - Only process racers with state = RUNNING and start_time IS NOT NULL
    - Update end_time and set state to FINISHED
    - Skip all invalid entries silently
    """
    try:
        data = request.get_json()
        rfid = data.get('rfid')
        
        if not rfid:
            return jsonify({"error": "RFID is required"}), 400
        
        # Get the active (started) race
        race = Race.get_active_race()
        
        if not race:
            return jsonify({
                "message": "No active race found",
                "action": "skipped"
            }), 200
        
        race_id = race['race_id']
        current_time = get_current_timestamp()
        
        # Get racer entry
        entry = RaceEntry.get_by_rfid(race_id, rfid)
        
        if not entry:
            return jsonify({
                "message": "RFID not registered in this race",
                "rfid": rfid,
                "action": "skipped"
            }), 200
        
        # Validate racer state and start time
        if entry['status'] != RACER_STATUS_RUNNING:
            return jsonify({
                "message": f"Invalid racer status: {entry['status']}",
                "rfid": rfid,
                "action": "skipped"
            }), 200
        
        if entry['start_time'] is None:
            return jsonify({
                "message": "Racer has no start time",
                "rfid": rfid,
                "action": "skipped"
            }), 200
        
        # Check if already finished
        if entry['end_time'] is not None:
            return jsonify({
                "message": "Racer already finished",
                "rfid": rfid,
                "end_time": entry['end_time'].isoformat(),
                "action": "skipped"
            }), 200
        
        # Valid racer - record end time
        RaceEntry.update_end_time(race_id, rfid, current_time)
        
        # Calculate race duration
        duration_seconds = (current_time - entry['start_time']).total_seconds()
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return jsonify({
            "message": "Finish time recorded",
            "rfid": rfid,
            "start_time": entry['start_time'].isoformat(),
            "end_time": current_time.isoformat(),
            "duration": duration,
            "status": RACER_STATUS_FINISHED
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/race/active', methods=['GET'])
def get_active_race():
    """Get the currently active race"""
    try:
        race = Race.get_active_race()
        
        if not race:
            return jsonify({"message": "No active race"}), 404
        
        # Convert datetime objects to strings
        race_data = dict(race)
        if race_data.get('race_date'):
            race_data['race_date'] = str(race_data['race_date'])
        if race_data.get('created_at'):
            race_data['created_at'] = race_data['created_at'].isoformat()
        
        return jsonify(race_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/race/<int:race_id>/finished', methods=['GET'])
def get_finished_racers(race_id):
    """Get all finished racers for a race"""
    try:
        entries = RaceEntry.get_all_entries(race_id)
        
        # Filter only finished racers
        finished = [e for e in entries if e['status'] == RACER_STATUS_FINISHED]
        
        # Convert datetime objects to strings
        finished_data = []
        for entry in finished:
            entry_data = dict(entry)
            if entry_data.get('start_time'):
                entry_data['start_time'] = entry_data['start_time'].isoformat()
            if entry_data.get('end_time'):
                entry_data['end_time'] = entry_data['end_time'].isoformat()
            if entry_data.get('created_at'):
                entry_data['created_at'] = entry_data['created_at'].isoformat()
            
            # Calculate duration
            if entry['start_time'] and entry['end_time']:
                duration_seconds = (entry['end_time'] - entry['start_time']).total_seconds()
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                seconds = int(duration_seconds % 60)
                entry_data['duration'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            finished_data.append(entry_data)
        
        return jsonify(finished_data), 200
        
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
    port = int(os.getenv('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=True)
