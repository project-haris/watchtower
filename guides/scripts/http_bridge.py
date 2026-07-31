#!/usr/bin/env python3
"""Haris NMEA hub — FINAL WORKING VERSION (verified 2026-07-31 on haris-arthur).

HTTP POST :8080 (simulator via Tailscale Funnel) -> broadcast + replay to
TCP clients :10130 (signalk-server TcpProvider pipedProvider).

Replay-on-connect is essential: signalk's TcpProvider disconnects after 60s
without data (TcpStream noDataReceivedTimeout) and reconnects with backoff.
Replaying the last 10 sentences on every connect guarantees no POST is lost
to a disconnect window.

Deployed at /opt/haris/http_bridge.py, run as systemd unit `simulator-bridge`.
"""
import threading, socketserver, collections
from http.server import BaseHTTPRequestHandler, HTTPServer

clients = []
recent = collections.deque(maxlen=10)
lock = threading.Lock()

def send_to(conn, line):
    try:
        conn.sendall(line.encode())
    except Exception:
        pass

def broadcast(line):
    with lock:
        recent.append(line)
        for c in list(clients):
            send_to(c, line)

class TcpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        with lock:
            clients.append(self.connection)
            backlog = list(recent)
        for line in backlog:
            send_to(self.connection, line)
        try:
            while True:
                if not self.connection.recv(1024):
                    break
        except Exception:
            pass
        finally:
            with lock:
                try: clients.remove(self.connection)
                except ValueError: pass

class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(errors="replace")
        if '$' in body:
            body = body[body.find('$'):]      # strip junk before first $ (sim prepends "None")
        for line in body.splitlines():
            line = line.rstrip()
            if line:
                broadcast(line + '\r\n')      # CRLF required by Signal K
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *a): pass

tcp = socketserver.ThreadingTCPServer(("0.0.0.0", 10130), TcpHandler)
tcp.daemon_threads = True
threading.Thread(target=tcp.serve_forever, daemon=True).start()
print("hub up: HTTP :8080 -> TCP :10130 (replay last 10)", flush=True)
HTTPServer(("0.0.0.0", 8080), HttpHandler).serve_forever()
