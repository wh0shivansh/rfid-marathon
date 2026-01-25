"""
Test script to simulate RFID hardware requests
Simulates the actual hardware format from tag_server.js
"""

import requests
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()

# Configuration
BASE_URL = os.getenv("RFID_LISTENER_URL", "http://localhost:9090")

def test_tag_read_start():
    """Simulate start reader tag read"""
    payload = {
        "reader_name": "Reader 1",
        "event_type": "tag_read",
        "event_data": [
            {
                "ep": "315354010100000000000013",
                "at": 1,
                "rc": 7,
                "ft": 478000,
                "lt": 479000,
                "bd": "",
                "fq": "",
                "pt": "",
                "ri": -45,
                "rv": 0
            },
            {
                "ep": "E20000123456789012345678",
                "at": 2,
                "rc": 12,
                "ft": 480000,
                "lt": 485000,
                "bd": "",
                "fq": "",
                "pt": "",
                "ri": -52,
                "rv": 0
            }
        ]
    }
    
    print("\n📡 Sending START reader data...")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{BASE_URL}/reader", json=payload)
    print(f"Response: {response.status_code}")
    print(f"Body: {response.text}")


def test_tag_read_end():
    """Simulate end reader tag read"""
    payload = {
        "reader_name": "Reader 2",
        "event_type": "tag_read",
        "event_data": [
            {
                "ep": "315354010100000000000013",
                "at": 1,
                "rc": 5,
                "ft": 500000,
                "lt": 502000,
                "bd": "",
                "fq": "",
                "pt": "",
                "ri": -48,
                "rv": 0
            }
        ]
    }
    
    print("\n📡 Sending END reader data...")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{BASE_URL}/reader", json=payload)
    print(f"Response: {response.status_code}")
    print(f"Body: {response.text}")


def test_heartbeat():
    """Simulate heartbeat"""
    payload = {
        "reader_name": "Reader 1",
        "event_type": "heart_beat",
        "event_data": 42
    }
    
    print("\n💓 Sending heartbeat...")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{BASE_URL}/reader", json=payload)
    print(f"Response: {response.status_code}")


def test_reader_exception():
    """Simulate reader exception"""
    payload = {
        "reader_name": "Reader 1",
        "event_type": "reader_exception",
        "event_data": {
            "err_code": 101,
            "err_string": "Antenna disconnected"
        }
    }
    
    print("\n⚠️ Sending reader exception...")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{BASE_URL}/reader", json=payload)
    print(f"Response: {response.status_code}")


def test_render_tags():
    """Test GET /render to retrieve accumulated tags"""
    print("\n📊 Getting accumulated tags from /render...")
    
    response = requests.get(f"{BASE_URL}/render")
    print(f"Response: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Tags collected: {len(data.get('tags', []))}")
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.text}")


def test_stats():
    """Test GET /api/v1/rfid/stats"""
    print("\n📈 Getting collector stats...")
    
    response = requests.get(f"{BASE_URL}/api/v1/rfid/stats")
    print(f"Response: {response.status_code}")
    
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    print("=" * 80)
    print("RFID Hardware Simulation Test")
    print("=" * 80)
    
    try:
        # Test tag reads
        test_tag_read_start()
        time.sleep(40)
        
        test_tag_read_end()
        time.sleep(1)
        
        # Test other events
        test_heartbeat()
        time.sleep(1)
        
        test_reader_exception()
        time.sleep(1)
        
        # Test retrieval
        test_stats()
        time.sleep(1)
        
        test_render_tags()
        
        print("\n✓ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server")
        print("Make sure the RFID listener is running on port 9090")
        print("Run: python -m flask --app rfid_listener run --host 0.0.0.0 --port 9090")
    except Exception as e:
        print(f"\n✗ Error: {e}")
