# Ansible Role: Project Haris

## Description

This role automates the deployment and configuration of the **Project Haris** edge computing stack on Raspberry Pi devices. It transforms a vanilla Raspberry Pi OS into a maritime security data node that runs Signal K locally and forwards snapshots toward the M-SOC pipeline.

The role handles:
- **System Preparation**: User creation, system dependencies, and CAN bus interface setup.
- **Signal K Server**: Installation and configuration of the Signal K data server for NMEA 2000/0183 ingestion.
- **Application Integration**: Deployment of the custom `harisd` data aggregator, local JSONL logging, and Filebeat shipping.

Haris snapshots use `haris_host` for the edge hostname so they do not collide with the ECS `host.*` fields added by Filebeat.

## Requirements

### Platform
- **OS**: Raspberry Pi OS (64-bit) / Debian Bookworm or newer.
- **Architecture**: aarch64 (ARM64).
- **Hardware**: Raspberry Pi 4 or 5.

### Controller Node
- Ansible >= 2.10
- `ansible.builtin`, `ansible.posix`, and `community.general` collections.

## Scope

This role does not install or configure Tailscale. Apply the `artis3n.tailscale.machine` collection role explicitly from your playbook when you want VPN access on the node.

## Role Structure

The role is organized into logical task files:
- `system_prep.yml`: Prepares the OS, installs drivers (CAN utils, firewalld), and creates the `haris` user.
- `signal_k.yml`: Installs NodeJS dependencies and Signal K server via NPM.
- `haris_integration.yml`: Deploys the custom Python scripts and configures system services.

## Variables

Variables are defined in `defaults/main.yml`. You **must** override the identifiers and security credentials in your `host_vars` or `group_vars`.

### General Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_vessel_id` | `"VESSEL-001"` | Unique identifier for the vessel (used in data tagging). |
| `haris_vessel_name` | `"Default Vessel"` | Human-readable name for the vessel. |
| `haris_timezone` | `"UTC"` | System timezone (e.g., `"America/New_York"`). |
| `haris_user` | `"haris"` | System user that owns the application files. |
| `haris_home` | `"/opt/haris"` | Installation directory for scripts and logs. |

### NMEA Sensor Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_nmea2000_interface` | `"can0"` | The CAN interface name (usually `can0` for PiCAN-M). |
| `haris_nmea0183_port` | `"/dev/ttyS0"` | Serial port for NMEA 0183 (PiCAN-M terminal block). |
| `haris_nmea0183_baud` | `4800` | Baud rate for the serial port (Standard: 4800, HS: 38400). |

### Signal K Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_signalk_version` | `"2.6.0"` | Version of Signal K Server to install. |
| `haris_signalk_port` | `3000` | Port for the Signal K web interface and API. |
| `haris_signalk_admin_password` | `"change_me_password"` | **(Required)** Password for the Signal K admin interface. |

### SOC Forwarding Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_soc_forward_enabled` | `false` | Enable legacy direct TCP forwarding of Signal K snapshots to the SOC pipeline. |
| `haris_soc_log_host` | `""` | Destination host for legacy JSON line forwarding, typically Citadel. |
| `haris_soc_log_port` | `5045` | Destination TCP port for the legacy Logstash `json_lines` input. |
| `haris_snapshot_interval` | `10` | Poll interval in seconds for the local Signal K API. |
| `haris_filebeat_enabled` | `true` | Install and configure Filebeat on the edge device. |
| `haris_filebeat_logstash_host` | `{{ haris_soc_log_host }}` | Destination Logstash host for the Beats pipeline. |
| `haris_filebeat_logstash_port` | `5044` | Destination Beats port on the M-SOC Logstash host. |
| `haris_filebeat_log_path` | `{{ haris_home }}/logs/signalk_snapshots.jsonl` | JSONL log file tailed by Filebeat. |

## Dependencies

None.

If you also want VPN access, apply the `artis3n.tailscale.machine` collection role separately. If you also want Elasticsearch, Logstash, and Kibana, use the separate `elk_stack` role alongside `haris`.

## Example Playbook

**`site.yml`**
```yaml
---
- name: Deploy Project Haris Stack
  hosts: vessels
  become: yes
  roles:
    - haris
```

## Usage Guide: Configuring Host Vars

To customize the deployment for a specific vessel, create a file in your inventory directory.

**File Structure:**
```text
inventory/
├── hosts
└── host_vars/
    └── haris_vessel.yml  <-- Specific config for this vessel IP
```

**`inventory/host_vars/haris_vessel.yml`**
```yaml
---
# Vessel Identity
haris_vessel_id: "VESSEL-ALPHA-01"
haris_vessel_name: "MV Atlantic Guardian"
haris_timezone: "UTC"

# Sensor Specifics
haris_nmea0183_baud: 38400 

# Signal K Security
haris_signalk_admin_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  663864396539666364663166...

# SOC forwarding via Filebeat
haris_soc_forward_enabled: false
haris_soc_log_host: "haris-citadel"
haris_filebeat_enabled: true
haris_filebeat_logstash_host: "haris-citadel"
haris_filebeat_logstash_port: 5044
```

## Deployment Steps

1.  **Install the Role**: Place the `haris` role in your `roles/` directory.
2.  **Configure Variables**: Create your `host_vars` file with the specific vessel details.
3.  **Run the Playbook**:
    ```bash
    ansible-playbook playbooks/group_vessel_edge/main.yml -D --ask-vault-pass
    ```

## Post-Deployment Verification

1.  **Check Services**:
    ```bash
    ssh haris@<tailscale-hostname>
    sudo systemctl status harisd
    sudo systemctl status signalk
    sudo systemctl status filebeat
    ```
    `harisd` is ordered after `signalk.service`, so if you restart Signal K during maintenance you should expect the collector to recover cleanly after Signal K is listening again.
2.  **Check Local Signal K API**:
    ```bash
    curl http://127.0.0.1:3000/signalk/v1/api/
    curl http://127.0.0.1:3000/signalk/v1/api/vessels/self
    ```
    `harisd` prefers `/signalk/v1/api/vessels/self`, but it will fall back to `/signalk/v1/api/` if Signal K temporarily returns `404` during startup, discovery, or after server upgrades.
3.  **Check Local Collector Output**:
    ```bash
    sudo tail -n 5 /opt/haris/logs/signalk_snapshots.jsonl
    ```
4.  **Check Filebeat Shipping**:
    ```bash
    sudo filebeat test config
    sudo filebeat test output
    ```
5.  **Check SOC Forwarding**:
    Verify that Citadel is listening on TCP `5044` for Beats traffic. Enable `haris_soc_forward_enabled` only if you also want the legacy direct TCP `5045` path.
6.  **Check Firewall**:
    ```bash
    sudo firewall-cmd --state
    sudo firewall-cmd --zone=tailscale --list-all
    ```
7.  **Access Dashboards**:
    - **Signal K**: `http://<tailscale-hostname>:3000`

## Security Architecture

The role is typically used together with a fail-closed firewall profile:

- **Default Zone**: `drop`
- **Trusted Zone**: `tailscale`
- **Allowed Services via Tailscale**: SSH (22), Signal K (3000), and operational ports defined in the playbook group vars

## License

MIT

## Author Information

Created by the Maritime Security Operations Center (M-SOC) Engineering Team.
