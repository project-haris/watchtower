# Project Haris — Guides

Operational and reference guides for the Project Haris maritime cybersecurity platform:
vessel edge data collection, Signal K integration, simulator/bench workflows, and M-SOC
pipeline. This directory is the repo-side, readable home for the material maintained in
the `project-haris` Hermes skill — add new guides here going forward.

## Index

| File | What it is |
| :--- | :--- |
| `project-haris-overview.md` | Platform overview: architecture, the two published repos (`marine-haris`, `watchtower`), topology, key components. Start here. |
| `simulator-http-bridge-setup.md` | **Full simulator → Haris bridge setup (verified 2026-07-31).** Architecture, Tailscale Funnel (ACL/cert/`--bg`), hub script + systemd unit, signalk-server 2.30 pipedProvider config, every pitfall (orphaned 10110, TcpProvider-is-a-client, `None` prefix, CRLF, `suppress0183event`), verification, teardown/reopen. |
| `simulator-connection-checklist.md` | Bench checklist: CAN wiring verification, `candump`/interface checks, HTTP bridge + Funnel sections, end-to-end verification flow, troubleshooting. |
| `macarthur-hat-field-check.md` | Post-deployment validation checklist for the MacArthur HAT vessel node: CAN overlay, interface state, bitrate, candump, UART devices, Signal K API, harisd, Filebeat, all-in-one command. |
| `macarthur-hat.md` | MacArthur HAT spec + data flow (NMEA 2000 via MCP251xfd, NMEA 0183 UARTs) and PiCAN-M comparison. |
| `openplotter-install.md` | OpenPlotter v4.x install reference for haris-arthur (McArthur HAT RPi5, Debian 12 Bookworm), headless + starting editions. |
| `scripts/http_bridge.py` | The NMEA hub: HTTP POST `:8080` → TCP `:10130` with replay-on-connect. Same content as `roles/haris/files/http_bridge.py` — **the role file is the source of truth for deployment**. |
| `scripts/data_aggregator.py` | The `harisd` collector: polls the Signal K API, writes JSONL snapshots. Reference copy — deployed from `roles/haris/files/src/data_aggregator.py`. |
| `references/haris-role-defaults.yml` | Reference snapshot of the `haris` role default variables. |
| `references/es-field-limit-fix.md` | 2026-08-05 incident: sinilind ES docs missing 2 days — ES 1000-field limit blown by full N2K payload; diagnosis recipe + fix (template/live index → 10000). |
| `references/raw-data-preservation.md` | Raw NMEA/CAN capture on both Pis (hub `nmea_raw.log` + `haris-canraw` candump), never-delete policy, rotation semantics, candump `-L` gotcha. |

## How this maps to the skill

The canonical, always-updated copies live in the `project-haris` Hermes skill
(`~/.hermes/skills/devops/project-haris/`). This directory mirrors them for repo-side
reading and future additions. When a guide changes, update the skill copy first, then
mirror it here.
