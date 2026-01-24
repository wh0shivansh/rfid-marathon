"""
Integration test script for the RFID Marathon System
Tests the complete flow from race creation to finish line
"""
import requests
import time
from datetime import datetime, timedelta

# Backend URLs
REGISTRATION_URL = "http://localhost:8003"
START_LINE_URL = "http://localhost:8000"
END_LINE_URL = "http://localhost:8002"
START_PROXY_URL = "http://localhost:9090"
END_PROXY_URL = "http://localhost:9090"


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_health_checks():
    """Test that all services are running"""
    print_section("HEALTH CHECKS")
    
    services = {
        "Registration Backend": f"{REGISTRATION_URL}/health",
        "Start Line Backend": f"{START_LINE_URL}/health",
        "End Line Backend": f"{END_LINE_URL}/health",
        "Start Line Proxy": f"{START_PROXY_URL}/health",
        "End Line Proxy": f"{END_PROXY_URL}/health",
    }
    
    all_healthy = True
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✓ {name}: OK")
            else:
                print(f"✗ {name}: FAILED (Status {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"✗ {name}: UNREACHABLE ({e})")
            all_healthy = False
    
    return all_healthy


def test_create_race():
    """Create a test race"""
    print_section("CREATE RACE")
    
    today = datetime.now().strftime("%Y-%m-%d")
    race_data = {
        "race_name": f"Test Marathon {datetime.now().strftime('%H:%M:%S')}",
        "race_date": today
    }
    
    response = requests.post(f"{REGISTRATION_URL}/races", json=race_data)
    print(f"POST /races: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        print(f"✓ Race created: ID={result['race_id']}, Name={result['race_name']}")
        return result['race_id']
    else:
        print(f"✗ Failed to create race: {response.text}")
        return None


def test_register_racers(race_id):
    """Register test racers"""
    print_section("REGISTER RACERS")
    
    racers = [
        {"rfid": "RFID001", "racer_name": "Alice Johnson", "bib_number": "101"},
        {"rfid": "RFID002", "racer_name": "Bob Smith", "bib_number": "102"},
        {"rfid": "RFID003", "racer_name": "Charlie Brown", "bib_number": "103"},
    ]
    
    registered = []
    for racer in racers:
        response = requests.post(
            f"{REGISTRATION_URL}/races/{race_id}/register",
            json=racer
        )
        if response.status_code == 201:
            print(f"✓ Registered: {racer['racer_name']} (RFID: {racer['rfid']})")
            registered.append(racer['rfid'])
        else:
            print(f"✗ Failed to register {racer['racer_name']}: {response.text}")
    
    return registered


def test_pre_race_scans(rfids):
    """Test RFID scans before race starts (grace period)"""
    print_section("PRE-RACE SCANS (Grace Period)")
    
    for rfid in rfids:
        response = requests.post(
            f"{START_PROXY_URL}/rfid/scan",
            json={"rfid": rfid}
        )
        if response.status_code == 201:
            result = response.json()
            print(f"✓ {rfid}: {result['backend_response']['message']}")
        else:
            print(f"✗ {rfid}: Failed")
    
    print("\n⏸  Racers are in GRACE state (no start times yet)")


def test_start_race(race_id):
    """Start the race"""
    print_section("START RACE")
    
    response = requests.post(
        f"{START_LINE_URL}/race/start",
        json={"race_id": race_id}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Race started!")
        print(f"  Start time: {result['start_time']}")
        print(f"  Racers started: {result['racers_started']}")
        return result['start_time']
    else:
        print(f"✗ Failed to start race: {response.text}")
        return None


def test_late_arrival():
    """Test a late arrival (new racer after race started)"""
    print_section("LATE ARRIVAL")
    
    late_racer = {"rfid": "RFID999"}
    response = requests.post(
        f"{START_PROXY_URL}/rfid/scan",
        json=late_racer
    )
    
    if response.status_code == 201:
        result = response.json()
        print(f"✓ Late arrival recorded: {result['backend_response']['message']}")
    else:
        print(f"✗ Failed: {response.text}")


def test_start_time_correction():
    """Test the 10-second rule for start time correction"""
    print_section("START TIME CORRECTION (10-second rule)")
    
    test_rfid = "RFID001"
    
    # First scan (within 10 seconds - should be ignored)
    print(f"\n1️⃣  Scanning {test_rfid} immediately (within 10s)...")
    response = requests.post(
        f"{START_PROXY_URL}/rfid/scan",
        json={"rfid": test_rfid}
    )
    if response.status_code == 200:
        result = response.json()
        print(f"   {result['backend_response']['message']}")
    
    # Wait 2 seconds
    print("\n⏱  Waiting 2 seconds...")
    time.sleep(2)
    
    # Second scan (still within 10 seconds - should be ignored)
    print(f"\n2️⃣  Scanning {test_rfid} again (still within 10s)...")
    response = requests.post(
        f"{START_PROXY_URL}/rfid/scan",
        json={"rfid": test_rfid}
    )
    if response.status_code == 200:
        result = response.json()
        print(f"   {result['backend_response']['message']}")


def test_finish_line(rfids):
    """Test finish line scans"""
    print_section("FINISH LINE SCANS")
    
    print("⏱  Simulating racers finishing (waiting 3 seconds between each)...\n")
    
    for i, rfid in enumerate(rfids, 1):
        time.sleep(3)  # Simulate race time
        
        response = requests.post(
            f"{END_PROXY_URL}/rfid/scan",
            json={"rfid": rfid}
        )
        
        if response.status_code == 200:
            result = response.json()
            backend_resp = result['backend_response']
            if 'duration' in backend_resp:
                print(f"✓ {rfid}: FINISHED in {backend_resp['duration']}")
            else:
                print(f"⚠ {rfid}: {backend_resp['message']}")
        else:
            print(f"✗ {rfid}: Failed")


def test_invalid_finish():
    """Test finish line with invalid racer (no start time)"""
    print_section("INVALID FINISH (No Start Time)")
    
    # Create a racer that was never started
    invalid_rfid = "RFID888"
    response = requests.post(
        f"{END_PROXY_URL}/rfid/scan",
        json={"rfid": invalid_rfid}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Correctly handled: {result['backend_response']['message']}")
    else:
        print(f"✗ Unexpected response: {response.text}")


def test_results(race_id):
    """Get race results"""
    print_section("RACE RESULTS")
    
    response = requests.get(f"{REGISTRATION_URL}/races/{race_id}/results")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n🏁 {result['race_name']} - {result['race_date']}")
        print(f"   Total Finished: {result['total_finished']}\n")
        
        print(f"{'Rank':<6} {'Name':<20} {'Bib':<8} {'Duration':<12}")
        print("-" * 50)
        
        for racer in result['results']:
            print(f"{racer['rank']:<6} {racer['racer_name'] or 'N/A':<20} "
                  f"{racer['bib_number'] or 'N/A':<8} {racer['duration']:<12}")
    else:
        print(f"✗ Failed to get results: {response.text}")


def test_statistics(race_id):
    """Get race statistics"""
    print_section("RACE STATISTICS")
    
    response = requests.get(f"{REGISTRATION_URL}/races/{race_id}/stats")
    
    if response.status_code == 200:
        result = response.json()
        stats = result['statistics']
        
        print(f"\n📊 {result['race_name']}")
        print(f"   State: {result['race_state']}")
        print(f"\n   Total Registered: {stats['total_registered']}")
        print(f"   In Grace: {stats['grace']}")
        print(f"   Running: {stats['running']}")
        print(f"   Finished: {stats['finished']}")
        print(f"   With Name: {stats['with_name']}")
        print(f"   Without Name: {stats['without_name']}")
    else:
        print(f"✗ Failed to get statistics: {response.text}")


def run_full_test():
    """Run the complete test suite"""
    print("\n" + "=" * 60)
    print("  🏃 RFID MARATHON SYSTEM - INTEGRATION TEST")
    print("=" * 60)
    
    # Health checks
    if not test_health_checks():
        print("\n❌ Some services are not running. Please start all services first.")
        return
    
    # Create race
    race_id = test_create_race()
    if not race_id:
        print("\n❌ Failed to create race. Aborting tests.")
        return
    
    # Register racers
    rfids = test_register_racers(race_id)
    if not rfids:
        print("\n❌ Failed to register racers. Aborting tests.")
        return
    
    # Pre-race scans
    test_pre_race_scans(rfids)
    
    # Start race
    start_time = test_start_race(race_id)
    if not start_time:
        print("\n❌ Failed to start race. Aborting tests.")
        return
    
    # Late arrival
    test_late_arrival()
    
    # Start time correction
    test_start_time_correction()
    
    # Finish line
    test_finish_line(rfids)
    
    # Invalid finish
    test_invalid_finish()
    
    # Results
    test_results(race_id)
    
    # Statistics
    test_statistics(race_id)
    
    print("\n" + "=" * 60)
    print("  ✅ ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == '__main__':
    try:
        run_full_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
