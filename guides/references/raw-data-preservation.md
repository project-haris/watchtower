# Raw Data Preservation (never delete policy)

**Policy (Ahmed, 2026-08-04): raw NMEA/CAN logs are NEVER deleted.**

## What is captured

| Node | Raw source | Path | Capture mechanism |
|---|---|---|---|
| haris-arthur | Simulator NMEA 0183 (all sentences via hub) | `/opt/haris/raw/nmea_raw.log` | hub `raw_write` in `broadcast()` |
| haris-sinilind | Real N2K CAN frames (can0, PiCAN-M) | `/opt/haris/raw/can0_raw.log` | `haris-canraw` service (candump) |

Arthur's CAN bus is NOT captured and NOT enabled — can0 is ERROR-PASSIVE, 0 frames
(no bus connection; arthur's only input is the funnel → simulator). Confirmed by Ahmed.

## Arthur — hub raw log

- Deployed hub (`/opt/haris/http_bridge.py`, v3): every cleaned sentence appended with ISO timestamp.
- Rotation at `RAW_MAX_BYTES` (50 MB): `nmea_raw.log → nmea_raw.log.1 → .2 → …` —
  `RAW_KEEP = 999999` (changed from 2, commit `b452e2b`) so **nothing is ever removed**.
- Rate: ~11 MB per 2 days of sim use (~200k sentences). Never hit 50 MB yet → no rotation file exists.
- Raw capture started **2026-08-03** (v2 hub deploy) — Jul 31 data predates it.
- **Trip counting ground truth**: cluster lines by timestamp gaps (>120s = new session).
  5 real sim sessions counted 2026-08-05 from this file. ES-derived session counts are
  unreliable (replay deque refreshes model timestamps on provider reconnect).

## Sinilind — candump capture

- Service: `haris-canraw.service` (user `haris`, `Restart=always`):
  `ExecStart=/bin/sh -c '/usr/bin/candump can0 -L >> /opt/haris/raw/can0_raw.log'`
- **Gotcha**: on this build `-L` means "log file format on **stdout**" — it does NOT take a
  file argument (`candump -L /path` fails with "name of CAN device '...' is too long").
  Lowercase `-l` auto-names a file in CWD. Append stdout redirection is the stable-path approach.
- Logrotate `/etc/logrotate.d/haris-canraw`: daily, `compress`, `copytruncate`,
  `rotate 9999` → effectively never deletes. ~237 frames/s at anchor → ~11.9 KB/s raw
  (~1 GB/day) → ~100 MB/day compressed.
- Role: `roles/haris/tasks/canraw.yml` gated on `haris_canraw_enabled` (default `false`,
  **true** on sinilind), commit `cec763b`.

## How to verify capture is live

```bash
systemctl is-active haris-canraw
sudo stat -c %s /opt/haris/raw/can0_raw.log   # grows ~12 KB/s on sinilind
tail -n 2 /opt/haris/raw/can0_raw.log         # (epoch.frac) can0 <id>#<data>
```

## Related

- `es-field-limit-fix.md` — why sinilind's ES docs were missing (unrelated to raw capture).
- Sim ground truth note: raw logs are the ONLY per-sentence/frame record; ES holds the
  10s-aggregated view. Nothing else preserves raw data (no candump on arthur, no serial capture).
