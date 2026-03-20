# Ansible Role: Project Haris

## Description

This role automates the deployment and configuration of the **Project Haris** edge computing stack on Raspberry Pi devices. It transforms a vanilla Raspberry Pi OS into a fully functional maritime security data node, ready for integration with a Maritime Security Operations Center (M-SOC).

The role handles:
- **System Preparation**: User creation, system dependencies, and CAN bus interface setup.
- **Tailscale VPN**: Secure mesh VPN connectivity using Tailscale (WireGuard-based).
- **Signal K Server**: Installation and configuration of the Signal K data server for NMEA 2000/0183 ingestion.
- **ELK Stack**: Deployment of Elasticsearch, Logstash, and Kibana for local data storage and visualization.
- **Application Integration**: Deployment of the custom `harisd` data aggregator and Filebeat for log shipping.

## Requirements

### Platform
- **OS**: Raspberry Pi OS (64-bit) / Debian Bookworm or newer.
- **Architecture**: aarch64 (ARM64).
- **Hardware**: Raspberry Pi 4 or 5 (Recommended: 8GB+ RAM for ELK stack).

### Controller Node
- Ansible >= 2.10
- `ansible.builtin`, `ansible.posix`, and `community.general` collections.

## Role Structure

The role is organized into logical task files:
- `system_prep.yml`: Prepares the OS, installs drivers (CAN utils, firewalld), and creates the `haris` user.
- `signal_k.yml`: Installs NodeJS dependencies and Signal K server via NPM.
- `elk_stack.yml`: Installs the Elastic repository and deploys the ELK components.
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
| `haris_home` | `"/opt/marine_haris"` | Installation directory for scripts and logs. |

### NMEA Sensor Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_nmea2000_interface` | `"can0"` | The CAN interface name (usually `can0` for PiCAN-M). |
| `haris_nmea0183_port` | `"/dev/ttyS0"` | Serial port for NMEA 0183 (PiCAN-M terminal block). |
| `haris_nmea0183_baud` | `4800` | Baud rate for the serial port (Standard: 4800, HS: 38400). |

### Tailscale VPN Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `tailscale_authkey` | `""` | **(Required)** Auth key for Tailscale authentication. |
| `tailscale_args` | `""` | Additional arguments for `tailscale up`. |
| `tailscale_tags` | `[]` | Tags to apply to the node. |
| `tailscale_up_skip` | `false` | Skip Tailscale authentication (for testing). |

### Signal K Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `signalk_version` | `"2.6.0"` | Version of Signal K Server to install. |
| `signalk_port` | `3000` | Port for the Signal K web interface and API. |
| `signalk_admin_password` | `"change_me_password"` | **(Required)** Password for the Signal K admin interface. |

### ELK Stack Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `elasticsearch_version` | `"8.x"` | Major version of Elastic stack to install. |
| `elasticsearch_heap_size` | `"2g"` | JVM Heap size (e.g., `2g`, `4g`). **Do not exceed 50% of RAM.** |
| `elasticsearch_password` | `"elastic_change_me"` | **(Required)** Password for the `elastic` superuser. |
| `kibana_port` | `5601` | Port for the Kibana dashboard. |

## Dependencies

This role depends on:
- `tailscale` role - Sets up VPN connectivity

## Example Playbook

**`site.yml`**
```yaml
---
- name: Deploy Project Haris Stack
  hosts: vessels
  become: yes
  roles:
    - marine_haris
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

# Tailscale VPN
tailscale_authkey: "tskey-auth-xxxxxxxxxxxxx"
tailscale_tags:
  - "tag:marine-haris"

# Signal K Security
signalk_admin_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  663864396539666364663166...

# ELK Stack Tuning (Pi 5 16GB recommended)
elasticsearch_heap_size: "4g"
elasticsearch_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  326465383736356662363834...
```

## Deployment Steps

1.  **Install the Role**: Place the `marine_haris` role in your `roles/` directory.
2.  **Configure Variables**: Create your `host_vars` file with the specific vessel details.
3.  **Generate Tailscale Auth Key**: Create an auth key at https://login.tailscale.com/admin/settings/keys
4.  **Run the Playbook**:
    ```bash
    ansible-playbook -i inventory/hosts site.yml --ask-vault-pass
    ```

## Post-Deployment Verification

1.  **Check Services**:
    ```bash
    ssh haris@<tailscale-hostname>
    sudo systemctl status harisd
    sudo systemctl status signalk
    sudo systemctl status elasticsearch
    sudo systemctl status tailscaled
    ```
2.  **Check Firewall**:
    ```bash
    sudo firewall-cmd --state
    sudo firewall-cmd --zone=tailscale --list-all
    ```
3.  **Access Dashboards** (via Tailscale only):
    - **Signal K**: `http://<tailscale-hostname>:3000`
    - **Kibana**: `http://<tailscale-hostname>:5601`

## Security Architecture

The role implements a fail-closed security model:

- **Default Zone**: `drop` - All incoming traffic is blocked by default
- **Trusted Zone**: `tailscale` - Only traffic from the Tailscale interface is accepted
- **Allowed Services via Tailscale**: SSH (22), Signal K (3000), Kibana (5601), Elasticsearch (9200)

## License

MIT

## Author Information

Created by the Maritime Security Operations Center (M-SOC) Engineering Team.
