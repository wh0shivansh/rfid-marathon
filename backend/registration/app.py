"""
REGISTRATION Backend Server
Handles race creation, racer registration, dashboard, and reporting
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import (
    db, Race, RaceEntry,
    get_current_date, format_date, parse_date, format_duration,
    RACE_STATE_IDLE, RACE_STATE_STARTED,
    RACER_STATE_GRACE, RACER_STATE_RUNNING, RACER_STATE_FINISHED
)

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "registration"}), 200


# ============= RACE MANAGEMENT =============

@app.route('/races', methods=['GET'])
def get_all_races():
    """Get all races"""
    try:
        races = Race.get_all()
        
        # Convert datetime objects to strings
        races_data = []
        for race in races:
            race_data = dict(race)
            if race_data.get('race_date'):
                race_data['race_date'] = str(race_data['race_date'])
            if race_data.get('created_at'):
                race_data['created_at'] = race_data['created_at'].isoformat()
            races_data.append(race_data)
        
        return jsonify(races_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/races', methods=['POST'])
def create_race():
    """Create a new race"""
    try:
        data = request.get_json()
        race_name = data.get('race_name')
        race_date = data.get('race_date')
        
        if not race_name or not race_date:
            return jsonify({"error": "race_name and race_date are required"}), 400
        
        # Validate date format
        try:
            parse_date(race_date)
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Create race
        race_id = Race.create(race_name, race_date)
        if race_id is None:
            return jsonify({"error": "Failed to create race"}), 500
        
        # Create entries table for this race
        RaceEntry.create_table(race_id)
        
        return jsonify({
            "message": "Race created successfully",
            "race_id": race_id,
            "race_name": race_name,
            "race_date": race_date
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/races/<int:race_id>', methods=['GET'])
def get_race(race_id):
    """Get race by ID"""
    try:
        race = Race.get_by_id(race_id)
        
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        # Convert datetime objects to strings
        race_data = dict(race)
        if race_data.get('race_date'):
            race_data['race_date'] = str(race_data['race_date'])
        if race_data.get('created_at'):
            race_data['created_at'] = race_data['created_at'].isoformat()
        
        return jsonify(race_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= RACER REGISTRATION =============

@app.route('/races/<int:race_id>/register', methods=['POST'])
def register_racer(race_id):
    """Register a racer for a race"""
    try:
        data = request.get_json()
        rfid = data.get('rfid')
        racer_name = data.get('racer_name')
        bib_number = data.get('bib_number')
        
        if not rfid or not racer_name or not bib_number:
            return jsonify({"error": "rfid, racer_name, and bib_number are required"}), 400
        
        # Check if race exists
        race = Race.get_by_id(race_id)
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        # Ensure entries table exists
        RaceEntry.create_table(race_id)
        
        # Register racer
        entry_id = RaceEntry.register_racer(race_id, rfid, racer_name, bib_number)
        
        return jsonify({
            "message": "Racer registered successfully",
            "entry_id": entry_id,
            "rfid": rfid,
            "racer_name": racer_name,
            "bib_number": bib_number
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/races/<int:race_id>/racers', methods=['GET'])
def get_race_racers(race_id):
    """Get all racers for a race"""
    try:
        # Check if race exists
        race = Race.get_by_id(race_id)
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        entries = RaceEntry.get_all_entries(race_id)
        
        # Convert datetime objects to strings and calculate durations
        entries_data = []
        for entry in entries:
            entry_data = dict(entry)
            if entry_data.get('start_time'):
                entry_data['start_time'] = entry_data['start_time'].isoformat()
            if entry_data.get('end_time'):
                entry_data['end_time'] = entry_data['end_time'].isoformat()
            if entry_data.get('created_at'):
                entry_data['created_at'] = entry_data['created_at'].isoformat()
            
            # Calculate duration
            entry_data['duration'] = format_duration(entry.get('start_time'), entry.get('end_time'))
            
            entries_data.append(entry_data)
        
        return jsonify(entries_data), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= DASHBOARD & REPORTING =============

@app.route('/races/<int:race_id>/results', methods=['GET'])
def get_race_results(race_id):
    """Get race results with rankings"""
    try:
        # Check if race exists
        race = Race.get_by_id(race_id)
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        entries = RaceEntry.get_all_entries(race_id)
        
        # Filter finished racers
        finished = [e for e in entries if e['state'] == RACER_STATE_FINISHED and e['start_time'] and e['end_time']]
        
        # Calculate durations and sort by finish time
        results = []
        for entry in finished:
            duration_seconds = (entry['end_time'] - entry['start_time']).total_seconds()
            results.append({
                'entry_id': entry['entry_id'],
                'rfid': entry['rfid'],
                'racer_name': entry['racer_name'],
                'bib_number': entry['bib_number'],
                'start_time': entry['start_time'].isoformat(),
                'end_time': entry['end_time'].isoformat(),
                'duration': format_duration(entry['start_time'], entry['end_time']),
                'duration_seconds': duration_seconds
            })
        
        # Sort by duration (fastest first)
        results.sort(key=lambda x: x['duration_seconds'])
        
        # Add rankings
        for i, result in enumerate(results, 1):
            result['rank'] = i
        
        return jsonify({
            'race_id': race_id,
            'race_name': race['race_name'],
            'race_date': str(race['race_date']),
            'race_state': race['state'],
            'total_finished': len(results),
            'results': results
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/races/<int:race_id>/stats', methods=['GET'])
def get_race_stats(race_id):
    """Get race statistics"""
    try:
        # Check if race exists
        race = Race.get_by_id(race_id)
        if not race:
            return jsonify({"error": "Race not found"}), 404
        
        entries = RaceEntry.get_all_entries(race_id)
        
        # Count by state
        stats = {
            'total_registered': len(entries),
            'grace': 0,
            'running': 0,
            'finished': 0,
            'with_name': 0,
            'without_name': 0
        }
        
        for entry in entries:
            if entry['state'] == RACER_STATE_GRACE:
                stats['grace'] += 1
            elif entry['state'] == RACER_STATE_RUNNING:
                stats['running'] += 1
            elif entry['state'] == RACER_STATE_FINISHED:
                stats['finished'] += 1
            
            if entry['racer_name']:
                stats['with_name'] += 1
            else:
                stats['without_name'] += 1
        
        return jsonify({
            'race_id': race_id,
            'race_name': race['race_name'],
            'race_date': str(race['race_date']),
            'race_state': race['state'],
            'statistics': stats
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get dashboard overview"""
    try:
        # Get today's race
        today = format_date(get_current_date())
        today_race = Race.get_by_date(today)
        
        # Get all races
        all_races = Race.get_all()
        
        dashboard = {
            'today_race': None,
            'total_races': len(all_races),
            'active_races': 0,
            'recent_races': []
        }
        
        if today_race:
            race_data = dict(today_race)
            race_data['race_date'] = str(race_data['race_date'])
            if race_data.get('created_at'):
                race_data['created_at'] = race_data['created_at'].isoformat()
            dashboard['today_race'] = race_data
        
        # Count active races
        for race in all_races:
            if race['state'] == RACE_STATE_STARTED:
                dashboard['active_races'] += 1
        
        # Get recent 5 races
        for race in all_races[:5]:
            race_data = dict(race)
            race_data['race_date'] = str(race_data['race_date'])
            if race_data.get('created_at'):
                race_data['created_at'] = race_data['created_at'].isoformat()
            dashboard['recent_races'].append(race_data)
        
        return jsonify(dashboard), 200
        
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
    port = int(os.getenv('PORT', 8003))
    app.run(host='0.0.0.0', port=port, debug=True)
