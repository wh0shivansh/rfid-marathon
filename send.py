import socket,json
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
msg = json.dumps({
        "rfid": "E2000016591702080740B3D1",
        "reader_id": "Reader 2",
        "timestamp": "2024-06-10T12:34:56Z",
        "timing_point": "mid",
        "antenna": "1",
        "read_count": "24",
        "signal_strength": "-55",
        "first_seen": "24000",
        "last_seen": "24000"
    })
# s.sendto(msg.encode(),("192.168.1.11",6000))
s.sendto(msg.encode(),("127.0.0.1",6000))