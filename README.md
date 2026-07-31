# Watchtower

Watchtower is the Ansible automation repo for Project Haris vessel edge nodes and M-SOC core services. It provisions edge devices, deploys the Haris data collector and Signal K stack, and configures the onshore ELK pipeline that receives `haris_signalk` events.

[![License](https://img.shields.io/github/license/ahmdngi/watchtower?style=flat-square)]()
[![Language](https://img.shields.io/badge/language-Ansible-blue?style=flat-square)]()
[![Stars](https://img.shields.io/github/stars/ahmdngi/watchtower?style=flat-square)](https://github.com/ahmdngi/watchtower)

## Main Playbooks

- `playbooks/group_vessel_edge/main.yml`: vessel edge devices
- `playbooks/group_msoc_core/main.yml`: M-SOC core nodes such as Citadel

## Key Components

- `guides/`: operational guides for Project Haris (simulator bridge, field checks, MacArthur HAT, OpenPlotter install, data contract, index in `guides/README.md`)
- `artis3n.tailscale.machine`: collection role that installs and authenticates Tailscale using `tailscale_authkey`
- `roles/haris`: deploys Signal K-related vessel settings, the `harisd` collector, and Filebeat on vessel devices
- `roles/haris` (simulator bridge): optional `simulator_bridge.yml` deploys the NMEA HTTP bridge (`http_bridge.py` + `simulator-bridge.service`) and merges the `sim-tcp` Signal K piped provider when `haris_simulator_bridge_enabled: true`
- `roles/nodered`: installs Node-RED on Debian-based edge devices using the official Node-RED installer
- `roles/mullvad_browser`: installs Mullvad Browser on Debian-based edge devices from Mullvad's official apt repository
- `roles/elk_stack`: deploys Elasticsearch, Logstash, and Kibana on core nodes
- `roles/firewalld`, `roles/sshd`, `roles/chrony`, `roles/zabbix_*`: supporting system services

## Data Flow

On vessel nodes, `harisd` polls the local Signal K API and writes JSONL snapshots locally. When SOC forwarding is enabled, it also forwards newline-delimited JSON events to Citadel on TCP `5045`.

On Citadel, Logstash accepts those events on TCP `5045` with `json_lines` and indexes them into `haris-signalk-*` in Elasticsearch.

## Current Architecture

```text
Vessel sensors / NMEA
  -> Signal K on haris-sinilind
  -> harisd / data_aggregator.py
  -> /opt/haris/logs/signalk_snapshots.jsonl
  -> Filebeat
  -> Tailscale encrypted tunnel
  -> Logstash on haris-citadel:5044
  -> Elasticsearch
  -> Kibana
```

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

## Common Runs

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -D
ansible-playbook playbooks/group_msoc_core/main.yml -D
```

Target a specific role or host when needed:

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t haris -D
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t nodered -D
ansible-playbook playbooks/group_msoc_core/main.yml -l haris-citadel -t elk_stack -D
```

## Notes

- The Haris role no longer depends on the Tailscale role. Tailscale is applied explicitly from the playbooks via `artis3n.tailscale.machine`.
- On non-OpenPlotter hosts, Signal K is started by a systemd unit that uses `/usr/local/bin/signalk-server` and runs with `HOME={{ haris_home }}`.
- Tailscale auth should be provided as `tailscale_authkey` in your group vars, host vars, or vaulted secrets.
- The simulator HTTP bridge (bench NMEA 0183 over URL) is enabled per host with `haris_simulator_bridge_enabled: true`. It deploys a Python hub (HTTP `:8080` → TCP `:10130`) and merges the `sim-tcp` NMEA0183 piped provider into Signal K settings. Tailscale Funnel (`haris_simulator_funnel_enabled: true`) exposes the bridge publicly at `https://<host>.<tailnet>.ts.net/` — **requires the `funnel` node attribute in the tailnet policy file (admin console, one-time)** and is world-public; tear down with `sudo tailscale funnel reset` when not in use. Full architecture and pitfalls: the `project-haris` skill, `references/simulator-http-bridge-setup.md`.

## Changelog

### 2026-07-31

- Added optional simulator HTTP bridge to the `haris` role: `simulator_bridge.yml` deploys `http_bridge.py` (HTTP `:8080` → TCP `:10130` with replay-on-connect), a `simulator-bridge` systemd unit, and idempotently merges the `sim-tcp` NMEA0183 piped provider (`suppress0183event: true`) into Signal K settings — without overwriting OpenPlotter-managed config. Enabled via `haris_simulator_bridge_enabled` (set on haris-arthur).
- Added optional Tailscale Funnel enablement (`haris_simulator_funnel_enabled`) — issues cert + `tailscale funnel --bg`; requires the `funnel` node attribute in the tailnet policy.
- **Fix**: on OpenPlotter hosts, `haris_manage_signalk_config` is now `false` (haris-sinilind + haris-arthur). The role's settings template is a minimal skeleton and would drop OpenPlotter's piped providers, security, and ssl if applied to `/home/pi/.signalk/settings.json`. OpenPlotter-owned settings are only touched by the idempotent `sim-tcp` merge.
- **Fix**: Funnel enablement is a single shell task (`check_mode: false`) — the earlier `from_json`-based version broke under `--check` because command output is unavailable in check mode.
- Verified end-to-end on haris-arthur: simulator → public Funnel URL → hub → Signal K → harisd → ELK (signalk-server 2.30.0).

### 2026-07-30

- Split the `haris` role so OpenPlotter hosts can keep hardware and Signal K service ownership separate from repo-managed Signal K `settings.json` values.
- Updated OpenPlotter vessel host vars for `haris-sinilind` and `haris-arthur`, including live Signal K config path overrides to `/home/pi/.signalk`.
- Removed unsupported Signal K admin password handling from `settings.json` and clarified that admin/security state is not managed by this repo through that file.
- Fixed the `nodered` role to use the current upstream installer name and to run the installer as the target runtime user instead of `root`.
- Fixed a `firewalld` role bug where unmanaged cleanup loops failed when discovery returned an empty list.
- Added troubleshooting notes for OpenPlotter NodeSource `apt` issues and the Signal K `Unable to sign token: secretOrPrivateKey must have a value` error.

## Troubleshooting

### OpenPlotter Fresh Install: NodeSource `apt update` Failure

On a fresh OpenPlotter Bookworm install, `apt update` may fail because `/etc/apt/sources.list.d/openplotterNodejs.list` points at a NodeSource `bookworm` release path that returns `404`.

Example failing source entry:

```text
deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main
```

Example failure:

```text
Err: https://deb.nodesource.com/node_18.x bookworm Release
  404 Not Found
E: The repository 'https://deb.nodesource.com/node_18.x bookworm Release' no longer has a Release file.
```

Recovery steps:

```bash
# 1. Install the keyring
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

# 2. Write ONE correct source file (node_22.x, not 18.x)
echo 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main' | sudo tee /etc/apt/sources.list.d/openplotterNodejs.list

# 3. Remove any conflicting duplicates or old backups
sudo rm -f /etc/apt/sources.list.d/nodesource.list
sudo rm -f /etc/apt/sources.list.d/openplotterNodejs.list.bak

# 4. Update
sudo apt update
```

If the issue persists, inspect the active source file directly:

```bash
cat /etc/apt/sources.list.d/openplotterNodejs.list
```

### Signal K: `Unable to sign token: secretOrPrivateKey must have a value`

If Signal K shows:

```text
Unable to sign token: secretOrPrivateKey must have a value
```

the current Signal K FAQ says to disable or reset security by removing the security strategy block from `settings.json`, which is usually located at `$HOME/.signalk/settings.json`.

Remove this section:

```json
"security": {
  "strategy": "./tokensecurity"
},
```

If the server is started with the `--securityenabled` argument, remove that as well.

After updating the configuration, restart Signal K.

## License

MIT
