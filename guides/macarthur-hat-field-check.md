# MacArthur HAT Field Check

Use this checklist on the Raspberry Pi after OpenPlotter is configured and the playbook has run.

## 1. Confirm CAN Interface

```bash
ip -details link show can0
```

Pass signs:
- `can0` exists.
- State includes `UP`.
- State includes `LOWER_UP`.
- CAN state is `ERROR-ACTIVE`.
- Bitrate is `250000`.
- Driver line includes `mcp251xfd`.
- Clock is `20000000`.
- Parent device is `spi0.1`.

Good example:

```text
can0: <NOARP,UP,LOWER_UP,ECHO>
can state ERROR-ACTIVE
bitrate 250000
mcp251xfd
clock 20000000
parentbus spi parentdev spi0.1
```

Meaning:
- `spi0.1` means the HAT is using `SPI0 CE1`, which is the correct MacArthur NMEA 2000 interface.

Fail signs:
- `Device "can0" does not exist`
- Missing `mcp251xfd`
- Parent device is not `spi0.1`
- State is `DOWN`

## 2. Check Raw NMEA 2000 Traffic

```bash
sudo candump can0
```

> **Pitfall (candump `-L`)**: to log frames to a file use `candump can0 -L >> file.log` — `-L` outputs "log file format" to **stdout** and takes NO file argument (`candump -L /path` fails with *"name of CAN device ... is too long"*). Production capture: `haris-canraw` service (see `references/raw-data-preservation.md`).

Pass sign:
- CAN frames scroll when connected to a powered NMEA 2000 network.

Example:

```text
can0  09F8027F   [8]  ...
can0  19F51323   [8]  ...
```

If nothing appears:
- Confirm the NMEA 2000 backbone is powered.
- Confirm CAN-H and CAN-L wiring.
- Confirm the backbone has proper termination.
- Confirm the MacArthur CAN interface was added in OpenPlotter CAN Bus.

Stop the command with `Ctrl+C`.

## 3. Check Kernel Detection

```bash
dmesg | grep -Ei "mcp251xfd|can0|spi"
```

Pass signs:
- Logs mention `mcp251xfd`.
- Logs mention `can0`.
- No repeated probe or SPI errors.

## 4. Confirm Pi 5 NMEA 0183 UARTs

For Raspberry Pi 5 with MacArthur HAT:
- TX/RX 1 uses UART2, commonly `/dev/ttyAMA2`.
- TX/RX 2 uses UART4, commonly `/dev/ttyAMA4`.

Configure this from the OpenPlotter dashboard:
- Open `OpenPlotter Serial`.
- Go to the UART / device setup area.
- Enable the Raspberry Pi 5 UARTs for the MacArthur HAT.
- Enable `UART2` for TX/RX 1.
- Enable `UART4` for TX/RX 2.
- Reboot when OpenPlotter asks for it.
- Return to `OpenPlotter Serial`.
- Assign a clear alias to each detected port, for example `macarthur-nmea0183-1` and `macarthur-nmea0183-2`.
- Add the needed serial connection to Signal K from OpenPlotter Serial.

```bash
ls -l /dev/ttyAMA2 /dev/ttyAMA4
```

Pass sign:
- The UART device you configured in OpenPlotter exists.

If missing:
- Open OpenPlotter Serial.
- Enable the correct UARTs for Raspberry Pi 5.
- Reboot and check again.

## 5. Check Signal K Service

```bash
systemctl status signalk --no-pager
```

Pass sign:
- Service is `active (running)`.

Check API:

```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq
```

Pass signs:
- Command returns JSON.
- After sensors are connected, paths appear under areas like `navigation`, `environment`, `electrical`, or `propulsion`.

If `jq` is missing:

```bash
curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self
```

## 6. Check Signal K CAN Connection

Open Signal K in a browser:

```text
http://haris-arthur:3000
```

Then check:

```text
Server -> Connections
```

Pass signs:
- There is an enabled NMEA 2000 / CAN connection.
- The interface is `can0`.

If raw `candump can0` works but Signal K has no data:
- The HAT is working.
- The issue is likely Signal K or OpenPlotter CAN connection setup.
- Recheck the OpenPlotter CAN Bus Signal K connection.

## 7. Check Haris Collector

```bash
systemctl status harisd --no-pager
```

Pass sign:
- Service is `active (running)`.

Check snapshots:

```bash
sudo tail -n 5 /opt/haris/logs/signalk_snapshots.jsonl
```

Pass signs:
- New JSON lines appear every few seconds.
- `vessel_id` and `vessel_name` match the host vars.
- Signal K paths appear inside the `signalk` object.

## 8. Check Filebeat

```bash
systemctl status filebeat --no-pager
sudo filebeat test config
sudo filebeat test output
```

Pass signs:
- Service is `active (running)`.
- `Config OK`.
- Output test succeeds.

## 9. Quick All-In-One Check

```bash
echo "## CAN"; ip -details link show can0
echo "## RAW CAN: press Ctrl+C after a few frames"; sudo timeout 10 candump can0
echo "## SIGNAL K"; curl -s http://127.0.0.1:3000/signalk/v1/api/vessels/self | jq '.uuid, .navigation, .environment, .electrical'
echo "## HARIS"; systemctl is-active harisd; sudo tail -n 2 /opt/haris/logs/signalk_snapshots.jsonl
echo "## FILEBEAT"; systemctl is-active filebeat; sudo filebeat test config
```

## 10. Expected OpenPlotter MacArthur Settings

In OpenPlotter CAN Bus:
- Device type: `MCP251xfd`
- Interface: `SPI0 CE1`
- Oscillator: `20000000`
- Interrupt: `GPIO 25`
- Signal K connection: enabled on `can0`

In OpenPlotter Serial for Raspberry Pi 5:
- TX/RX 1: `UART2` / `/dev/ttyAMA2`
- TX/RX 2: `UART4` / `/dev/ttyAMA4`
- Enable these from the OpenPlotter Serial dashboard, reboot, assign aliases, then add the serial ports to Signal K from the same app.

References:
- https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea2000.html#configuration
- https://macarthur-hat-documentation.readthedocs.io/en/latest/nmea0183.html#configuration
