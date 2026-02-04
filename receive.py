import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 9091))
print("Listening...")
while True:
    data, addr = s.recvfrom(4096)
    print("From", addr, json.loads(data))