# common/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


class Config:
    """
    Configuration settings for the AquaSense-Monitor system.
    """

    # --- Sensor Data Simulation ---
    SENSOR_ID: str = "wtf-pipe-1"
    READING_INTERVAL_SECONDS: int = 2  # How often sensor data is emitted

    # --- Normal Ranges ---
    TEMP_NORMAL_MIN: float = 10.0
    TEMP_NORMAL_MAX: float = 35.0
    PRESSURE_NORMAL_MIN: float = 1.0
    PRESSURE_NORMAL_MAX: float = 3.0
    FLOW_NORMAL_MIN: float = 20.0
    FLOW_NORMAL_MAX: float = 100.0

    # --- Anomaly Detection Thresholds ---
    # Spike Detection: A single reading far outside the expected range
    TEMP_SPIKE_THRESHOLD_HIGH: float = TEMP_NORMAL_MAX
    TEMP_SPIKE_THRESHOLD_LOW: float = TEMP_NORMAL_MIN
    PRESSURE_SPIKE_THRESHOLD_HIGH: float = PRESSURE_NORMAL_MAX
    PRESSURE_SPIKE_THRESHOLD_LOW: float = PRESSURE_NORMAL_MIN
    FLOW_SPIKE_THRESHOLD_HIGH: float = FLOW_NORMAL_MAX
    FLOW_SPIKE_THRESHOLD_LOW: float = FLOW_NORMAL_MIN

    # Drift Detection: A sustained abnormal value
    # Number of consecutive readings outside normal range to trigger drift
    DRIFT_CONSECUTIVE_READINGS: int = 8  # 8 readings * 2 seconds/reading = 16 seconds
    TEMP_DRIFT_THRESHOLD_HIGH: float = TEMP_NORMAL_MAX
    TEMP_DRIFT_THRESHOLD_LOW: float = TEMP_NORMAL_MIN
    PRESSURE_DRIFT_THRESHOLD_HIGH: float = PRESSURE_NORMAL_MAX
    PRESSURE_DRIFT_THRESHOLD_LOW: float = PRESSURE_NORMAL_MIN
    FLOW_DRIFT_THRESHOLD_HIGH: float = FLOW_NORMAL_MAX
    FLOW_DRIFT_THRESHOLD_LOW: float = FLOW_NORMAL_MIN

    # Dropout Detection: No data received for a sensor for more than X seconds
    DROPOUT_THRESHOLD_SECONDS: int = 10  # If no data for 10 seconds
    DROPOUT_CHECK_INTERVAL_SECONDS = 2

    # --- Anomaly Storage and Retention ---
    MAX_ANOMALIES_TO_STORE: int = 100  # Max number of recent anomalies (size-based)
    ANOMALY_RETENTION_SECONDS: int = 120  # Anomalies older than 2 minutes (time-based)
    ANOMALY_CLEANUP_INTERVAL_SECONDS: int = 60  # How often to run the cleanup task

    # --- LLM Configuration (for Ollama) ---
    OLLAMA_HOST: str = "ollama"  # Service name in docker-compose
    OLLAMA_PORT: int = 11434
    LLM_MODEL_NAME: str = "mistral"  # Model to use from Ollama
    LLM_MAX_NEW_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.2

    # --- Service Ports ---
    ANOMALY_DETECTOR_HOST: str = "anomaly_detector"  # Service name in docker-compose
    ANOMALY_DETECTOR_PORT: int = 8001

    SENSOR_SIMULATOR_HOST: str = "sensor_simulator"  # Service name in docker-compose
    SENSOR_SIMULATOR_PORT: int = 8002

    HTTP_REQUEST_TIMEOUT_SECONDS = 10

    API_SERVICE_PORT: int = 8000

    # --- Shared Data Paths (relative to container WORKDIR) ---
    DATA_DIR: str = "../data"
    ANOMALIES_FILE: str = os.path.join(DATA_DIR, "anomalies.json")
    SUMMARY_FILE: str = os.path.join(DATA_DIR, "summary.json")
