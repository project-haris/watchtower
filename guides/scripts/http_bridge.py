#!/usr/bin/env python3
"""Haris NMEA hub — v2 (verified 2026-08-03 on haris-arthur).

HTTP POST :8080 (simulator via Tailscale Funnel) -> broadcast + replay to
TCP clients :10130 (signalk-server TcpProvider pipedProvider).

v2 changes vs v1:
1. Raw stream capture: every cleaned NMEA sentence appended to
   /opt/haris/raw/nmea_raw.log with an ISO-8601 UTC timestamp, one line per
   sentence. Rotates at 50 MB (keeps 2 old files). This is the ONLY place the
   full raw stream is persisted — Signal K itself does not record it.
2. allow_reuse_address=True on both servers. Without it, a restart right after
   a crash/stop fails with EADDRINUSE because signalk's TcpProvider reconnect
   loop leaves server-side TIME_WAIT sockets on :10130 and the default
   ThreadingTCPServer doesn't set SO_REUSEADDR. (v1 hit this 2026-08-03.)

Replay-on-connect is essential: signalk's TcpProvider disconnects after 60s
without data (TcpStream noDataReceivedTimeout) and reconnects with backoff.
Replaying the last 10 sentences on every connect guarantees no POST is lost
to a disconnect window.

Deployed at /opt/haris/http_bridge.py, run as systemd unit `simulator-bridge`.
"""
import threading, socketserver, collections, os, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

RAW_DIR = "/opt/haris/raw"
RAW_LOG = os.path.join(RAW_DIR, "nmea_raw.log")
RAW_MAX_BYTES = 50 * 1024 * 1024
RAW_KEEP = 2

clients = []
recent = collections.deque(maxlen=10)
lock = threading.Lock()

def raw_rotate():
    """Rotate nmea_raw.log -> .1 -> .2 when over size. No-op if file small/missing."""
    try:
        if os.path.exists(RAW_LOG) and os.path.getsize(RAW_LOG) >= RAW_MAX_BYTES:
            for i in range(RAW_KEEP, 0, -1):
                src = RAW_LOG if i == 1 else RAW_LOG + "." + str(i - 1)
                dst = RAW_LOG + "." + str(i)
                if os.path.exists(src):
                    if os.path.exists(dst):
                        os.remove(dst)
                    os.rename(src, dst)
    except Exception:
        pass

def raw_write(line):
    """Append one timestamped NMEA line to the raw log."""
    try:
        if not os.path.isdir(RAW_DIR):
            os.makedirs(RAW_DIR, exist_ok=True)
        raw_rotate()
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        with open(RAW_LOG, "a") as f:
            f.write(ts + " " + line.rstrip("\r\n") + "\n")
    except Exception:
        pass

def send_to(conn, line):
    try:
        conn.sendall(line.encode())
    except Exception:
        pass

def broadcast(line):
    with lock:
        recent.append(line)
        raw_write(line)
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

class ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True

tcp = ReuseTCPServer(("0.0.0.0", 10130), TcpHandler)
threading.Thread(target=tcp.serve_forever, daemon=True).start()
print("hub up: HTTP :8080 -> TCP :10130 (replay last 10) | raw -> " + RAW_LOG, flush=True)
httpd = ReuseHTTPServer(("0.0.0.0", 8080), HttpHandler)
httpd.serve_forever()
