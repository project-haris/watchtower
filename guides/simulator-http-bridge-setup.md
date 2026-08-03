# Simulator → Haris HTTP Bridge — Full Working Setup

**Verified 2026-07-31 on haris-arthur** (RPi5 + MacArthur HAT, OpenPlotter, **signalk-server 2.30.0**).
This is the complete record of every config and change that got the bench simulator streaming
into the Haris M-SOC pipeline. The simulator PC needs nothing but a URL — no CAN adapter,
no tailnet membership, no firewall changes.

---

## 1. Architecture

```
simulator PC (any network)
   │  HTTP POST: raw NMEA 0183 lines
   ▼
https://haris-arthur.<tailnet>.ts.net/      ← Tailscale Funnel (public, :443)
   │
   ▼  (tailscaled local forward)
hub :8080  (/opt/haris/http_bridge.py, systemd: simulator-bridge)
   │  HTTP POST handler: strips junk before first '$', appends CRLF
   ▼
hub TCP :10130  (replay last 10 sentences on every connect)
   │
   ▼  (signalk pipedProvider "sim-tcp" — TcpProvider CLIENT dials 127.0.0.1:10130)
liner → Nmea0183ToSignalK parser → delta
   │
   ▼
Signal K model (vessels.<uuid>)
   │
   ▼
harisd (data_aggregator, polls API every 10s) → /opt/haris/logs/signalk_snapshots.jsonl
   │
   ▼
Filebeat → Logstash :5044 → Elasticsearch → Kibana
```

Key insight: **signalk-server 2.30's NMEA0183 TCP *input* is a client-side pipedProvider**
(`TcpStream` in `@signalk/streams`), not the legacy 10110 listener. The hub exists to be the
TCP server that provider dials into.

---

## 2. Tailscale Funnel setup (public HTTPS endpoint)

### 2.1 Grant the node the `funnel` attribute (one-time)

Admin Console → Access Controls → add to policy file:

```json
{
  "acls": [
    { "src": ["*"], "dst": ["*"] }
  ],
  "nodeAttrs": [
    { "target": ["100.127.13.61"], "attr": ["funnel"] }
  ]
}
```

Target by tailnet IP (hostnames are finicky). Without this, `tailscale funnel` prints
"Funnel is enabled, but the list of allowed nodes in the tailnet policy file does not
include the one you are using" and the config does not persist.

### 2.2 Issue the HTTPS certificate (one-time, kills SSL_ERROR_SYSCALL)

```bash
sudo tailscale cert haris-arthur.tailb05740.ts.net
```

### 2.3 Enable Funnel — MUST use `--bg`

```bash
sudo tailscale funnel --bg 8080
sudo tailscale funnel status
```

- `--bg` writes the serve config into tailscaled so it survives. The foreground form
  (`tailscale funnel 8080`) tears the config down on Ctrl+C — that's a guaranteed
  "No serve config" loop.
- Expected status:
  ```
  # Funnel on:
  https://haris-arthur.tailb05740.ts.net (Funnel on)
  |-- / proxy http://127.0.0.1:8080
  ```
- Teardown: `sudo tailscale funnel reset` (URL stops working; ACL + cert remain,
  so reopening is instant).

---

## 3. Hub (HTTP :8080 → TCP :10130)

Script: `references/simulator-http-bridge.py` in this skill. Deployed at
`/opt/haris/http_bridge.py`.

```bash
sudo tee /opt/haris/http_bridge.py > /dev/null <<'EOF'
#!/usr/bin/env python3
"""Haris NMEA hub: HTTP POST :8080 (funnel) -> broadcast + replay to TCP clients :10130 (Signal K TcpProvider)"""
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
EOF
```

### 3.1 systemd unit (survives reboot)

```bash
sudo tee /etc/systemd/system/simulator-bridge.service > /dev/null <<'EOF'
[Unit]
Description=Haris Simulator HTTP Bridge (NMEA 0183 -> Signal K)
After=network-online.target signalk.service
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/haris/http_bridge.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now simulator-bridge
systemctl is-active simulator-bridge   # → active
ss -tlnp | grep -E "8080|10130"        # → both LISTEN
```

---

## 4. Signal K pipedProvider (the input mechanism)

Edit `/home/pi/.signalk/settings.json` (OpenPlotter default user `pi`; signalk runs as root on
haris-arthur, but the file lives under pi's home). Append to `pipedProviders`:

```json
{
  "enabled": true,
  "id": "sim-tcp",
  "pipeElements": [
    {
      "type": "providers/simple",
      "options": {
        "logging": false,
        "type": "NMEA0183",
        "subOptions": {
          "type": "tcp",
          "host": "127.0.0.1",
          "port": 10130,
          "suppress0183event": true
        }
      }
    }
  ]
}
```

Apply with python (safe JSON edit) then restart:

```bash
sudo python3 - <<'EOF'
import json
p = "/home/pi/.signalk/settings.json"
d = json.load(open(p))
d["pipedProviders"].append({
    "enabled": True,
    "id": "sim-tcp",
    "pipeElements": [{
        "type": "providers/simple",
        "options": {
            "logging": False,
            "type": "NMEA0183",
            "subOptions": {
                "type": "tcp",
                "host": "127.0.0.1",
                "port": 10130,
                "suppress0183event": True
            }
        }
    }]
})
json.dump(d, open(p, "w"), indent=4)
EOF

sudo systemctl restart signalk
sleep 15
ss -tnp | grep 10130   # expect ESTAB (provider connected to hub)
```

`suppress0183event: true` is **required** — it stops the wrapper from emitting the raw
sentence to `app.emit('nmea0183')`, which otherwise can abort before the delta is pushed.

---

## 5. Firewall

- **Tailnet path**: nothing needed — Funnel traffic arrives via tailscaled's outbound
  connection; the local hops (:8080, :10130) are loopback, which firewalld doesn't block.
- **LAN fallback** (simulator on same Wi-Fi, no Funnel): open the bridge port:
  ```bash
  sudo firewall-cmd --permanent --add-port=8080/tcp && sudo firewall-cmd --reload
  ```
  Point the simulator at `http://<pi-lan-ip>:8080/`.
- Manual firewall-cmd changes are wiped on re-provision — add to watchtower host vars if
  you need them permanently.

---

## 6. Verification

### 6.1 Transport
```bash
ss -tlnp | grep -E "8080|10130"     # both LISTEN
ss -tnp | grep 10130                # ESTAB = provider connected
sudo tailscale funnel status        # proxy line present
```

### 6.2 End-to-end POST through the public URL (None prefix + RMC on purpose)
```bash
curl -X POST -d 'None$IIRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,310726,003.1,W*73' \
  https://haris-arthur.tailb05740.ts.net/
# → ok
```

### 6.3 Model — correct path for 2.30 (vessels/self and v2 API both 404 in this build)
```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/ | jq \
  '.vessels[(.self | sub("vessels\\."; ""))] | .navigation, .environment'
```

### 6.4 harisd snapshots
```bash
sudo tail -f /opt/haris/logs/signalk_snapshots.jsonl
# expect signalk.navigation / signalk.environment populated, fresh @timestamp
```

### 6.5 ELK arrival (on haris-citadel)
```bash
curl -sk -u elastic:<pw> "https://127.0.0.1:9200/haris-signalk-*/_search?q=vessel_id:VESSEL-ARTHUR&size=1&sort=@timestamp:desc"
# expect signalk.navigation.headingTrue.value etc. flattened, $source sim-tcp.*
```

---

## 7. Pitfalls — every one cost real time (do not re-litigate)

| Symptom | Root cause | Fix |
|---|---|---|
| `candump`/10110 receives but model empty | **Port 10110 is orphaned in 2.30** — `dist/interfaces/nmea-tcp.js` binds and emits `tcpserver0183data`, but nothing in dist consumes that event | Don't use 10110 for input; use the pipedProvider client (section 4) |
| `TcpProvider:connect ECONNREFUSED` | The provider is a **client**; it dials host:port. Nothing was listening | Run the hub (section 3) |
| Provider connects then drops; data missed | `TcpStream` has a **60s no-data idle timeout** + reconnect backoff | Hub replays last 10 sentences on every connect |
| POST returns `ok` but model empty | Simulator prepends literal **`None`** to every sentence (`None$HETHS,...` — a Python str(None) concat on their side) | Hub strips everything before the first `$` |
| Model empty even with clean sentences | **No CRLF** — Signal K line-buffers; unterminated lines discarded on close | Hub appends `\r\n` |
| Bad checksum → silent drop | NMEA checksum validation | Verify with python XOR; fix the sentence |
| Delta parsed but never lands | `app.emit('nmea0183')` path in the wrapper can abort before push | `suppress0183event: true` |
| System clock reset to `2019-09-13 06:00:00` every ~60s; Zabbix "clock out of sync"; chrony Stratum 0 with all sources `^?` | **`@signalk/set-system-time` plugin enabled** — reads time from Signal K data and runs `sudo date -u -s '<value>'` every `interval` s (default 60). On the bench the value is the **simulator's hardcoded GPS date**, so it fights chrony: plugin sets 2019 → chrony rejects 7-year offset (`maxupdateskew 100.0`) → no sync. RTC stays correct, making it look like a boot/RTC problem | Disable the plugin: edit `/home/pi/.signalk/plugin-config-data/set-system-time.json` → `"enabled": false`, then `sudo systemctl restart signalk` (the running plugin keeps firing until restart — config file change alone is not enough). Restore clock with `sudo hwclock --hctosys` (RTC is correct). `pi ALL=(ALL) NOPASSWD: ALL` (OpenPlotter default) is what lets the JS plugin run `sudo date` unchecked. Keep the plugin disabled whenever the simulator feeds fake time; it is only legit with a real GPS |
| `tailscale funnel` shows "Success" then `No serve config` | Foreground mode; Ctrl+C tears it down | `--bg` |
| `SSL_ERROR_SYSCALL` on public URL | Cert not provisioned yet | `sudo tailscale cert <url>` once |
| `.navigation` null in API root | Wrong path — data lives at `.vessels[<uuid>]`; `.self` has a `vessels.` prefix | jq with `sub("vessels\\."; "")` |
| Vessel UUID changes on restart | signalk regenerates self id | Never hardcode; resolve `.self` at runtime; downstream keys on `vessel_id` env |

Checksum checker for any sentence:
```bash
python3 -c "s='IIRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,310726,003.1,W';print(hex(__import__('functools').reduce(lambda a,b:a^ord(b),s,0)).upper()[2:])"
```

---

## 8. Teardown / reopen

```bash
# teardown
sudo tailscale funnel reset
sudo systemctl stop simulator-bridge

# reopen (simulator config unchanged — same URL)
sudo systemctl start simulator-bridge
sudo tailscale funnel --bg 8080
sudo tailscale funnel status
```

Funnel's ACL grant and cert persist, so reopen is instant. The hub replays recent sentences
to the provider on reconnect, so no POST is lost.

---

## 9. Security note

The Funnel URL is **world-public** — anyone who finds it can inject fake vessel data into
the Signal K / M-SOC pipeline. Bench-only. Options when kept open: shared-secret header
check in the hub, or `funnel reset` when not in use.
