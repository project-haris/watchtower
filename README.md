# Watchtower

Watchtower is the Ansible automation repo for Project Haris vessel edge nodes and M-SOC core services. It provisions edge devices, deploys the Haris data collector and Signal K stack, and configures the onshore ELK pipeline that receives `haris_signalk` events.

## Main Playbooks

- `playbooks/group_vessel_edge/main.yml`: vessel edge devices
- `playbooks/group_msoc_core/main.yml`: M-SOC core nodes such as Citadel

## Key Components

- `roles/tailscale`: installs and authenticates Tailscale using `tailscale_auth_key`
- `roles/haris`: deploys Signal K and the `harisd` collector on vessel devices
- `roles/elk_stack`: deploys Elasticsearch, Logstash, and Kibana on core nodes
- `roles/firewalld`, `roles/sshd`, `roles/chrony`, `roles/zabbix_*`: supporting system services

## Data Flow

On vessel nodes, `harisd` polls the local Signal K API and writes JSONL snapshots locally. When SOC forwarding is enabled, it also forwards newline-delimited JSON events to Citadel on TCP `5045`.

On Citadel, Logstash accepts those events on TCP `5045` with `json_lines` and indexes them into `haris-signalk-*` in Elasticsearch.

## Common Runs

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -D
ansible-playbook playbooks/group_msoc_core/main.yml -D
```

Target a specific role or host when needed:

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t haris -D
ansible-playbook playbooks/group_msoc_core/main.yml -l haris-citadel -t elk_stack -D
```

## Notes

- The Haris role no longer depends on the Tailscale role. Tailscale is applied explicitly from the playbooks.
- Signal K is started by a systemd unit that uses `/usr/local/bin/signalk-server` and runs with `HOME={{ haris_home }}`.
- Tailscale auth should be provided as `tailscale_auth_key` in your group vars, host vars, or vaulted secrets.

## License

MIT
