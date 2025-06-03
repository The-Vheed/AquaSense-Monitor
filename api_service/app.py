# api_service/app.py
from fastapi import FastAPI, HTTPException
from typing import List, Optional
from datetime import datetime, timezone
import json
import os
import sys
import httpx

# Add the parent directory to sys.path to allow importing from common
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.config import Config
from common.models import Anomaly, AnomalySummary, HealthStatus, SensorReading
from summarizer import LLMSummarizer  # Import the LLMSummarizer class

app = FastAPI(
    title="AquaSense-Monitor Public API",
    description="Provides access to recent anomalies, LLM summaries, and system health.",
    version="1.0.0",
)

# Initialize the LLMSummarizer globally
# This ensures the LLM model is loaded once when the app starts
llm_summarizer_instance = LLMSummarizer()

# --- Global State for Health Status ---
# These will be updated based on file read times or pings to other services
health_status_data = {
    "sensor_simulator_active": False,
    "anomaly_detector_active": False,
    "llm_summarizer_active": False,
    "api_service_active": True,  # This service is running
    "ollama_active": False,
    "last_sensor_reading_received": None,  # This will now be updated by anomaly detector's health check
    "last_anomaly_detected": None,
    "last_summary_generated": None,
    "current_anomalies_count": 0,
    "ollama_model_loaded": False,  # This will be checked by pinging Ollama
}

# URL for the anomaly detector service
anomaly_detector_url = (
    f"http://{Config.ANOMALY_DETECTOR_HOST}:{Config.ANOMALY_DETECTOR_PORT}/anomalies"
)


async def check_service_health(
    service_host: str, port: int, endpoint: str = "/status", return_data=False
):
    """Pings a service's health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{service_host}:{port}{endpoint}", timeout=5
            )
            response.raise_for_status()
            if return_data:
                return True, response.json()
            else:
                return True
    except (httpx.RequestError, httpx.HTTPStatusError):
        if return_data:
            return False, None
        else:
            return False


async def check_ollama_model_loaded():
    """Checks if the specified Ollama model is loaded."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{Config.OLLAMA_HOST}:{Config.OLLAMA_PORT}/api/show",
                json={"name": Config.LLM_MODEL_NAME},
                timeout=5,
            )
            response.raise_for_status()
            # If the response is successful, the model exists and is likely loaded/pullable
            return True
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Ollama model check failed: {e}")
        return False


# API Endpoints
@app.get("/anomalies", response_model=List[Anomaly])
async def get_recent_anomalies():
    """
    Returns a list of recent anomalies detected by the system.
    Fetches data from the anomaly detector server.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(anomaly_detector_url, timeout=10.0)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            anomalies_data = response.json()
            anomalies = [Anomaly(**a) for a in anomalies_data]

            if anomalies:
                health_status_data["last_anomaly_detected"] = anomalies[-1].timestamp
                health_status_data["current_anomalies_count"] = len(anomalies)
            else:
                health_status_data["last_anomaly_detected"] = None
                health_status_data["current_anomalies_count"] = 0
            return anomalies
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail=f"Could not connect to Anomaly Detector service: {e}",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Anomaly Detector returned an error: {e.response.text}",
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, detail="Error decoding anomalies data from detector."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching anomalies: {e}",
        )


@app.get(
    "/summary", response_model=AnomalySummary
)  # Change response_model to AnomalySummary
async def get_latest_summary():
    """
    Generates a structured summary of recent anomalies using the LLM.
    """
    # Fetch recent anomalies from the detector
    anomalies = await get_recent_anomalies()

    # Call the updated generate_summary method
    success, summary_output = await llm_summarizer_instance.generate_summary(anomalies)

    # Update last summary generated timestamp for health check purposes
    health_status_data["last_summary_generated"] = datetime.now(timezone.utc)

    if success:
        return summary_output
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate anomaly summary: {summary_output}",
        )


@app.get("/status", response_model=HealthStatus)
async def get_health_status():
    """
    Returns the health status of the data stream and components.
    """
    # Check if data directory exists. If not, services might not be writing.
    if not os.path.exists(Config.DATA_DIR):
        print(f"Warning: Shared data directory {Config.DATA_DIR} does not exist.")
        # This implies a serious setup issue or very early startup.
        # Most flags will remain False.

    # Check Anomaly Detector health
    health_status_data["anomaly_detector_active"] = await check_service_health(
        Config.ANOMALY_DETECTOR_HOST,
        Config.ANOMALY_DETECTOR_PORT,
        endpoint="/anomalies",  # Use anomalies endpoint as a ping
    )

    # Check LLM Summarizer health using the dedicated check_llm_status method
    llm_summarizer_health_status, _ = await llm_summarizer_instance.check_llm_status()
    health_status_data["llm_summarizer_active"] = llm_summarizer_health_status

    # Ping other services for more direct health checks
    health_status_data["ollama_active"] = await check_service_health(
        Config.OLLAMA_HOST,
        Config.OLLAMA_PORT,
        endpoint="/api/tags",  # A simple Ollama endpoint
    )
    health_status_data["ollama_model_loaded"] = await check_ollama_model_loaded()

    # Check Sensor Simulator health directly
    health_status_data["sensor_simulator_active"], sensor_simulator_data = (
        await check_service_health(
            Config.SENSOR_SIMULATOR_HOST,
            Config.SENSOR_SIMULATOR_PORT,
            endpoint="/status",  # Use the simulator's /status endpoint
            return_data=True,
        )
    )
    if sensor_simulator_data:
        health_status_data["last_sensor_reading_received"] = sensor_simulator_data.get(
            "last_data_sent", health_status_data["last_sensor_reading_received"]
        )

    return HealthStatus(**health_status_data)
