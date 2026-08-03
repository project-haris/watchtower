# Changelog

All notable changes to watchtower (Project Haris Ansible automation).

## [Unreleased]

## [0.6.1] - 2026-08-03

### Changed
- `guides/scripts/http_bridge.py` (hub) → v2: raw NMEA stream capture to `/opt/haris/raw/nmea_raw.log` (ISO-UTC timestamped, 50 MB rotate, keep 2) + `allow_reuse_address=True` on both servers (fixes EADDRINUSE on restart caused by Signal K TcpProvider TIME_WAIT sockets).
- `guides/simulator-http-bridge-setup.md`: v2 script inline, new pitfall row for hub restart EADDRINUSE / TIME_WAIT.
- `guides/simulator-connection-checklist.md`: `set-system-time` clock pitfall (from 0.6.0, included here for completeness).

## [0.6.0] - 2026-08-03

### Docs
- `guides/simulator-http-bridge-setup.md` + `guides/simulator-connection-checklist.md`: document the `@signalk/set-system-time` clock-reset pitfall (bench sim feeds hardcoded 2019 GPS time → plugin runs `sudo date -u -s` every 60s → fights chrony → Zabbix clock-out-of-sync alert). Fix: disable plugin + restart signalk + `hwclock --hctosys`.
- `AGENTS.md`: repo context file for AI agents, now tracked.
- `.gitignore`: drop the `AGENTS.md` ignore entry.

## [0.5.0] - 2026-07-31

### Fixes
- guides: update haris-sinilind tailnet IP (`100.109.79.60` → `100.77.88.72`).

## [0.4.0] - 2026-07-31

### Added
- guides: Project Haris operational guides + index (`guides/`).
- haris: simulator HTTP bridge — hub (`simulator-bridge.service`), `sim-tcp` Signal K pipedProvider, Tailscale Funnel docs.
- haris: strip trailing dot from Tailscale DNS name for funnel cert.
- haris: protect OpenPlotter `settings.json` (no templating) + fix funnel under check mode.
