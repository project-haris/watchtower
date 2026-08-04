#!/usr/bin/env python3
"""Haris NMEA hub: HTTP POST :8080 (funnel) -> broadcast + replay to TCP clients :10130 (Signal K TcpProvider)

v2: raw stream capture — every cleaned NMEA sentence appended to /opt/haris/raw/nmea_raw.log
with an ISO timestamp. Rotates at RAW_MAX_BYTES (50 MB), keeps RAW_KEEP old files.

v3: RMC date correction — the bench simulator's GPRMC sentences embed a stale date
(2025-12-10) that Signal K refuses to promote. fix_rmc_date() rewrites the DDMMYY
field to today's UTC date and recomputes the NMEA checksum before broadcast, so the
model position always carries a fresh timestamp.
"""
import threading, socketserver, collections, os, datetime, time
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

def fix_rmc_date(line):
    """Rewrite the DDMMYY date field of RMC sentences to today's UTC date.

    RMC variants ($GPRMC/$GNRMC/$IIRMC/$AIRMC) carry their date in field index 9
    (fields[0] == '$GPRMC', fields[9] == 'DDMMYY'). The bench simulator embeds a
    stale date (2025-12-10) so Signal K never promotes the sentence. We replace
    the date with today's UTC date and RECOMPUTE the NMEA checksum (XOR of the
    chars between '$' and '*'). Non-RMC sentences pass through unchanged. The
    caller owns line endings (CRLF appended later).
    """
    try:
        if not line.startswith('$'):
            return line
        fields = line.split(',')
        if len(fields) < 10 or not fields[0].endswith('RMC'):
            return line
        fields[9] = datetime.datetime.now(datetime.timezone.utc).strftime('%d%m%y')
        body = ','.join(fields)
        star = body.find('*')
        payload = body if star < 0 else body[:star]
        ck = 0
        for ch in payload[1:]:
            ck ^= ord(ch)
        return payload + '*' + format(ck, '02X')
    except Exception:
        return line

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
            body = body[body.find('$'):]
        for line in body.splitlines():
            line = line.rstrip()
            if line:
                broadcast(fix_rmc_date(line) + '\r\n')   # CRLF required by Signal K
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
