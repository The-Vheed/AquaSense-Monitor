# sensor_simulator/simulator.py
import asyncio
from contextlib import asynccontextmanager
import httpx
import random
from datetime import datetime, timezone
from fastapi import FastAPI
import uvicorn
import os
import sys

# Add the parent directory to sys.path to allow importing from common
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import Config
from common.models import SensorReading

app = FastAPI(
    title="AquaSense Sensor Simulator",
    description="Simulates sensor data and sends it to the Anomaly Detector.",
    version="1.0.0",
)

# Global state for health status
health_status_data = {
    "sensor_simulator_active": True,  # This service is running
    "last_data_sent": None,
    "target_detector_url": f"http://{Config.ANOMALY_DETECTOR_HOST}:{Config.ANOMALY_DETECTOR_PORT}/data",
}

# Global httpx client to reuse connections
http_client = httpx.AsyncClient()


async def send_sensor_reading(reading: SensorReading):
    """
    Asynchronously sends a single sensor reading to the anomaly detector.
    Handles network errors and updates global health status.
    """

    # Print errors to prevent crashing sensor simulation upon anomaly server downtime
    try:
        response = await http_client.post(
            health_status_data["target_detector_url"],
            json=reading.model_dump(mode="json"),
            timeout=Config.HTTP_REQUEST_TIMEOUT_SECONDS,  # Add a timeout to prevent indefinite blocking
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"Successfully sent reading: {reading.model_dump_json()}")
        health_status_data["last_data_sent"] = datetime.now(timezone.utc)

    except httpx.RequestError as e:
        print(f"Error sending data to Anomaly Detector API (Request Error): {e}")
    except httpx.HTTPStatusError as e:
        print(
            f"Anomaly Detector API returned error status {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        print(f"An unexpected error occurred while sending data: {e}")


async def generate_and_send_data_task():
    """
    Generates simulated sensor data and schedules its sending to the Anomaly Detector.
    This function now uses asyncio.create_task to make sending non-blocking.
    """
    print(f"Sensor Simulator starting for sensor: {Config.SENSOR_ID}")
    print(
        f"Sending data every {Config.READING_INTERVAL_SECONDS} seconds to {health_status_data['target_detector_url']}"
    )

    counter = 0

    while True:
        timestamp = datetime.now(timezone.utc)
        temperature = random.uniform(Config.TEMP_NORMAL_MIN, Config.TEMP_NORMAL_MAX)
        pressure = random.uniform(
            Config.PRESSURE_NORMAL_MIN, Config.PRESSURE_NORMAL_MAX
        )
        flow = random.uniform(Config.FLOW_NORMAL_MIN, Config.FLOW_NORMAL_MAX)

        # Introduce anomalies for testing
        if (
            counter % 40 in list(range(Config.DRIFT_CONSECUTIVE_READINGS + 1))
            and counter > Config.DRIFT_CONSECUTIVE_READINGS + 1
        ):  # Every 80 seconds (40 * 2s) - Drift (sustained high temp)
            print("--- INTRODUCING DRIFT ANOMALY (Temperature) ---")
            temperature = random.uniform(
                Config.TEMP_DRIFT_THRESHOLD_HIGH + 1,
                Config.TEMP_DRIFT_THRESHOLD_HIGH + 5,
            )
        elif (
            counter % 20 == 0 and counter != 0
        ):  # Every 40 seconds (20 * 2s) - Dropout (skip sending)
            print("--- INTRODUCING DROPOUT ANOMALY (Skipping data for 11s) ---")
            for _ in range(int(11 / Config.READING_INTERVAL_SECONDS)):
                await asyncio.sleep(Config.READING_INTERVAL_SECONDS)  # Simulate no data
            counter += 1  # Increment counter for the skipped intervals
            continue  # Skip sending this reading to trigger dropout
        elif counter % 10 == 0 and counter != 0:  # Every 20 seconds (20 * 2s) - Spike
            print("--- INTRODUCING SPIKE ANOMALY ---")
            param_to_spike = random.choice(["temperature", "pressure", "flow"])
            if param_to_spike == "temperature":
                temperature = random.uniform(
                    Config.TEMP_SPIKE_THRESHOLD_HIGH + 5,
                    Config.TEMP_SPIKE_THRESHOLD_HIGH + 15,
                )
            elif param_to_spike == "pressure":
                pressure = random.uniform(
                    Config.PRESSURE_SPIKE_THRESHOLD_HIGH + 1,
                    Config.PRESSURE_SPIKE_THRESHOLD_HIGH + 2,
                )
            elif param_to_spike == "flow":
                flow = random.uniform(
                    Config.FLOW_SPIKE_THRESHOLD_HIGH + 10,
                    Config.FLOW_SPIKE_THRESHOLD_HIGH + 20,
                )

        reading = SensorReading(
            timestamp=timestamp,
            sensor_id=Config.SENSOR_ID,
            temperature=temperature,
            pressure=pressure,
            flow=flow,
        )

        # Schedule the sending of the reading as a non-blocking task
        # This allows the loop to immediately proceed to the next sleep.
        asyncio.create_task(send_sensor_reading(reading))
        print(f"Scheduled sending of reading for timestamp: {reading.timestamp}")

        await asyncio.sleep(Config.READING_INTERVAL_SECONDS)
        counter += 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifecycle event to start the background data generation task.
    Ensures HTTP client is closed on shutdown.
    """
    print("Sensor Simulator FastAPI app starting up...")
    # Start the data generation in a background task
    asyncio.create_task(generate_and_send_data_task())
    yield
    print("Sensor Simulator FastAPI app shutting down...")
    # Close the HTTP client when the app shuts down
    await http_client.aclose()
    print("HTTP client closed.")


app.router.lifespan_context = lifespan


@app.get("/status")
async def get_health_status():
    """
    Returns the health status of the sensor simulator.
    """
    return health_status_data


if __name__ == "__main__":
    # Use uvicorn to run the FastAPI app
    uvicorn.run(
        app, host=Config.SENSOR_SIMULATOR_HOST, port=Config.SENSOR_SIMULATOR_PORT
    )
