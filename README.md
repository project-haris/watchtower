# Watchtower

Ansible automation for **Project Haris** (حارس = Guardian) — the maritime cybersecurity lab's vessel edge nodes and M-SOC core. Watchtower provisions the edge devices, deploys the Haris Signal K stack and `harisd` collector, and configures the onshore ELK pipeline that receives `haris_signalk` events.

Part of the oversight.ee maritime cybersecurity ecosystem, alongside ShipCrawler (vessel OSINT) and Sirb (N-agent orchestration).

[![License](https://img.shields.io/github/license/ahmdngi/watchtower?style=flat-square)]()
[![Language](https://img.shields.io/badge/language-Ansible-blue?style=flat-square)]()
[![Stars](https://img.shields.io/github/stars/ahmdngi/watchtower?style=flat-square)](https://github.com/ahmdngi/watchtower)

---

## Inventory

| Group | Host | Role |
|---|---|---|
| `vessel_edge` | `haris-sinilind` (100.77.88.72) | Vessel edge: NMEA 2000/0183 → Signal K → harisd → Filebeat (OpenPlotter, MacArthur HAT) |
| `vessel_edge` | `haris-arthur` (100.127.13.61) | Bench/simulator vessel node (OpenPlotter, MacArthur HAT) |
| `msoc_core` | `haris-gateway` (100.105.105.88) | M-SOC gateway |
| `msoc_core` | `haris-citadel` (100.126.59.101) | M-SOC core: Logstash, Elasticsearch, Kibana, Zabbix server |

All hosts are on the Tailscale tailnet — Ansible reaches them over the encrypted tunnel.

## Main Playbooks

```bash
# Vessel edge devices (sinilind, arthur)
ansible-playbook playbooks/group_vessel_edge/main.yml -D

# M-SOC core nodes (gateway, citadel)
ansible-playbook playbooks/group_msoc_core/main.yml -D

# Target a specific role or host
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t haris -D
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t nodered -D
ansible-playbook playbooks/group_msoc_core/main.yml -l haris-citadel -t elk_stack -D
```

`-D` = `--diff` (dry-run friendly). Every role respects the `disabled_roles.yml` kill switch.

## Roles

**In-repo roles** (`roles/`):

| Role | Purpose |
|---|---|
| `haris` | Signal K settings, `harisd` collector, Filebeat, simulator HTTP bridge, raw CAN capture (`canraw.yml`) |
| `elk_stack` | Elasticsearch, Logstash, Kibana on core nodes (`haris-signalk-*` index template) |
| `nodered` | Node-RED on Debian edge devices (official installer, as the runtime user) |
| `mullvad_browser` | Mullvad Browser from Mullvad's official apt repo |
| `zabbix_agent` / `zabbix_server` | Monitoring agents + server |

**Common system roles** — referenced by the playbooks but installed as galaxy/git roles into `~/.ansible/roles` via `requirements.yml` (TalTech HPC gitlab sources): `sysctl`, `users_groups`, `sshd`, `soft_apt`, `firewalld`, `resolv_hosts`, `chrony`, `logrotate`, and more.

```bash
ansible-galaxy install -r requirements.yml
```

**Collections**: `artis3n.tailscale.machine` installs and authenticates Tailscale using `tailscale_authkey` (provide in group/host vars or vault).

## Data Flow

```text
                   Project Haris Data Pipeline

             Vessel Edge Node                     M-SOC Core Node
          +---------------------+               +----------------------+
          |   haris-sinilind    |               |    haris-citadel     |
          |---------------------|               |----------------------|
          | NMEA 2000 / 0183    |               | Logstash             |
          | Signal K :3000      |               | Beats input :5044    |
          | harisd              |               | TCP json_lines :5045 |
          | data_aggregator.py  |               | Elasticsearch :9200  |
          | JSONL log file      |               | Kibana :5601         |
          | Filebeat            |               | Zabbix server        |
          +----------+----------+               +----------+-----------+
                     |                                     ^
                     | Tailscale encrypted tunnel          |
                     | Beats events on TCP 5044            |
                     +-------------------------------------+
```

- On vessel nodes, `harisd` polls the local Signal K API and writes JSONL snapshots; with SOC forwarding enabled it also pushes newline-delimited JSON events to Citadel TCP `5045`.
- On Citadel, Logstash accepts those events (`json_lines`) and indexes them into `haris-signalk-*` in Elasticsearch.
- Raw preservation: the simulator hub captures raw NMEA to `/opt/haris/raw/nmea_raw.log` (never deleted), and `haris-canraw.service` captures raw CAN frames on sinilind — per-frame detail survives even though the aggregator prunes `meta`/`values` maps from snapshots (~10× smaller docs, ends the ES field explosion).

## Guides

`guides/` is the repo-side home of the Project Haris operational docs (mirrored from the `project-haris` Hermes skill — update the skill first, then mirror). Index in [`guides/README.md`](guides/README.md). Highlights:

> **Interactive architecture diagram:** [`guides/architecture-watchtower.html`](guides/architecture-watchtower.html) — archify-generated (dark/light themes, PNG/SVG export). Source spec: [`guides/architecture-watchtower.json`](guides/architecture-watchtower.json).

- `project-haris-overview.md` — platform architecture, all Haris repos, topology. Start here.
- `simulator-http-bridge-setup.md` — simulator → Haris bridge, Tailscale Funnel, every pitfall (verified)
- `simulator-connection-checklist.md` — bench checklist: CAN wiring, candump, end-to-end verification
- `macarthur-hat.md` / `macarthur-hat-field-check.md` — HAT spec + post-deployment validation
- `crew-app-signalk-data-contract.md` — Signal K delta contract for the Android crew app
- `references/es-field-limit-fix.md` — 2026-08-05 incident: ES 1000-field limit blown by N2K payload
- `references/raw-data-preservation.md` — raw NMEA/CAN capture policy, candump `-L` gotcha

## Simulator Bridge (bench workflows)

Optional per-host features of the `haris` role:

- `haris_simulator_bridge_enabled: true` — deploys the NMEA HTTP bridge (`http_bridge.py`: HTTP `:8080` → TCP `:10130`, replay-on-connect) and merges the `sim-tcp` Signal K piped provider, without touching OpenPlotter-owned config.
- `haris_simulator_funnel_enabled: true` — exposes the bridge publicly via Tailscale Funnel at `https://<host>.<tailnet>.ts.net/`. Requires the `funnel` node attribute in the tailnet policy (admin console, one-time); world-public — tear down with `sudo tailscale funnel reset`.

## Notes

- The `haris` role does not depend on the Tailscale role; Tailscale is applied explicitly from the playbooks via `artis3n.tailscale.machine`.
- On non-OpenPlotter hosts, Signal K runs as a systemd unit via `/usr/local/bin/signalk-server` with `HOME={{ haris_home }}`.
- On OpenPlotter hosts (sinilind, arthur) `haris_manage_signalk_config` is `false` — the role's settings template is a minimal skeleton and would drop OpenPlotter's piped providers; only the idempotent `sim-tcp` merge touches those settings.
- Tailscale auth: provide `tailscale_authkey` in group vars, host vars, or vaulted secrets.

## Troubleshooting

**OpenPlotter fresh install: NodeSource `apt update` 404** — `/etc/apt/sources.list.d/openplotterNodejs.list` points at a dead `node_18.x` bookworm path. Reinstall the keyring and write a single `node_22.x` source (`nodistro main`), remove duplicates/backups, `apt update`. Full commands in the changelog below.

**Signal K: `Unable to sign token: secretOrPrivateKey must have a value`** — remove the `security` strategy block from `$HOME/.signalk/settings.json` (and any `--securityenabled` server argument), restart Signal K.

## Changelog

Full history in [CHANGELOG.md](CHANGELOG.md).

- **Unreleased (2026-08-04/05)** — raw CAN capture role (`haris-canraw.service`, never-delete logrotate) on sinilind; aggregator `prune_payload()` strips `meta`/`values` from snapshots (~10× smaller N2K docs); ES `total_fields.limit` → 10000 (field-explosion incident fix); raw-data-preservation + es-field-limit guides.
- **0.6.1 (2026-08-03)** — hub `http_bridge.py` v2: raw NMEA capture (50 MB rotate), `allow_reuse_address` fixes EADDRINUSE on restart.
- **0.6.0 (2026-08-03)** — `@signalk/set-system-time` clock pitfall documented (bench sim feeds 2019 GPS time, fights chrony); AGENTS.md tracked.
- **0.5.0 (2026-07-31)** — sinilind tailnet IP update.
- **0.4.0 (2026-07-31)** — guides/ added; simulator HTTP bridge + Funnel; OpenPlotter `settings.json` protection; funnel under check mode.

## Related

- **[ShipCrawler 2.0 (Geo-Watch)](https://github.com/ShipCrawler/shipcrawler-2.0)** — Agentic maritime perimeter awareness for offshore wind (Liivi 1+2, Gulf of Riga)
- **[shipCrawler (1.x)](https://github.com/ahmdngi/shipCrawler)** — Production vessel-OSINT dashboard (IEEE Access 2026)
- **[Sirb](https://github.com/ahmdngi/sirb)** — Agnostic N-agent task orchestration kernel (Swarm)
- **Project Haris** — `marine-haris` (edge collector) and `watchtower` (this repository)
- **oversight.ee** — Maritime cybersecurity company site ([oversight.ee](https://www.oversight.ee))

## License

MIT
