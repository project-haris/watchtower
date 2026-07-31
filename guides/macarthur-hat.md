# MacArthur HAT — Alternative OpenMarine HAT for Haris

**Source:** OpenMarine / OpenPlotter project — https://github.com/OpenMarine/MacArthur-HAT  
**Docs:** https://macarthur-hat-documentation.readthedocs.io/en/latest/  
**User bookmarks:** /root/hermes-vault/user-notes/macarthur-hat-links.md

## Overview

The MacArthur HAT is a Raspberry Pi add-on board designed by Adrian Studer & Sailoog for the OpenMarine/OpenPlotter ecosystem. Named after Ellen MacArthur, it provides broad multi-protocol marine connectivity. Unlike the PiCAN-M HAT (which focuses on NMEA 2000 + 0183), MacArthur adds Seatalk, 1-Wire, I²C, and optional MAIANA AIS integration — making it a research/exploration HAT for Haris.

## Key Differences vs PiCAN-M HAT

| Feature | PiCAN-M HAT (Production) | MacArthur HAT (Research) |
|---------|--------------------------|--------------------------|
| NMEA 2000 | CAN via SPI, MCP2515 | CAN via SPI0-1, optional 120Ω term |
| NMEA 0183 | Serial /dev/ttyS0 | 2× opto-isolated inputs + 2× outputs via UART2/UART4 |
| Seatalk1 | ❌ | ✅ Dedicated input (can also be GPIO) |
| 1-Wire | ❌ | ✅ DS18B20 connector (engine/exhaust/fridge) |
| I²C | ❌ | ✅ STEMMA QT / Qwiic (IMU, temp, pressure, humidity) |
| AIS | ❌ | Optional MAIANA via UART0 |
| Power | External 5V USB-C | Optional 12V→5V DC/DC module (ship battery direct), smart auto on/off |
| Stackable | ❌ | ✅ Works with Moitessier HAT, dAISy HAT, Pypilot |
| Software | marine_haris (custom Python) | OpenPlotter GUI config + Signal K |
| Isolation | NMEA 0183 isolated on some revisions | NMEA 0183 inputs opto-isolated; N2K non-isolated |
| Drivers | Kernel SPI/UART | None needed (OpenPlotter) |
| OS | Debian + systemd | OpenPlotter 3.x/4.x (RPi 3/4/5) |

## Data Flow (if used with Haris)

```
NMEA 2000 ──→ SPI0-1 CAN Interface ──┐
2× NMEA 0183 ──→ UART2/UART4 (opto) ──┤
Seatalk1 ──→ Dedicated input ────────┤
1-Wire (DS18B20) ──→ GPIO ──────────┤──→ OpenPlotter / Signal K → marine_haris
I²C Sensors ──→ STEMMA QT/Qwiic ────┤
MAIANA AIS (opt) ──→ UART0 ────────┘
                                     ↓
                              12V Ship Power → Smart Auto On/Off
```

## Hardware Specs

- **Compatibility:** RPi 3 (no 0183), RPi 4, RPi 5
- **N2K connector:** Screw terminals + optional 120Ω termination jumper
- **0183 wiring:** 2× opto-isolated inputs, 2× non-isolated outputs
- **Power module (optional):** 12V→5V DC/DC, SD card protection, GPIO-triggered shutdown
- **Grounding:** MUST connect 12V/GND to ship ground before other connections (non-isolated design)

## Relevance to Project Haris

The MacArthur HAT represents an **alternative/research path** for the Haris edge node — broader sensor support at the cost of relying on OpenPlotter for configuration rather than the custom `marine_haris` stack. It's useful for:
- Vessels with legacy Seatalk1 instruments
- Environmental monitoring (1-Wire temp, I²C sensors)
- AIS integration without a separate dAISy HAT
- Testing against PiCAN-M as a comparison baseline

Current production deployment (`haris-sinilind`) uses PiCAN-M HAT exclusively.
