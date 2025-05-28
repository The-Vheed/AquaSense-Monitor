import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import json
import os
import sys

# Add the parent directory to sys.path to allow importing from common
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import Config
from common.models import SensorReading, Anomaly

app = FastAPI(
    title="Anomaly Detector API",
    description="Receives sensor data, detects anomalies, and stores them.",
    version="1.0.0",
)

# - Global State Management
# Store recent anomalies (max size defined in config)
recent_anomalies: deque[Anomaly] = deque(maxlen=Config.MAX_ANOMALIES_TO_STORE)

# Store the last known reading timestamp for dropout detection
last_reading_timestamps: Dict[str, datetime] = {}
last_processed_reading_timestamp: Optional[datetime] = None

# Store recent readings for drift detection (per sensor_id and parameter)
# Format: {sensor_id: {parameter: deque[value]}}
drift_buffers: Dict[str, Dict[str, deque[float]]] = {}


# - Anomaly Detection Logic
def detect_spike(reading: SensorReading) -> Optional[List[Anomaly]]:
    """Detects spike anomalies."""
    anomalies = []

    if not (Config.TEMP_NORMAL_MIN <= reading.temperature <= Config.TEMP_NORMAL_MAX):
        if (
            reading.temperature > Config.TEMP_SPIKE_THRESHOLD_HIGH
            or reading.temperature < Config.TEMP_SPIKE_THRESHOLD_LOW
        ):
            anomalies.append(
                Anomaly(
                    type="spike",
                    timestamp=reading.timestamp,
                    sensor_id=reading.sensor_id,
                    parameter="temperature",
                    value=reading.temperature,
                    message=f"Temperature spike detected: {reading.temperature}°C.",
                )
            )

    if not (
        Config.PRESSURE_NORMAL_MIN <= reading.pressure <= Config.PRESSURE_NORMAL_MAX
    ):
        if (
            reading.pressure > Config.PRESSURE_SPIKE_THRESHOLD_HIGH
            or reading.pressure < Config.PRESSURE_SPIKE_THRESHOLD_LOW
        ):
            anomalies.append(
                Anomaly(
                    type="spike",
                    timestamp=reading.timestamp,
                    sensor_id=reading.sensor_id,
                    parameter="pressure",
                    value=reading.pressure,
                    message=f"Pressure spike detected: {reading.pressure} bar.",
                )
            )

    if not (Config.FLOW_NORMAL_MIN <= reading.flow <= Config.FLOW_NORMAL_MAX):
        if (
            reading.flow > Config.FLOW_SPIKE_THRESHOLD_HIGH
            or reading.flow < Config.FLOW_SPIKE_THRESHOLD_LOW
        ):
            anomalies.append(
                Anomaly(
                    type="spike",
                    timestamp=reading.timestamp,
                    sensor_id=reading.sensor_id,
                    parameter="flow",
                    value=reading.flow,
                    message=f"Flow spike detected: {reading.flow} L/min.",
                )
            )
    return anomalies if anomalies else None


def detect_drift(reading: SensorReading) -> Optional[List[Anomaly]]:
    """Detects drift anomalies based on sustained abnormal values."""
    sensor_id = reading.sensor_id
    timestamp = reading.timestamp

    if sensor_id not in drift_buffers:
        drift_buffers[sensor_id] = {
            "temperature": deque(maxlen=Config.DRIFT_CONSECUTIVE_READINGS),
            "pressure": deque(maxlen=Config.DRIFT_CONSECUTIVE_READINGS),
            "flow": deque(maxlen=Config.DRIFT_CONSECUTIVE_READINGS),
        }

    anomalies = []

    # Update buffers
    drift_buffers[sensor_id]["temperature"].append(reading.temperature)
    drift_buffers[sensor_id]["pressure"].append(reading.pressure)
    drift_buffers[sensor_id]["flow"].append(reading.flow)

    # Check for temperature drift
    if (
        len(drift_buffers[sensor_id]["temperature"])
        == Config.DRIFT_CONSECUTIVE_READINGS
    ):
        temp_readings = list(drift_buffers[sensor_id]["temperature"])
        if all(t > Config.TEMP_DRIFT_THRESHOLD_HIGH for t in temp_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="temperature",
                    value=temp_readings[-1],  # Last value in the drift
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Temperature drift detected: sustained >{Config.TEMP_DRIFT_THRESHOLD_HIGH}°C for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )
        elif all(t < Config.TEMP_DRIFT_THRESHOLD_LOW for t in temp_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="temperature",
                    value=temp_readings[-1],
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Temperature drift detected: sustained <{Config.TEMP_DRIFT_THRESHOLD_LOW}°C for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )
    # Check for pressure drift
    if len(drift_buffers[sensor_id]["pressure"]) == Config.DRIFT_CONSECUTIVE_READINGS:
        pressure_readings = list(drift_buffers[sensor_id]["pressure"])
        if all(p > Config.PRESSURE_DRIFT_THRESHOLD_HIGH for p in pressure_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="pressure",
                    value=pressure_readings[-1],
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Pressure drift detected: sustained >{Config.PRESSURE_DRIFT_THRESHOLD_HIGH} bar for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )
        elif all(p < Config.PRESSURE_DRIFT_THRESHOLD_LOW for p in pressure_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="pressure",
                    value=pressure_readings[-1],
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Pressure drift detected: sustained <{Config.PRESSURE_DRIFT_THRESHOLD_LOW} bar for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )

    # Check for flow drift
    if len(drift_buffers[sensor_id]["flow"]) == Config.DRIFT_CONSECUTIVE_READINGS:
        flow_readings = list(drift_buffers[sensor_id]["flow"])
        if all(f > Config.FLOW_DRIFT_THRESHOLD_HIGH for f in flow_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="flow",
                    value=flow_readings[-1],
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Flow drift detected: sustained >{Config.FLOW_DRIFT_THRESHOLD_HIGH} L/min for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )
        elif all(f < Config.FLOW_DRIFT_THRESHOLD_LOW for f in flow_readings):
            anomalies.append(
                Anomaly(
                    type="drift",
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    parameter="flow",
                    value=flow_readings[-1],
                    duration_seconds=Config.DRIFT_CONSECUTIVE_READINGS
                    * Config.READING_INTERVAL_SECONDS,
                    message=f"Flow drift detected: sustained <{Config.FLOW_DRIFT_THRESHOLD_LOW} L/min for last {Config.DRIFT_CONSECUTIVE_READINGS} readings.",
                )
            )

    return anomalies if anomalies else None


def detect_dropout(reading: SensorReading) -> Optional[List[Anomaly]]:
    """Detects dropout anomalies if no data is received for a sensor."""
    current_time = reading.timestamp
    dropout_anomalies = []

    for sensor_id, last_ts in last_reading_timestamps.items():
        if (
            sensor_id == reading.sensor_id
            and (current_time - last_ts).total_seconds()
            > Config.DROPOUT_THRESHOLD_SECONDS
        ):
            dropout_anomalies.append(
                Anomaly(
                    type="dropout",
                    timestamp=current_time,
                    sensor_id=sensor_id,
                    duration_seconds=int((current_time - last_ts).total_seconds()),
                    message=f"Dropout detected for sensor '{sensor_id}': No data received for more than {Config.DROPOUT_THRESHOLD_SECONDS} seconds.",
                )
            )

    # Update last reading timestamp for the current sensor
    last_reading_timestamps[reading.sensor_id] = reading.timestamp

    return dropout_anomalies if dropout_anomalies else None


async def write_anomalies_to_file():
    """
    Writes the current list of recent anomalies to a shared JSON file.
    This function is called periodically and after new anomalies are detected.
    """
    # Ensure the data directory exists
    os.makedirs(Config.DATA_DIR, exist_ok=True)

    try:
        # Convert deque to list and then to dictionary for JSON serialization
        anomalies_list = [a.model_dump(mode="json") for a in list(recent_anomalies)]
        with open(Config.ANOMALIES_FILE, "w") as f:
            json.dump(anomalies_list, f, indent=2)
        # print(f"Anomalies written to {Config.ANOMALIES_FILE}")
    except Exception as e:
        print(f"Error writing anomalies to file: {e}")


async def cleanup_old_anomalies():
    """
    Background task to periodically remove anomalies older than ANOMALY_RETENTION_SECONDS.
    """
    while True:
        await asyncio.sleep(Config.ANOMALY_CLEANUP_INTERVAL_SECONDS)
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time - timedelta(seconds=Config.ANOMALY_RETENTION_SECONDS)

        removed_count = 0
        while recent_anomalies and recent_anomalies[0].timestamp < cutoff_time:
            recent_anomalies.popleft()
            removed_count += 1

        if removed_count > 0:
            print(
                f"Cleaned up {removed_count} old anomalies. Remaining: {len(recent_anomalies)}"
            )


# - FastAPI Endpoints
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifecycle event. Ensures shared data directory exists, loads existing
    anomalies if present, and starts background tasks.
    """
    print("Anomaly Detector FastAPI app starting up.")
    os.makedirs(Config.DATA_DIR, exist_ok=True)

    # Load existing anomalies on startup
    if (
        os.path.exists(Config.ANOMALIES_FILE)
        and os.path.getsize(Config.ANOMALIES_FILE) > 0
    ):
        try:
            with open(Config.ANOMALIES_FILE, "r") as f:
                persisted_anomalies_data = json.load(f)
            # Convert loaded data back to Anomaly models and append to deque
            for anomaly_data in persisted_anomalies_data:
                recent_anomalies.append(Anomaly(**anomaly_data))
            print(
                f"Loaded {len(recent_anomalies)} existing anomalies from {Config.ANOMALIES_FILE}"
            )
        except json.JSONDecodeError as e:
            print(
                f"Error decoding existing anomalies file: {e}. Starting with empty anomalies."
            )
            # If the file is corrupted, reinitialize it as empty
            with open(Config.ANOMALIES_FILE, "w") as f:
                json.dump([], f)
        except Exception as e:
            print(
                f"An unexpected error occurred while loading anomalies: {e}. Starting with empty anomalies."
            )
            with open(Config.ANOMALIES_FILE, "w") as f:
                json.dump([], f)
    else:
        # If the file doesn't exist or is empty, initialize it as an empty list
        with open(Config.ANOMALIES_FILE, "w") as f:
            json.dump([], f)
        print(
            f"Initialized empty {Config.ANOMALIES_FILE} as no existing anomalies were found."
        )

    # Start the background cleanup task
    asyncio.create_task(cleanup_old_anomalies())
    print("Anomaly Detector: Started background anomaly cleanup task.")

    yield
    print("Anomaly Detector FastAPI app shutting down.")


# Set the lifespan context manager for the app
app.router.lifespan_context = lifespan


@app.post("/data", status_code=200)
async def receive_sensor_data(
    reading: SensorReading, background_tasks: BackgroundTasks
):
    global last_processed_reading_timestamp
    """
    Receives sensor data, performs anomaly detection, and updates internal state.
    """

    # Detect anomalies
    detected_anomalies: List[Anomaly] = []

    # Spike detection
    spike_anomalies = detect_spike(reading)
    if spike_anomalies:
        detected_anomalies.extend(spike_anomalies)

    # Drift detection
    drift_anomalies = detect_drift(reading)
    if drift_anomalies:
        detected_anomalies.extend(drift_anomalies)

    # Dropout detection - This now takes 'reading' to update its own last_reading_timestamps
    dropout_anomalies = detect_dropout(reading)
    if dropout_anomalies:
        detected_anomalies.extend(dropout_anomalies)

    # Add detected anomalies to the recent_anomalies deque
    for anomaly in detected_anomalies:
        recent_anomalies.append(anomaly)
        print(
            f"ANOMALY DETECTED: {anomaly.message} ({anomaly.type}) at {anomaly.timestamp}"
        )

    # Schedule writing anomalies to file in the background
    background_tasks.add_task(write_anomalies_to_file)

    last_processed_reading_timestamp = reading.timestamp

    return {
        "message": "Data received and processed",
        "anomalies_detected": len(detected_anomalies),
    }


@app.get("/anomalies", response_model=List[Anomaly])
async def get_recent_anomalies():
    """
    Returns a list of recent anomalies detected by the system.
    This endpoint is intended for internal consumption by llm_summarizer and api_service.
    """
    return list(recent_anomalies)


@app.get("/status", status_code=200)
async def status_check():
    """
    Status check endpoint for the Anomaly Detector service.
    """
    return {
        "status": "ok",
        "service": "anomaly_detector",
        "timestamp": datetime.now(timezone.utc),
    }
