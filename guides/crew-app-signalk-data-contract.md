# Haris Crew App — Signal K Data Contract

The crew app (Flutter/Android) ingests real-time vessel data via a Signal K WebSocket and renders it on dashboard gauges. This document defines the exact protocol so synthetic sources (like `ais-generator`) can feed it identically.

## Connection

```
ws://<host>:<port>/signalk/v1/stream?subscribe=none
```

Defaults: `haris-sinilind:3000` (hardcoded in `AppConstants`).

## Subscription Flow

1. Connect via WebSocket with `?subscribe=none` query param
2. Send a subscription message:
   ```json
   {"context": "vessels.self", "subscribe": [{"path": "navigation.*", "period": 1000, "format": "delta"}]}
   ```
3. Server begins streaming delta messages for **all** vessels (not just "self")

## Delta Message Format

Parsed by `VesselDataModel.fromSignalkDelta()` at `lib/data/models/vessel_data_model.dart`:

```json
{
  "context": "vessels.urn:mrn:signalk:uuid:<MMSI>",
  "updates": [{
    "timestamp": "2026-05-30T12:00:00Z",
    "values": [
      {"path": "navigation.position", "value": {"latitude": 59.44, "longitude": 24.76}},
      {"path": "navigation.speedOverGround", "value": 14.0},
      {"path": "navigation.courseOverGroundTrue", "value": 180.0},
      {"path": "navigation.headingTrue", "value": 178.0}
    ]
  }]
}
```

### Supported paths (from `fromSignalkDelta` switch cases)

| Signal K Path | Model Field | Type |
|---|---|---|
| `navigation.position` | `latitude`, `longitude` | `{"latitude": float, "longitude": float}` |
| `navigation.speedOverGround` | `speedOverGround` | float (knots) |
| `navigation.headingTrue` | `heading` | float (degrees) |
| `navigation.courseOverGroundTrue` | — | float (degrees, ignored in model) |
| `environment.depth.belowTransducer` | `depth` | float (meters) |
| `propulsion.port.revolutions` | `engineRpm` | float (RPM) |
| `environment.wind.speedApparent` | `windSpeed` | float (m/s or kn) |
| `environment.wind.angleApparent` | `windAngle` | float (degrees) |
| `environment.outside.temperature` | `temperatureOutside` | float (°C) |

Minimum viable delta: `navigation.position` + `navigation.speedOverGround` + `navigation.headingTrue`. The merge function at `VesselDataModel.merge()` is additive — missing paths leave the previous value intact.

## HTTP Discovery Endpoint

The crew app does NOT use this (it connects directly to a known host:port), but standard Signal K clients expect:

```
GET /signalk/v1/api/
```

Returns vessel metadata:
```json
{
  "self": "vessels.urn:mrn:signalk:uuid:999001001",
  "vessels": {
    "urn:mrn:signalk:uuid:999001001": {
      "name": "SYNTH-ALPHA",
      "mmsi": "999001001",
      "type": "passenger",
      "design": {"draft": {"value": 6.5, "units": "m"}, "beam": {"value": 30, "units": "m"}, "length": {"value": 210, "units": "m"}}
    }
  }
}
```

## Crew App Data Flow

```
Signal K Server (WS) → SignalkWsDatasource → VesselDataModel (delta parse)
                                              → StreamController<VesselDataModel> (broadcast)
                                              → VesselDataProvider (Riverpod StateNotifier)
                                              → Dashboard UI (gauges, position, connection status)
```

- Reconnect: exponential backoff (1s initial → 60s max, doubles per attempt)
- Stale threshold: 15s (`staleDataThreshold`)
- Configurable host/port via Settings page (persisted in SharedPreferences)

## Running the AIS Generator as a Source

```bash
cd /root/workspace/ais-generator
source .venv/bin/activate
python -m src.main start
# Listens on 0.0.0.0:3456, accessible at ws://<tailscale-ip>:3456/signalk/v1/stream?subscribe=none
```

In the crew app Settings, change:
- **Signal K Host** → Tailscale IP (e.g. 100.72.133.89)
- **Signal K Port** → 3456

The crew app treats it identically to the real vessel's Signal K server — same delta format, same subscription flow, same gauge rendering.

## Known Issues

### Settings changes ignored (serverConfigProvider not wired to settingsProvider)

**Symptom:** User changes host/port in Settings → Dashboard stays on "Loading" or silently connects to old server. Connection indicator may never turn green.

**Root cause:** `lib/presentation/providers/vessel_data_provider.dart` had a `serverConfigProvider` declared as `StateProvider` returning hardcoded `AppConstants.defaultSignalkUrl:defaultSignalkPort`. This provider never watched `settingsProvider` — the provider that Settings page writes to. Changing host/port in the UI had zero effect on the actual connection target.

```dart
// BROKEN: hardcoded defaults, never updates
final serverConfigProvider = StateProvider<({String host, int port})>((ref) {
  return (host: AppConstants.defaultSignalkUrl, port: AppConstants.defaultSignalkPort);
});
```

**Fix applied May 2026 (3 changes to `vessel_data_provider.dart`):**

1. Changed `serverConfigProvider` from `StateProvider` (immutable) to `Provider` that watches `settingsProvider`:
   ```dart
   final serverConfigProvider = Provider<({String host, int port})>((ref) {
     final settings = ref.watch(settingsProvider);
     return (host: settings.signalkHost, port: settings.signalkPort);
   });
   ```

2. Changed connection-on-startup to always disconnect-first then reconnect (so config changes trigger a fresh connection instead of being gated by `disconnected` status):
   ```dart
   Future.microtask(() {
     if (repo.currentConnectionStatus != VesselConnectionStatus.disconnected) {
       repo.disconnect();
     }
     Future.delayed(const Duration(milliseconds: 100), () {
       repo.connect(host: config.host, port: config.port);
     });
   });
   ```

3. Added import `import 'package:haris_crew/presentation/providers/settings_provider.dart';`.

**Verification:** Open Settings → change host/port → navigate to Dashboard → connection indicator transitions: disconnected (red) → connecting (amber spinner) → connected (green) → gauges populate with data from the new server within 1-2 ticks of the Signal K update interval.
