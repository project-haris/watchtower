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
| `haris_openplotter_mode` | `false` | Compatibility base mode for OpenPlotter-managed hosts. The default derived behavior is to stop managing Signal K install/service and CAN boot/networking, but you can override the split ownership flags below. |
| `haris_manage_signalk_install` | `{{ not haris_openplotter_mode }}` | Install the Signal K package/runtime. |
| `haris_manage_signalk_service` | `{{ not haris_openplotter_mode }}` | Create and manage the role-owned `signalk.service` unit. |
| `haris_manage_signalk_config` | `{{ not haris_openplotter_mode }}` | Manage selected non-security Signal K `settings.json` values such as vessel identity and interface settings. |
| `haris_manage_can_boot_config` | `{{ not haris_openplotter_mode }}` | Manage Raspberry Pi boot overlay lines for the CAN HAT. |
| `haris_manage_can_networking` | `{{ not haris_openplotter_mode }}` | Manage `/etc/network/interfaces.d/can0`. |
| `haris_can_boot_config_lines` | `["# --- Project Haris PiCAN Config ---", "dtparam=spi=on", "dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25"]` | Lines written to Raspberry Pi `config.txt` to enable the CAN HAT overlay. Override per host for different HATs. |
| `haris_can_bitrate` | `250000` | CAN bitrate used in `/etc/network/interfaces.d/can0`. |

### OpenPlotter Compatibility Mode

Set `haris_openplotter_mode: true` on hosts where OpenPlotter manages hardware. You can then choose whether the role should still manage Signal K configuration.

With the default derived settings for this mode, the role intentionally avoids reconfiguring core OpenPlotter-managed components:
- Skips Signal K installation and the role-managed `signalk.service`.
- Skips CAN overlay writes to `/boot/firmware/config.txt` or `/boot/config.txt`.
- Skips CAN overlay-triggered reboot logic.
- Skips writing `/etc/network/interfaces.d/can0` and associated `ifupdown` CAN bring-up.

You can override that default split, but be careful: on OpenPlotter hosts `settings.json`
is OpenPlotter-owned and contains live piped providers (gps, can0, ...), security, and ssl.
The role's `signalk_settings.json.j2` is a minimal skeleton — templating it over
OpenPlotter's file **drops all of that**. The safe repo touch on OpenPlotter hosts is the
idempotent `sim-tcp` merge from `simulator_bridge.yml` (gated by
`haris_simulator_bridge_enabled`), which preserves everything else. This repo currently
sets `haris_manage_signalk_config: false` on its OpenPlotter hosts (haris-sinilind,
haris-arthur).

```yaml
haris_openplotter_mode: true
haris_manage_signalk_install: false
haris_manage_signalk_service: false
haris_manage_signalk_config: false   # do NOT template OpenPlotter-owned settings.json
haris_manage_can_boot_config: false
haris_manage_can_networking: false
haris_signalk_config_dir: "/home/pi/.signalk"
```

What still runs in this mode:
- System/user preparation required by Haris runtime.
- Haris collector deployment and `harisd` service management.
- Filebeat installation/config/service management when `haris_filebeat_enabled: true`.
- Any explicitly enabled split Signal K tasks, such as `haris_manage_signalk_config: true`.

Why this mode exists:
- OpenPlotter commonly manages CAN, serial/UART, and Signal K through its own tools and package flows.
- Letting both systems manage the same components can cause configuration drift, unexpected reboots, or service conflicts.

Recommended host vars pattern on OpenPlotter:
```yaml
haris_openplotter_mode: true
haris_manage_signalk_install: false
haris_manage_signalk_service: false
haris_manage_signalk_config: false   # OpenPlotter owns settings.json
haris_manage_can_boot_config: false
haris_manage_can_networking: false
haris_signalk_config_dir: "/home/pi/.signalk"
haris_nmea0183_port: "/dev/ttyAMA2"   # Pi 5 MacArthur TX/RX 1 (UART2)
haris_nmea2000_interface: "can0"      # Keep aligned with OpenPlotter CAN interface name
```

For MacArthur NMEA 2000 setup in the OpenPlotter CAN Bus app, choose the MCP251xfd device settings documented by MacArthur:
- Interface: `SPI0 CE1`
- Oscillator: `20000000`
- Interrupt: `GPIO 25`

If both `SPI0 CE0` and `SPI0 CE1` are shown, select `SPI0 CE1`. The MacArthur HAT NMEA 2000 CAN controller is wired to SPI0 chip-select 1.
Reference: https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea2000.html#configuration

### CAN HAT Profiles (PiCAN-M vs MacArthur)

Use host-specific overrides in `host_vars` when the vessel hardware differs.

| HAT | CAN overlay (`haris_can_boot_config_lines`) | NMEA 0183 serial note | Notes |
| :--- | :--- | :--- | :--- |
| PiCAN-M | `dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25` | Usually `/dev/ttyS0` | Default profile used by this role. |
| MacArthur HAT v1.2 | `dtoverlay=mcp251xfd,spi0-1,interrupt=25` | Depends on Pi model and enabled UARTs | MacArthur NMEA2000 uses MCP251xfd on SPI0 CE1 (GPIO 25 interrupt). |

Example host override for MacArthur:

```yaml
haris_can_boot_config_lines:
  - "# --- Project Haris MacArthur HAT Config ---"
  - "dtparam=spi=on"
  - "dtoverlay=mcp251xfd,spi0-1,interrupt=25"
```

For MacArthur NMEA 0183, UART mapping in docs is:
- Raspberry Pi 4: TX/RX 1 on UART3, TX/RX 2 on UART5
- Raspberry Pi 5: TX/RX 1 on UART2, TX/RX 2 on UART4
  (exact section reference: https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea0183.html#configuration)

Set `haris_nmea0183_port` to the actual Linux device exposed on your target host after enabling those UARTs.
For Raspberry Pi 5, a common mapping is:
- TX/RX 1 (UART2) -> `/dev/ttyAMA2`
- TX/RX 2 (UART4) -> `/dev/ttyAMA4`

Current repository example for MacArthur on Raspberry Pi 5:
- [playbooks/group_vessel_edge/host_vars/haris-arthur.yml](/home/ahmed/maritime/project-haris/watchtower/playbooks/group_vessel_edge/host_vars/haris-arthur.yml) sets `haris_nmea0183_port: "/dev/ttyAMA2"`.
- The same host example points `haris_signalk_config_dir` at `/home/pi/.signalk` so OpenPlotter's live Signal K `settings.json` is the one being managed.
- The same host example enables `haris_openplotter_mode: true` so OpenPlotter keeps control of hardware bring-up while the repo can still manage selected non-security `settings.json` values if desired.

### Configuration Sources

- PiCAN-M MCP2515 overlay convention (`mcp2515-can0`, 16MHz, GPIO 25): Raspberry Pi overlay usage pattern and role default legacy behavior in this repository.
- MacArthur HAT NMEA2000 config (`MCP251xfd`, `SPI0 CE1`, `GPIO 25`, 20MHz reference in OpenPlotter UI):  
  https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea2000.html
- MacArthur HAT NMEA0183 UART mapping by Pi model (Pi 4: UART3/UART5, Pi 5: UART2/UART4):  
  https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea0183.html#configuration

### Signal K Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_signalk_version` | `"2.23.0"` | Version of Signal K Server to install. |
| `haris_signalk_port` | `3000` | Port for the Signal K web interface and API. |
| `haris_signalk_config_dir` | `{{ haris_home }}/.signalk` | Signal K configuration directory containing `settings.json`. Override this on OpenPlotter hosts, for example to `/home/pi/.signalk`. |

Signal K admin credentials are not managed by this role via `settings.json`. Current Signal K security state is stored in `security.json`, and admin user creation/password management should be done through Signal K's supported security flows such as the Admin UI or documented runtime options.

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

### Simulator HTTP Bridge (bench NMEA 0183 over URL)

Enables a bench simulator (or any HTTP POST source of NMEA 0183 lines) to stream into
Signal K without CAN hardware, tailnet membership, or firewall changes. Architecture:

```text
simulator → https://<host>.<tailnet>.ts.net/ (Tailscale Funnel, optional)
  → hub HTTP :8080 → hub TCP :10130 (replay last 10 on connect)
  → Signal K pipedProvider "sim-tcp" (TcpProvider client) → model → harisd → ELK
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `haris_simulator_bridge_enabled` | `false` | Deploy the hub script, `simulator-bridge` systemd unit, and merge the `sim-tcp` piped provider into Signal K settings. |
| `haris_simulator_bridge_http_port` | `8080` | HTTP POST port the simulator targets. |
| `haris_simulator_bridge_tcp_port` | `10130` | TCP port Signal K's `TcpProvider` dials (hub listener). |
| `haris_simulator_funnel_enabled` | `false` | Issue the Tailscale cert and run `tailscale funnel --bg` to expose the bridge publicly. **Requires the `funnel` node attribute in the tailnet policy (admin console, one-time).** |
| `haris_simulator_firewall_open` | `false` | Open the HTTP port in firewalld — only needed when the simulator is on the same LAN and NOT using Funnel/tailnet. |

Pitfalls encoded in the merge script (`files/merge_sim_tcp_provider.py`) and hub
(`files/http_bridge.py`): the legacy Signal K TCP input port 10110 is orphaned in
signalk-server 2.30 (accepts but never processes), the working input mechanism is the
`TcpProvider` piped provider (Signal K dials OUT), `suppress0183event: true` is required,
and sentences need CRLF + a `$` prefix. Full reference: the `project-haris` skill,
`references/simulator-http-bridge-setup.md`.

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
5.  **Post-Playbook MacArthur HAT Validation**:
    Run these checks after the playbook completes (and after reconnecting if a reboot occurred):
    ```bash
    # 1) Confirm CAN overlay is present in boot config
    grep -n "mcp251xfd\|spi0-1" /boot/firmware/config.txt /boot/config.txt 2>/dev/null

    # 2) Confirm CAN interface exists
    ip -details link show can0

    # 3) Bring CAN up at expected bitrate and verify
    sudo ip link set can0 up type can bitrate 250000
    ip -details link show can0

    # 4) Check kernel probe logs for MacArthur CAN controller
    dmesg | rg -i "mcp251xfd|can0|spi"

    # 5) Verify Pi 5 UART device nodes used for NMEA0183
    ls -l /dev/ttyAMA2 /dev/ttyAMA4
    ```
    Expected results:
    - `can0` exists and can be brought `UP`.
    - `dmesg` shows MCP251xfd initialization without probe errors.
    - `/dev/ttyAMA2` exists when using MacArthur TX/RX 1 on Raspberry Pi 5.
6.  **Check SOC Forwarding**:
    Verify that Citadel is listening on TCP `5044` for Beats traffic. Enable `haris_soc_forward_enabled` only if you also want the legacy direct TCP `5045` path.
7.  **Check Firewall**:
    ```bash
    sudo firewall-cmd --state
    sudo firewall-cmd --zone=tailscale --list-all
    ```
8.  **Access Dashboards**:
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
