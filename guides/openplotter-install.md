# OpenPlotter v4.x.x — Installation Reference for RPi5 (haris-arthur)

## OS Base

- **Distribution:** Debian 12 (Bookworm)
- **Confirmed on haris-arthur:** `PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"`
- **OpenPlotter requirement:** v4.x.x only works on Debian 12 Bookworm

## Download Links

Official images hosted on OpenMarine Nextcloud:

| Edition | Download | Best For |
|---------|----------|----------|
| **Starting** | https://cloud.openmarine.net/s/TwxS4AJrtTJ485T | Monitor connected — **Ahmed's choice for haris-arthur** |
| **Headless** | https://cloud.openmarine.net/s/cMJrfH45aPeamFc | Remote access via SSH/RDP |
| **Touchscreen** | https://cloud.openmarine.net/s/3gjyKsrpKRb6ZHe | DSI touchscreen displays |

## Default Credentials

| Field | Value |
|-------|-------|
| Hostname | `openplotter` |
| User | `pi` |
| Password | `raspberry` |
| SSH (Headless) | Enabled |
| Wi-Fi AP (Headless) | SSID: `openplotter`, Password: `12345678`, IP: `10.42.0.1` |

## Install Steps

1. Download the `.img.xz` file from the link above
2. Use **Raspberry Pi Imager** (latest version — old versions don't support RPi5)
3. Click "Choose OS" → scroll to bottom → "Use Custom" → select the downloaded image
4. Click "Choose Storage" → select your SD card
5. Click "Write"
6. Insert SD card into RPi5 and boot

## Post-Install: Haris Provisioning

After OpenPlotter is running on the RPi5, use the watchtower Ansible playbook to deploy the Haris stack:

```bash
# From the Ansible controller
ansible-playbook playbooks/group_vessel_edge/main.yml -l haris-arthur -D
```

The haris-arthur host vars set `haris_openplotter_mode: true`, which means Ansible skips Signal K and CAN boot config (OpenPlotter manages those) but still deploys the haris data collector, Filebeat, and Zabbix agent.

## Required OpenPlotter Config for McArthur HAT

After OpenPlotter is installed, configure CAN and serial from the OpenPlotter dashboard:

**CAN Bus (NMEA 2000):**
- Open CAN Bus app → MCP251xfd tab
- Add device: Interface=SPI0 CE1, Oscillator=20000000, Interrupt=GPIO 25 (pin 22)
- Reboot
- Open CAN Bus app again — toggle **"Add Connection to Signal K"** for the device
- Verify: browser → `http://<hostname>:3000` → Server → Connections → NMEA 2000 on `can0` enabled

**Serial (NMEA 0183):**
- Open Serial app → Enable UART2 (/dev/ttyAMA2) for TX/RX 1
- Enable UART4 (/dev/ttyAMA4) for TX/RX 2 (optional)
- Reboot → Assign aliases → Add serial connections to Signal K

**External NMEA 0183 Device (e.g. Arduino dGPS):**

For USB-connected serial devices (Arduino, USB GPS dongle), the device appears as a USB serial port and is managed via udev rules, not the McArthur HAT screw terminals.

On haris-arthur, the Arduino dGPS was set up as follows:

**1. Identify the Arduino USB serial:**
```bash
lsusb
# Look for: Vendor 2341 (Arduino), Product 0043
dmesg | grep -i "arduino\|usb.*tty"
```

**2. Create a persistent udev rule** so the device always gets the same symlink regardless of USB port:

```bash
sudo nano /etc/udev/rules.d/10-openplotter.rules
```

Add a line matching your device's vendor, product, and serial:
```
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341",ATTRS{idProduct}=="0043",ATTRS{serial}=="14238313834351A06212",SYMLINK+="ttyOP_gps",MODE="0666"
```

Reload udev:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**3. Configure in Signal K:**

The device appears at `/dev/ttyOP_gps`. Add it as an NMEA 0183 provider in Signal K settings (`~/.signalk/settings.json`) or via the OpenPlotter Serial app:

| Setting | Value |
|---------|-------|
| Device | `/dev/ttyOP_gps` |
| Type | `serial` |
| Protocol | `NMEA0183` |
| Baud rate | `9600` |
| Validate checksum | `true` |

> **Note:** This particular Arduino dGPS used **9600 baud**, not the standard NMEA 0183 4800. Adjust baud rate to match your device's firmware configuration.

**4. Verify:**
```bash
cat /dev/ttyOP_gps
```
Should show NMEA 0183 sentences like `$GPGGA`, `$GPRMC`, `$GPGSA`, etc. Then check Signal K:
```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq '.navigation.position'
```

> **Note:** When the device is disconnected while powered, the symlink breaks (`ls: cannot access '/dev/ttyOP_gps': No such file or directory`) and Signal K stops receiving NMEA data — that's expected. Reconnect USB and it resumes automatically.

## Required OpenPlotter Config for PiCAN-M HAT

For haris-sinilind (PiCAN-M), configure CAN and serial from the OpenPlotter dashboard:

**CAN Bus (NMEA 2000):**
- Open CAN Bus app → **MCP2515** tab (different chipset from McArthur)
- Add device: Interface=**SPI0 CE0**, Oscillator=**16000000**, Interrupt=**GPIO 25**
- Reboot
- Open CAN Bus app again — toggle **"Add Connection to Signal K"** or **"Signal K"** for the `can0` device
- Verify: browser → `http://<hostname>:3000` → Server → Connections → NMEA 2000 on `can0` enabled

**Serial (NMEA 0183):**
- Open Serial app → Enable **ttyS0** (onboard UART, GPIO 14/15)
- Reboot → Assign an alias (e.g. `pican-nmea0183`)
- Add serial connection to Signal K at **4800 baud**

**Key differences from McArthur HAT:**
| Feature | PiCAN-M | McArthur |
|---------|---------|----------|
| Chip | **mcp2515** | mcp251xfd |
| SPI | **CE0** | CE1 |
| Oscillator | **16 MHz** | 20 MHz |
| Interrupt | **GPIO 25** | GPIO 25 |
| NMEA 0183 | **ttyS0** | ttyAMA2 / ttyAMA4 |

> **Note:** If you're provisioning haris-sinilind via Ansible and OpenPlotter is managing CAN/serial, set `haris_openplotter_mode: true` in the host vars to tell the Ansible role to skip its own CAN and Signal K setup (same as haris-arthur).

## Troubleshooting

### OpenPlotter Fresh Install: NodeSource `apt update` Failure

**Symptom:** Fresh OpenPlotter install fails on `apt update` because `/etc/apt/sources.list.d/openplotterNodejs.list` points at a NodeSource release path returning `404`.

```
Err: https://deb.nodesource.com/node_18.x bookworm Release
  404 Not Found
E: The repository 'https://deb.nodesource.com/node_18.x bookworm Release' no longer has a Release file.
```

A variant shows a `Signed-By` conflict when two source files point at `node_22.x` with incompatible formats:

```
E: Conflicting values set for option Signed-By regarding source https://deb.nodesource.com/node_22.x/ nodistro: /etc/apt/keyrings/nodesource.gpg !=
E: The list of sources could not be read.
```

**Cause:** NodeSource removed the `node_18.x` repository, and OpenPlotter images still reference it. After an update bumps Node from 18 to 22, leftover `.bak` files and duplicate source entries create `Signed-By` conflicts.

**Recovery (handles both symptoms):**

```bash
# 1. Install prerequisites and refresh the NodeSource GPG key
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

### Signal K: `Failed to load native canSocket module`

**Symptom:** Signal K logs show:

```
Failed to load native canSocket module: Cannot find module '../build/Release/can...
```

The NMEA 2000 / CAN connection in Signal K won't work, and no CAN data appears in Signal K paths.

**Cause:** The `@canboat/canboatjs` native addon was not compiled during npm install. The package's `binding.gyp` defines a native C++ addon for raw CAN socket access, but the `node-gyp rebuild` step failed or was skipped (often because build tools were missing at install time, or Node.js was updated afterward).

**Fix:** Rebuild the native addon and restart Signal K:

```bash
cd /usr/lib/node_modules/signalk-server/node_modules/@canboat/canboatjs
sudo npm rebuild
sudo systemctl restart signalk
```

Verify:
```bash
journalctl -u signalk --no-pager | grep -i "canSocket\|canboat"
```

Expected output shows the native module loaded without error.

> **Note:** Requires `build-essential` (gcc, make, python3) on the system. If missing: `sudo apt install build-essential python3`.

**Reference:** https://forum.openmarine.net/showthread.php?tid=7036&pid=36998

### Signal K: `Unable to sign token: secretOrPrivateKey must have a value`

**Symptom:** Signal K shows the following error:

```
Unable to sign token: secretOrPrivateKey must have a value
```

**Fix:** Disable or reset security by removing the `security` strategy block from `settings.json` (usually at `$HOME/.signalk/settings.json`).

Remove this section:

```json
"security": {
  "strategy": "./tokensecurity"
},
```

If the server is started with the `--securityenabled` argument, remove that as well. After updating the configuration, restart Signal K.

## References

- OpenPlotter docs: https://openplotter.readthedocs.io/latest/getting_started/downloading.html
- MacArthur HAT NMEA 2000 setup: https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea2000.html
- MacArthur HAT diagrams: https://github.com/OpenMarine/MacArthur-HAT/tree/main/images
  - Pinout/block diagram: https://raw.githubusercontent.com/OpenMarine/MacArthur-HAT/main/images/macarthur-diagram.png
- watchtower haris-arthur host vars: `playbooks/group_vessel_edge/host_vars/haris-arthur.yml`
