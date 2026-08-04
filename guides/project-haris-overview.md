
# Project Haris

**"Haris" (حارس) = Guardian** — maritime cybersecurity lab and platform.

## Architecture Overview

```
Vessel NMEA Network → PiCAN-M HAT → Raspberry Pi 5 → marine_haris
  → Local Storage (NVMe) → Tailscale VPN → M-SOC
  → Filebeat → Logstash → Elasticsearch → Kibana
  → Zabbix agent → Zabbix server (monitoring)
```

## Repositories

### 1. `marine_haris` — Edge Data Collector
- **Path:** `/root/project-haris/marine_haris/`
- **Language:** Python 3
- **Hardware:** RPi 5 (16GB) + PiCAN-M HAT + NVMe 128GB + TP-Link Archer NX200
- **BOM:** ~$710 total
- **Key files:**
  - `src/data_collection/nmea2000_parser.py` — CAN bus PGN parser (position, COG/SOG, heading, depth, wind)
  - `src/data_collection/nmea0183_parser.py` — Serial parser (RMC/GGA/GLL/VTG/HDT/DBT/MTW)
  - `src/data_collection/signal_k_ingestor.py` — Signal K API poller
  - `src/data_collection/data_aggregator.py` — Thread-safe aggregator, merges all sources into `VesselState` snapshots (default 10s interval)
  - `src/transmission/sync_to_server.py` — rsync-over-SSH batch sync
  - `src/transmission/webhook_sender.py` — Real-time webhook forwarding
  - `src/system/harisd.service` — systemd unit (hardened: NoNewPrivileges, PrivateTmp, ProtectSystem=strict)
  - `config/firewalld_setup.sh` — Fail-closed firewall (default drop zone)
  - `hardware/BOM.md` — Bill of materials
  - `docs/ARCHITECTURE.md` — Full architecture document
- **Data flow:** NMEA 2000 (CAN/SocketCAN) + NMEA 0183 (serial/ttyS0) + Signal K API → Data Aggregator → JSONL logs

### 2. `watchtower` — Ansible Automation
- **Path:** `/root/git-repos-personal/watchtower/`
- **Repo:** `https://github.com/project-haris/watchtower.git`
- **Language:** YAML (Ansible)
- **Full reference:** `~/wiki/projects/watchtower.md`
- **Inventory:** `hosts` — 4 nodes across 2 groups:
  - `[vessel_edge]`: `haris-sinilind` (PiCAN-M, 100.77.88.72), `haris-arthur` (McArthur HAT, 100.127.13.61)
  - `[msoc_core]`: `haris-citadel` (ELK+Zabbix, 100.126.59.101), `haris-gateway` (100.105.105.88)
- **Playbooks:**
  - `playbooks/group_vessel_edge/main.yml` — Vessel edge provisioning (Debian). Roles: sysctl, users_groups, sshd, soft_apt, mullvad_browser, firewalld, resolv_hosts, tailscale (artis3n), cron, **haris**, nodered, chrony, zabbix_agent
  - `playbooks/group_msoc_core/main.yml` — M-SOC core provisioning (Rocky/RedHat). Roles: sysctl, users_groups, sshd, soft_yum, firewalld, resolv_hosts, tailscale, cron, chrony, zabbix_agent, **zabbix_server**, **elk_stack**, docker
- **Host vars — haris-sinilind:** VESSEL-SINILIND, PiCAN-M overlay (`mcp2515-can0,oscillator=16000000,interrupt=25`), `/dev/ttyS0` @ 4800
- **Host vars — haris-arthur:** VESSEL-ARTHUR, McArthur overlay (`mcp251xfd,spi0-1,interrupt=25`), `/dev/ttyAMA2`, `haris_openplotter_mode: true`
- **Host vars — haris-citadel:** `haris_install_elk_stack: true`, `haris_install_zabbix_server: true`, `haris_install_docker: true`
- **Secrets:** Ansible Vault (`vars_common_secrets.yml` — Tailscale auth, user passwords, Signal K admin password)
- **Key roles:**
  - `roles/haris/tasks/main.yml` — system_prep (system deps, CAN overlay, Filebeat, haris user) → signal_k (npm signalk-server, settings template, systemd) → haris_integration (deploy data_aggregator.py, harisd.service, filebeat.yml)
  - `roles/elk_stack/tasks/main.yml` — Full ELK 8.x: repos, install, JVM heap, config templates, security (ES bootstrap+user passwords, kibana_system, logstash_writer role, haris-signalk index template), service enable
  - `roles/zabbix_server/tasks/main.yml` — Zabbix 7.4 on Rocky: DB setup, schema import, frontend config (Apache+PHP-FPM), service enable
  - `roles/zabbix_agent/tasks/main.yml` — Agent2 on Debian+RedHat: repo config, install, config template
  - `roles/nodered/tasks/main.yml` — Node-RED on Debian: official installer, Node.js 22, Pi nodes
  - `roles/mullvad_browser/tasks/main.yml` — Mullvad Browser repo + install (stable/alpha fallback)
- **haris role defaults:** `haris_vessel_id: VESSEL-001`, `haris_home: /opt/haris`, `haris_nmea2000_interface: can0`, `haris_nmea0183_port: /dev/ttyS0`, `haris_openplotter_mode: false`, `haris_can_boot_config_lines: [mcp2515 overlay]`, `haris_signalk_version: 2.23.0`, `haris_signalk_admin_password: change_me_password`, `haris_snapshot_interval: 10`, `haris_filebeat_enabled: true`
- **data_aggregator.py:** Python script deployed to vessel edge. Polls `http://127.0.0.1:3000/signalk/v1/api/vessels/self` every N seconds (fallback to API root on 404). Builds JSON events with @timestamp, source=haris_signalk, haris_host, vessel_id, vessel_name. Writes JSONL → Filebeat → Logstash :5044. Optionally forwards TCP :5045.
- **harisd.service template:** systemd unit with env vars for vessel identity, Signal K URL, log path, SOC forwarding. Ordered after signalk.service.
- **filebeat.yml.j2:** filestream input on JSONL, NDJSON parser, output to Logstash Beats port.
- **signalk_settings.json.j2:** Vessel identity, NMEA 0183 device/baud, N2K interface, admin password.
- **MACARTHUR_FIELD_CHECK.md** — 212-line post-deployment checklist: CAN interface verification (mcp251xfd, spi0.1, UP, 250000), candump, dmesg, UART check (/dev/ttyAMA2/4), Signal K API, harisd, Filebeat, all-in-one command, expected OpenPlotter CAN Bus settings (MCP251xfd, SPI0 CE1, 20MHz, GPIO 25)
- **Shared vars:** `vars_common_all.yml` — sysctl (IPv6 off), sshd (pubkey, AllowGroups admin root, IPv4-only), users (root, ahmed, ansible, admin with vaulted passwords), packages (apt/yum), comprehensive Estonian IP CIDR list (~230 entries), Zabbix server refs, cron (weekly /tmp cleanup)
- **Requirements:** collections (ansible.posix, community.general 10.7.5, community.docker, community.mysql, grafana.grafana 5.7.0, zabbix.zabbix, artis3n.tailscale), roles (githubixx/harden-linux, TalTech HPC gitlab roles, geerlingguy/docker, weareinteractive/cron, robertdebock/logrotate, linux-system-roles)

### 3. `tailscale-topography` — Network Topology Visualizer
- **Path:** `/root/project-haris/tailscale-topography/`
- **Language:** JavaScript (Node.js + vanilla JS frontend, zero deps)
- **How it works:** `server.js` execs `tailscale status --json`, returns normalized topology JSON
- **Frontend:** `public/index.html` — radial SVG graph + metric cards, refreshes every 30s
- **Connection types:** Direct (green) vs DERP-relayed (amber)
- **Deployment:** systemd, Docker (socket-mounts host tailscaled), Nix shell
- **Config:** env vars: `HOST`, `PORT`, `TAILSCALE_TIMEOUT_MS`, `TAILSCALE_BIN`, `TAILSCALE_SOCKET`

### 4. `vsat-honeypot` — SAILOR 900 VSAT Honeypot
- **Path:** `/root/project-haris/vsat-honeypot/`
- **Language:** Perl (zero CPAN deps — core modules only)
- **Purpose:** Emulates Cobham SAILOR 900 VSAT Ka Installation Manager web interface
- **Deployment:** Standalone Perl, Docker, Docker Compose, Nix shell
- **Config:** `config/honeypot.json` (bind/port, rate limit, navigation mode, vessel identity)
- **Endpoints:**
  - `POST /api/login` — credential capture (admin/1234, service/service)
  - `GET /api/status` — simulated device state
  - `POST /api/config/network` — fake network config
  - `POST /api/config/antenna` — fake antenna config
  - `POST /api/command` — diagnostic console capture
  - `POST /api/upload` — file upload capture
- **Security:** In-memory rate limiting (180 req/60s), session cookies, GitLeaks CI scanning
- **Server header spoof:** `Allegro-WebServer/3.2.1` (matches real SAILOR)

## Current Topology

- **vessel_edge:** `haris-sinilind`
- **msoc_core:** `haris-gateway`, `haris-citadel` (ELK + Zabbix server)
- **Contact:** ahmed@ahmdngi.io

### 5. `haris-crew-app` — Android Crew Monitoring App

- **Path:** `/root/project-haris/haris-crew-app/`
- **Language:** Dart (Flutter)
- **Purpose:** Android app for vessel crew to monitor live Signal K data + ELK alerts
- **Architecture:** Clean architecture — core/, data/, domain/, presentation/
- **State:** Riverpod 2.x
- **Cache:** SharedPreferences (no codegen required)
- **Vessel data:** WebSocket to Signal K, delta parser with auto-reconnect + exponential backoff
- **Alerts:** REST fetch + WebSocket push from Citadel relay
- **Screens:** Dashboard (gauges, position, connection), Alerts (list + detail), Settings
- **Auth:** Tailscale (device on tailnet)
- **Build:** Flutter 3.44.0, AGP 9.0.1, Kotlin 2.3.20, Gradle 9.1.0, compileSdk 36, Java 21
- **APK:** `flutter build apk --debug` → build/app/outputs/flutter-apk/app-debug.apk
- **Package:** ee.haris.crew, minSdk 26
- **Docs:** docs/ARCHITECTURE.md — full architecture document

### 6. `haris-command-center` — Real-Time Monitoring Dashboard

- **Path:** `/root/git-repos-personal/haris-command-center/`
- **Repo:** https://github.com/ahmdngi/haris-command-center (**PRIVATE** — `config.py` contains real ES passwords + node IPs; do not make public without scrubbing creds to env vars)
- **Language:** Python (Flask), vanilla JS, SSE, Leaflet 1.9.4
- **Purpose:** real-time monitoring dashboard for the full Haris M-SOC — 17 collectors polling 4 Tailscale nodes every 10s, streaming via SSE
- **Run:** `cd /root/git-repos-personal/haris-command-center && source venv/bin/activate && HOME=/root python3 app.py` → `http://100.72.133.89:5001` (must set `HOME=/root` or SSH key resolution breaks)
- **Collectors:** Node, Elastic, Logstash, Pipeline, SignalK, Zabbix, Honeypot, Nmea, Tailscale, ZabbixAlert, DataFlow, FlapDetector, Filebeat, Hardware, HoneypotDetail, EsLifecycle, LogstashErrors
- **Key design decisions:**
  - SSH via `subprocess` (paramiko rejects Tailscale SSH "none" auth)
  - Logstash `:9600` is localhost-only on citadel → collectors SSH + curl localhost
  - ES search via SSH with `elastic` user (`kibana_system` can health/cat only); elastic pw from `/root/elastic` on citadel
  - NMEA collector reads `:10130` (hub TCP broadcast), NOT `:10110` (orphaned in signalk 2.30)
  - Leaflet CDN links must NOT get SRI hashes (wrong hashes block loading)
  - Cache-busting: bump `?v=` on static files (css v5, sse v3, ui v7, core v5)
- **⚠️ Known bug (2026-08-04):** `collectors/signalk_collector.py` calls `/signalk/v1/api/vessels/self` — **404s on signalk-server 2.30**; vessel telemetry panel + position map show nulls. Fix: API root + `.vessels[<uuid>]` resolution (mirror harisd's fallback). Rest of dashboard works.
- **Release:** v0.3.0 (Leaflet vessel map + track), pushed 2026-08-04, branch `main`.

## NMEA 0183 → Signal K Ingestion

Feeding external NMEA 0183 (simulators, bench rigs) into Signal K. **Full guide: `references/nmea-signalk-ingestion.md`** (field-verified on arthur bench, 2026-07/08).

- **Key fact (signalk-server 2.30):** the working TCP input is a pipedProvider whose TcpProvider *dials out*; port 10110 is orphaned. Use `providers/simple` + `subOptions: {type: tcp, suppress0183event: true}` (config: `references/simulator-http-bridge-setup.md` §4).
- **Hub**: `references/simulator-http-bridge.py` (v3) — HTTP :8080 → TCP :10130 broadcast + replay deque(10), strips junk before `$`, appends CRLF, **rewrites stale RMC DDMMYY dates + recomputes checksums** (`fix_rmc_date`).
- **Pitfalls**: bad checksums drop silently; stale-dated RMC never promotes (sim's real position hides in `navigation.position.values.<source>`); TIME_WAIT on :10130 → `allow_reuse_address = True` as class attribute.
- **Ansible**: never template settings.json on OpenPlotter hosts (`haris_manage_signalk_config: false`); trailing-dot on `tailscale status --json` DNSName; check-mode traps; funnel node attribute is admin-console-only.
- **Refs**: `references/rmc-date-freshness-fix.md`, `references/elk-arrival-verification.md`, `references/rpi5-serial-and-monitoring-gotchas.md`, `references/signalk-set-system-time-pitfall.md`, `scripts/verify_rmc_date_fix.py`, `scripts/signalk-data-watchdog.sh` (10-min data watchdog — cron job `arthur-data-watchdog`).

## Explainer Video Production

Remotion motion graphics video (1920×1080, 30fps, 30s, 5 acts) explaining Project Haris — PiCAN-M and MacArthur HAT data flows. **Full spec: `references/haris-explainer-video.md`** (scaffold command, project structure, per-act frame ranges, color palette, composition).

## Related Skills (kept separate — load on demand)

- `vnc-remote-access` (devops) — VNC to headless Pi/OpenPlotter hosts: RealVNC auth without cloud sign-in (`Authentication=VncAuth`, `Encryption=PreferOff`), X11-vs-Wayland trap (RealVNC can't capture Wayland — use `LXDE-pi-x`), lightdm autologin, client troubleshooting (TigerVNC, macOS Screen Sharing).
- `tailscale-funnel-serve` (devops) — expose local services publicly or tailnet-only via Tailscale Funnel/Serve: ACL `nodeAttrs` prerequisite, `--bg` persistence, cert, verification, teardown (`tailscale funnel reset`).

## References

- `references/crew-app-signalk-data-contract.md` — Exact Signal K delta format, WebSocket subscription flow, and supported paths for the Haris Crew App's data ingestion layer. Use when building synthetic AIS sources or debugging crew app connectivity.
- `references/macarthur-hat.md` — MacArthur HAT specification, data flow, and comparison vs PiCAN-M HAT.
- `references/watchtower-macarthur-field-check.md` — Post-deployment validation checklist for McArthur HAT on RPi5: CAN interface verification, candump, dmesg, UART, Signal K, harisd, Filebeat. Originally at `watchtower/roles/haris/MACARTHUR_FIELD_CHECK.md`.
- `references/watchtower-data-aggregator.py` — Python data collector deployed to vessel edge: polls Signal K API, writes JSONL snapshots, forwards to SOC via Filebeat or legacy TCP.
- `references/watchtower-haris-role-defaults.yml` — All `haris` role variables with defaults and descriptions.
- `references/openplotter-install.md` — OpenPlotter v4.x.x installation reference for haris-arthur (McArthur HAT RPi5). OS: Debian 12 Bookworm. Download links for Headless and Starting editions.
- `references/simulator-http-bridge-setup.md` — **Complete simulator→Haris HTTP bridge setup (verified 2026-07-31)**. Full architecture, Tailscale Funnel (ACL/cert/--bg), hub script + systemd unit, signalk-server 2.30 pipedProvider config, all pitfalls (10110 orphan, TcpProvider client, None prefix, CRLF, suppress0183event), verification + teardown.
- `references/simulator-http-bridge.py` — Final working hub script (HTTP :8080 → TCP :10130 with replay-on-connect, v3 with RMC date correction). Deploy to `/opt/haris/http_bridge.py`.
- `references/nmea-signalk-ingestion.md` — Full NMEA 0183 → Signal K ingestion guide (absorbed from `nmea-signalk-ingestion` skill): architecture, hub, Ansible + Hermes deployment pitfalls, field pitfalls.
- `references/rmc-date-freshness-fix.md` — RMC stale-date diagnosis + hub `fix_rmc_date` fix and harisd `HARIS_MAX_SIGNAL_AGE` freshness filter (2026-08-04).
- `references/elk-arrival-verification.md` — Verifying signal data arrival in Elasticsearch (logstash stats, filebeat registry, per-vessel queries).
- `references/rpi5-serial-and-monitoring-gotchas.md` — RPi5 serial + monitoring pitfalls.
- `references/signalk-set-system-time-pitfall.md` — Signal K / system time pitfalls.
- `references/haris-explainer-video.md` — Remotion explainer video spec (absorbed from `haris-explainer-video` skill).
- **Scripts:** `scripts/verify_rmc_date_fix.py` — end-to-end check of the RMC date fix; `scripts/signalk-data-watchdog.sh` — 10-min arthur data watchdog (silent when healthy, alerts on stale/offline).
- **Wiki:** `~/wiki/projects/watchtower.md` — Full Ansible automation reference: inventory, playbooks, all roles, templates, common commands.
- GitHub org: https://github.com/project-haris
- License: MIT (all repos)
- This is research/operational tooling for authorized environments only
