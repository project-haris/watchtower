# Ansible Role: Node-RED

## Description

This role installs Node-RED on Debian-based edge devices using the official Node-RED Linux installer documented for Raspberry Pi and other Debian systems:

- installs `build-essential`, `curl`, and `git`
- downloads the official `update-nodejs-and-nodered-deb` installer
- runs the installer non-interactively for the configured Node-RED user
- enables and starts the `nodered` systemd service

## Requirements

- Debian, Ubuntu, Raspberry Pi OS, or another Debian-based system
- network access to GitHub, NodeSource, npm, and other upstreams used by the official installer
- the configured `nodered_user` must already exist on the target host

## Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `nodered_script_url` | `"https://github.com/node-red/linux-installers/releases/latest/download/update-nodejs-and-nodered-deb"` | Official Node-RED Debian installer URL |
| `nodered_script_path` | `"/usr/local/sbin/update-nodejs-and-nodered-deb"` | Where the installer is stored on the host |
| `nodered_user` | `"haris"` | User account that owns the Node-RED runtime and flows |
| `nodered_install_pi_nodes` | `true` | Whether to install the Raspberry Pi specific nodes |
| `nodered_enable_service` | `true` | Enable Node-RED at boot |
| `nodered_start_service` | `true` | Start Node-RED after installation |
| `nodered_force_reinstall` | `false` | Re-run the installer even if `node-red` already exists |
| `nodered_nodejs_major` | `"22"` | Node.js major version flag passed to the installer |
| `nodered_service_name` | `"nodered"` | systemd service name managed by the role |

## Example Run

Run only the Node-RED role on vessel edge devices:

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -t nodered -D
```

Target a single host if you want to test it first:

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-sinilind -t nodered -D
```

## Notes

- This role follows the official Node-RED Raspberry Pi/Debian installer flow from `https://nodered.org/docs/getting-started/raspberrypi`.
- The official docs currently say the installer ensures Node.js is new enough and installs Node.js 22 LTS when it needs to install Node.js itself.
- By default, this repo installs Node-RED under the existing `haris` user so its runtime data stays aligned with the rest of the vessel stack.
- If you want to re-run the upstream installer on a host that already has Node-RED, set `nodered_force_reinstall: true`.
