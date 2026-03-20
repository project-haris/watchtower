# This script is the "brain" of the data collection layer. It consolidates high-frequency, fragmented data from multiple sources (NMEA 2000 and NMEA 0183) into a single, coherent **Vessel State** object.
#It solves the problem of mismatched data rates (e.g., GPS updating at 1Hz, compass at 10Hz, depth at 0.1Hz) by maintaining the "latest known good value" for every parameter and emitting a unified snapshot at a configurable interval (e.g., every 10 seconds).

#!/usr/bin/env python3
"""
Data Aggregator for Project Haris

Consolidates fragmented, high-frequency data from NMEA 2000 and NMEA 0183 streams
into a unified 'VesselState' object suitable for logging and transmission to the M-SOC.
"""

import time
import threading
import logging
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class VesselState:
    """
    A unified data structure representing the current state of the vessel.
    All units are standardized to SI (Metric) where applicable.
    """
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    vessel_id: str = "UNKNOWN"
    
    # Position (WGS84)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    position_source: Optional[str] = None # e.g., 'NMEA2000', 'GPS'
    
    # Navigation
    speed_over_ground_mps: Optional[float] = None # Meters per second
    course_over_ground_rad: Optional[float] = None # Radians
    heading_true_rad: Optional[float] = None # Radians
    
    # Environment
    water_depth_m: Optional[float] = None
    water_temp_c: Optional[float] = None
    
    # Status Flags
    is_moving: bool = False
    data_stale: bool = False

    def to_json(self) -> str:
        """Serialize the state to a JSON string."""
        return json.dumps(self.to_dict())

    def to_dict(self) -> Dict:
        """Convert to dictionary, handling datetime serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        # Convert radians to degrees for human-readable JSON if needed
        if self.course_over_ground_rad is not None:
            data['course_over_ground_deg'] = round(self.course_over_ground_rad * (180 / 3.14159), 2)
        if self.heading_true_rad is not None:
            data['heading_true_deg'] = round(self.heading_true_rad * (180 / 3.14159), 2)
        return data

class DataAggregator:
    def __init__(self, vessel_id: str, snapshot_interval: float = 10.0, callback: Callable[[VesselState], None] = None):
        """
        Initialize the Aggregator.
        
        Args:
            vessel_id (str): Unique identifier for this vessel.
            snapshot_interval (float): How often (seconds) to emit a consolidated state snapshot.
            callback (Callable): A function to call with the VesselState every interval.
        """
        self.vessel_id = vessel_id
        self.snapshot_interval = snapshot_interval
        self.callback = callback
        
        self._state = VesselState(vessel_id=vessel_id)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        
        # Thresholds
        self.STALE_THRESHOLD_SECONDS = 30.0
        self.MOVEMENT_THRESHOLD_MPS = 0.5 # ~1 knot

    def ingest_nmea2000(self, data: Dict):
        """
        Ingest parsed NMEA 2000 data.
        Expected keys: 'type', 'latitude', 'longitude', 'sog', 'cog', 'heading', etc.
        """
        with self._lock:
            self._state.timestamp = datetime.utcnow()
            pgn_type = data.get('type')
            
            if pgn_type == 'position':
                self._state.latitude = data.get('latitude')
                self._state.longitude = data.get('longitude')
                self._state.position_source = "NMEA2000_PGN129025"
            
            elif pgn_type == 'cog_sog':
                # NMEA 2000 usually gives speed in m/s
                self._state.speed_over_ground_mps = data.get('sog')
                # NMEA 2000 usually gives COG in radians
                self._state.course_over_ground_rad = data.get('cog')
                self._update_movement_status()

            elif pgn_type == 'heading':
                self._state.heading_true_rad = data.get('heading')

            # Add more PGN mappings as needed...

    def ingest_nmea0183(self, data: 'NMEAData'):
        """
        Ingest parsed NMEA 0183 data.
        Accepts the NMEAData object from nmea0183_parser.py.
        """
        with self._lock:
            self._state.timestamp = datetime.utcnow()
            
            # Position (NMEA 0183 RMC/GGA)
            if data.latitude is not None:
                self._state.latitude = data.latitude
                self._state.longitude = data.longitude
                self._state.position_source = "NMEA0183"
            
            # Speed (NMEA 0183 usually in knots)
            if data.speed_knots is not None:
                # Convert knots to m/s (1 knot = 0.514444 m/s)
                self._state.speed_over_ground_mps = data.speed_knots * 0.514444
                self._update_movement_status()
            
            # Course (NMEA 0183 usually in degrees True)
            if data.course_over_ground is not None:
                # Convert degrees to radians
                self._state.course_over_ground_rad = data.course_over_ground * (3.14159 / 180)
            
            # Heading
            if data.heading is not None:
                self._state.heading_true_rad = data.heading * (3.14159 / 180)
                
            # Depth
            if data.depth_meters is not None:
                self._state.water_depth_m = data.depth_meters
                
            # Water Temp
            if data.water_temperature is not None:
                self._state.water_temp_c = data.water_temperature

    def _update_movement_status(self):
        """Internal helper to update the is_moving flag."""
        if self._state.speed_over_ground_mps is not None:
            self._state.is_moving = self._state.speed_over_ground_mps > self.MOVEMENT_THRESHOLD_MPS
        else:
            self._state.is_moving = False

    def get_current_state(self) -> VesselState:
        """Returns a snapshot of the current state (thread-safe copy)."""
        with self._lock:
            # Check for stale data
            age = (datetime.utcnow() - self._state.timestamp).total_seconds()
            self._state.data_stale = age > self.STALE_THRESHOLD_SECONDS
            
            # Create a copy to avoid reference issues
            return VesselState(**asdict(self._state))

    def _aggregation_loop(self):
        """The main loop that periodically calls the callback."""
        logger.info(f"Aggregator started. Emitting state every {self.snapshot_interval} seconds.")
        while self._running:
            try:
                # Wait for the interval
                time.sleep(self.snapshot_interval)
                
                # Get snapshot
                snapshot = self.get_current_state()
                
                # Send to callback (e.g., Sync Agent or Database)
                if self.callback:
                    self.callback(snapshot)
                    
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")

    def start(self):
        """Start the background aggregation thread."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._aggregation_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the aggregation thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Aggregator stopped.")

# --- Example Usage ---
if __name__ == "__main__":
    # Mock callback function
    def handle_snapshot(state: VesselState):
        print("\n--- New Snapshot ---")
        print(f"Time: {state.timestamp}")
        print(f"Pos: {state.latitude}, {state.longitude}")
        print(f"Speed: {state.speed_over_ground_mps} m/s (Moving: {state.is_moving})")
        print(f"Source: {state.position_source}")
        if state.data_stale:
            print("!! WARNING: DATA STALE !!")

    # Initialize
    aggregator = DataAggregator(
        vessel_id="HARIS-TEST-01", 
        snapshot_interval=5.0, 
        callback=handle_snapshot
    )
    
    # Start background thread
    aggregator.start()
    
    try:
        # Simulate receiving NMEA 0183 data in the main thread
        from nmea0183_parser import NMEAData # Importing for demo
        
        # Simulate 3 updates
        for i in range(3):
            mock_data = NMEAData(
                latitude=25.0 + i*0.001,
                longitude=-80.0 - i*0.001,
                speed_knots=5.0 + i
            )
            aggregator.ingest_nmea0183(mock_data)
            print(f"Injected NMEA 0183 data {i+1}")
            time.sleep(2)
            
        # Keep running to see snapshots
        print("Aggregator running... Ctrl+C to stop.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        aggregator.stop()

### **Integration Strategy**

# 1.  **Thread Safety**: This script uses a `threading.Lock` to ensure that data from different sensors (which might arrive in different threads) doesn't corrupt the state.
# 2.  **Periodic Snapshots**: Instead of flooding your database or the M-SOC with thousands of messages per second, the aggregator emits a clean, unified snapshot at a fixed interval (e.g., every 10 seconds).
# 3.  **Usage in `harisd`**:
#     ```python
#     # In your main service script
#     def on_state_update(state):
#         # 1. Save to local SQLite/InfluxDB
#         db.save(state.to_dict())
#         # 2. Queue for transmission to M-SOC
#         transmission_queue.put(state.to_json())

#     aggregator = DataAggregator(vessel_id="VESSEL-001", callback=on_state_update)
#     aggregator.start()

#     # When NMEA Parser gets data
#     nmea_data = nmea_parser.read_sentence()
#     if nmea_data:
#         aggregator.ingest_nmea0183(nmea_data)
#     ```