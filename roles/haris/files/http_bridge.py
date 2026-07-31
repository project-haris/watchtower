#!/usr/bin/env python3
"""Haris NMEA hub: HTTP POST :8080 (funnel / LAN) -> broadcast + replay to TCP clients :10130 (Signal K TcpProvider).

Verified 2026-07-31 on haris-arthur (signalk-server 2.30.0). See the project-haris skill:
references/simulator-http-bridge-setup.md for the full architecture and pitfalls.
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
                try:
                    clients.remove(self.connection)
                except ValueError:
                    pass


class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(errors="replace")
        if '$' in body:
            body = body[body.find('$'):]      # strip junk before first $ (simulators prepend "None")
        for line in body.splitlines():
            line = line.rstrip()
            if line:
                broadcast(line + '\r\n')      # CRLF required by Signal K
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


tcp = socketserver.ThreadingTCPServer(("0.0.0.0", 10130), TcpHandler)
tcp.daemon_threads = True
threading.Thread(target=tcp.serve_forever, daemon=True).start()
print("hub up: HTTP :8080 -> TCP :10130 (replay last 10)", flush=True)
HTTPServer(("0.0.0.0", 8080), HttpHandler).serve_forever()
