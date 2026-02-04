Mid-line UDP listener

This small utility listens on UDP port 6000 for incoming JSON payloads from a mid-line laptop/hub (Laptop M). It normalizes the payload to the shape expected by the proxy (`/reader/mid`) and forwards via HTTP to the proxy running on Laptop E (default `http://192.168.1.10:9090/reader/mid`).

Files:
- `udp_listener.py` - The UDP server + forwarder.
- `send_test_tag.py` - Simple UDP test sender to simulate a reader.

Usage (development):

```bash
# start the UDP listener (on Laptop M)
python mid_server/udp_listener.py

# from any machine, simulate a tag to Laptop M
python mid_server/send_test_tag.py 192.168.1.11 6000
```

Environment variables:
- `PROXY_URL` - full URL of the proxy endpoint to POST to (default: `http://192.168.1.10:9090/reader/mid`).
- `BIND_HOST` - host to bind UDP to (default: `0.0.0.0`).
- `BIND_PORT` - UDP port (default: `6000`).

Notes:
- The script uses `requests` for simplicity; ensure `requests` is available in the Python runtime.
- For production packaging we will combine this with the proxy/backend and provide toggles in the GUI as requested.
