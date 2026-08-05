# Simulator Connection Checklist — haris-arthur (McArthur HAT)

Checklist for connecting haris-arthur to an NMEA 2000 simulator via CAN-H and CAN-L wires.

---

## Pre-Meeting (do before leaving)

### 1. Signal K CAN native module working
```bash
journalctl -u signalk --no-pager | grep "canSocket\|canboat"
# Expect: native module loaded, address claimed (100)
```

### 2. Signal K running and CAN provider enabled
```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self
# Expect: returns JSON with uuid
```

### 3. CAN interface up
```bash
ip -details link show can0 | grep -E "UP|ERROR"
# Expect: UP, ERROR-ACTIVE (not ERROR-PASSIVE)
```

### 4. OpenPlotter CAN Bus app
- Open → MCP251xfd tab → confirm device listed → toggle Add Connection to Signal K if not already green

### 5. Pack
- Raspberry Pi 5 + McArthur HAT + USB-C power supply
- Ethernet cable or Wi-Fi dongle (Tailscale may not route at venue)
- Micro-HDMI cable + monitor (just in case)
- Small flathead screwdriver (for McArthur screw terminals)
- Multimeter (continuity/voltage checks)

---

## On-Site — Physical Connection

### 1. Ask simulator team for wire color mapping

Standard NMEA 2000 colors (verify with their documentation):
| Signal | Standard Color |
|--------|---------------|
| CAN-H  | White         |
| CAN-L  | Blue          |
| V+ (12V) | Red        |
| V- (GND) | Black       |

**Different brands use different colors** — always confirm before connecting.

### 2. Wire CAN-H and CAN-L to McArthur screw terminals

- Locate the NMEA 2000 screw terminal block on the McArthur HAT
- Connect **CAN-H** → terminal marked CAN-H (or CH)
- Connect **CAN-L** → terminal marked CAN-L (or CL)
- If the simulator provides 12V, V+ and V- can be connected for network power — otherwise the RPi can run on its own USB-C supply. Both should share the same ground if possible.

### 3. Termination check

- If haris-arthur is at the **end of the NMEA 2000 line** → close the **N2K TERM** jumper on the McArthur HAT (adds 120Ω)
- If the simulator already terminates both ends → leave jumper **open**
- When in doubt, start with jumper **closed** (haris-arthur as end node)

Multimeter test with power off:
- **60Ω** between CAN-H and CAN-L = both terminators present ✅
- **120Ω** between CAN-H and CAN-L = only one terminator present
- **< 40Ω** = short circuit or damaged port ❌

### 4. Power on

Power the simulator first, then haris-arthur (or both simultaneously).

---

## Verification Flow

### 1. Hardware — CAN state
```bash
ip -details link show can0
# Expect: UP, ERROR-ACTIVE, bitrate 250000
```

### 2. CAN frame traffic
```bash
sudo timeout 10 candump can0
# Expect: CAN frames scrolling (PGN hex IDs)
```

> **Pitfall (candump `-L`)**: to log frames to a file use `candump can0 -L >> file.log` (append). On this can-utils build `-L` means "log file format on **stdout**" and takes NO file argument — `candump can0 -L /path` fails with *"name of CAN device '...' is too long"*. Lowercase `-l` auto-names a file in the CWD. Production capture runs as the `haris-canraw` service — see `references/raw-data-preservation.md`.

### 3. Signal K — address claim
```bash
journalctl -u signalk --no-pager | grep -i "claimed\|address\|canboat"
# Expect: "Claimed address XXX"
```

### 4. Signal K — data paths
```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq '.navigation, .environment, .electrical'
# Expect: populated paths (position, COG, SOG, depth, wind...)
```

### 5. OpenPlotter dashboard
Browser → `http://haris-arthur:3000` → Dashboard or Web Apps → live gauges updating.

### 6. Haris data collector
```bash
systemctl status harisd --no-pager
sudo tail -f /opt/haris/logs/signalk_snapshots.jsonl
# Expect: new JSONL lines every N seconds with populated vessel data
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `candump` shows nothing | CAN-H/L swapped | Swap the two wires |
| `ERROR-PASSIVE`, tx counter rising | No termination or no ACK | Close N2K TERM jumper, confirm other end terminated |
| `BUS-OFF` | Short circuit | Check CAN-H/L for continuity, no shorts to V+/V- |
| Signal K shows no data | CAN connection not toggled | OpenPlotter CAN Bus → toggle Add Connection to Signal K |
| canboatjs native module error | Build deps missing | `cd /usr/lib/node_modules/signalk-server/node_modules/@canboat/canboatjs && sudo npm rebuild` |
| `navigation` null but candump has frames | Signal K plugin misconfig | Server → Connections → confirm NMEA 2000 on can0 enabled |

---

## Simulator Without CAN Hardware — HTTP Bridge (NMEA 0183 over URL)

Use when the simulator cannot do CAN but can POST raw NMEA 0183 text lines to a URL.

1. Bridge script on the Pi (`/opt/haris/http_bridge.py`, see `references/simulator-http-bridge.py`): accepts HTTP POST, forwards body verbatim to Signal K NMEA 0183 TCP input at 127.0.0.1:10110.
2. Verify Signal K TCP input is listening: `ss -tlnp | grep 10110` (enable in Signal K server settings if absent).
3. Run the bridge: `sudo python3 /opt/haris/http_bridge.py` (or install as systemd service for persistence).
4. Point the simulator at `http://<pi-ip>:8080/`.
5. Verify end-to-end: inject `echo '$IIRMC,...' | nc 127.0.0.1 10110`, then `curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq '.navigation.position'` → expect populated lat/lon.

Pitfalls (all hit in the field):
- **Clock stuck at 2019-09-13 06:00 / chrony never syncs (bench sim)**: `@signalk/set-system-time` plugin (enabled by default with `interval: 60, sudo: true`) reads time from Signal K data and runs `sudo date -u -s '<value>'` every 60s. With the simulator feeding a hardcoded GPS date, it resets the system clock to 2019 every minute; chrony rejects the 7-year offset (`maxupdateskew 100.0`) so all NTP sources go `^?` and Stratum stays 0. RTC remains correct, so it masquerades as a boot/RTC fault. Fix: `"enabled": false` in `/home/pi/.signalk/plugin-config-data/set-system-time.json` + `sudo systemctl restart signalk` (restart required — config change alone doesn't stop the running plugin) + `sudo hwclock --hctosys` to restore the clock. Zabbix then clears its time-sync alert on next poll. Only legit with a real GPS source.
- **Checksums**: test sentences MUST have valid NMEA checksums — Signal K silently drops bad ones, leaving `.navigation.position` null. Verify any sentence with:
  `python3 -c "s='...';print(hex(__import__('functools').reduce(lambda a,b:a^ord(b),s,0)).upper()[2:])"`
- **Stale dates**: RMC with an old date (e.g. 1994) may be dropped; use a current DDMMYY.
- **Debian has no `nc` package** — install `netcat-openbsd`, or use bash TCP: `echo '...' > /dev/tcp/127.0.0.1/10110`.
- **Firewall**: watchtower firewalld role is fail-closed drop on wlan0 (no ports open). Traffic over Tailscale (tailscale0) bypasses the drop zone — a simulator PC on the tailnet works with zero firewall changes. Non-tailnet clients need `sudo firewall-cmd --permanent --add-port=8080/tcp` (bridge) or `--add-port=10110/tcp` (direct Signal K input) + `--reload`.
- **Persistence**: manual `firewall-cmd` changes and ad-hoc bridge runs don't survive re-provision/reboot — add ports to watchtower host vars and install the bridge as a systemd unit.

## FINAL WORKING PIPELINE — signalk-server 2.30, simulator POSTs NMEA to a URL (verified 2026-07-31)

Architecture that works on haris-arthur (signalk-server 2.30.0, OpenPlotter):

```
simulator PC → https://haris-arthur.<tailnet>.ts.net/ (Tailscale Funnel :443)
  → hub HTTP :8080 (/opt/haris/http_bridge.py, systemd unit simulator-bridge)
  → hub TCP :10130 (replay last 10 sentences on connect)
  → signalk pipedProvider "sim-tcp" (TcpProvider CLIENT → 127.0.0.1:10130)
  → liner → Nmea0183ToSignalK parser → delta → model
```

Signal K provider config (in /home/pi/.signalk/settings.json, pipedProviders):

```json
{
  "enabled": true,
  "id": "sim-tcp",
  "pipeElements": [{
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
  }]
}
```

Reading the model (this build has NO working /signalk/v1/api/vessels/self and NO v2 API — both 404):
```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/ | jq '.vessels[(.self | sub("vessels\\."; ""))] | .navigation, .environment'
```

Debugging findings that cost hours — do not re-litigate:
- **Port 10110 is an orphan in 2.30.** The legacy nmea-tcp interface (dist/interfaces/nmea-tcp.js) binds 10110 and emits `tcpserver0183data`, but NOTHING in dist consumes that event. Sentences sent there are accepted and silently dropped. Don't use it.
- **`providers/simple` + `subOptions.type: "tcp"` makes Signal K a TCP CLIENT** (TcpStream in @signalk/streams). It connects OUT to host:port and reads. It is not a listener. It also has a 60s no-data idle timeout and reconnects with backoff — hence the hub's replay-on-connect.
- **`subOptions.dataType` vs `options.type`**: the factory reads the parser from `subOptions.dataType ?? options.type` and the transport from `options.type` (pipeStartByType). The GPS-serial config shape (options.type="NMEA0183" + subOptions.type="serial") also works — NMEA0183 is a valid pipeStart type that dispatches on subOptions.type.
- **`suppress0183event: true`** on subOptions is required so the wrapper skips `app.emit('nmea0183')` — without it, in some paths the sentence-event emission can abort before the delta is pushed.
- **Simulator "None" prefix**: the bench simulator prepends a literal `None` to each sentence (`None$HETHS,...`) — a Python str(None) concat on their side. The hub strips everything before the first `$`.
- **CRLF required**: Signal K's NMEA input line-buffers; sentences without `\r\n` get discarded on connection close.
- **Checksum validation**: bad checksums = silent drops. Verify with python functools.reduce XOR.
- **Self UUID changes on every signalk restart** — never hardcode the vessel uuid; always resolve via `.self` key (strip the `vessels.` prefix).

### Exposing the bridge publicly — Tailscale Funnel (when simulator PC is NOT on the tailnet)

Verified 2026-07-31 on haris-arthur. Exposes localhost:8080 to the public internet via `https://<machine>.<tailnet>.ts.net/`, works behind NAT (needs only outbound internet). Simulator PC needs no Tailscale at all.

```bash
sudo tailscale funnel 8080          # serve local :8080 publicly
sudo tailscale funnel status        # show public URL + target
sudo tailscale funnel reset         # tear down when done
```

Verification chain:
1. Bridge must be running: `ss -tlnp | grep 8080`, else `sudo python3 /opt/haris/http_bridge.py`
2. From any off-tailnet machine: `curl -X POST -d '$IIRMC,...' https://haris-arthur.<tailnet>.ts.net/` → expect `ok`
3. On the Pi: `curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq '.navigation.position'` → expect populated lat/lon
4. First run may take a minute to provision the HTTPS cert — re-check `tailscale funnel status` if it times out.

Security: the Funnel URL is world-public — anyone who finds it can inject fake NMEA into the Signal K pipeline. Bench-only; tear down with `funnel reset` when not in use, or add a shared-secret header check to the bridge.

## End of Session — Save Sample Data
```bash
sudo timeout 30 candump can0 > ~/simulator-candump-$(date +%Y%m%d_%H%M).log
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq > ~/simulator-signalk-$(date +%Y%m%d_%H%M).json
```

## References

- McArthur HAT NMEA 2000 docs: https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea2000.html
- McArthur HAT pinout diagram: https://raw.githubusercontent.com/OpenMarine/MacArthur-HAT/main/images/macarthur-diagram.png
- OpenPlotter CAN Bus manual: https://openplotter.readthedocs.io/latest/can/output.html
