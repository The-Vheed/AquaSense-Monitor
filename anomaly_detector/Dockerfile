# anomaly_detector/Dockerfile
FROM python:3.10-slim-buster

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY anomaly_detector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities and config
COPY common/ /app/common/

# Copy anomaly detection code
COPY anomaly_detector/*.py .

# Create shared data directory
RUN mkdir -p /app/data

# Expose the port FastAPI will run on
EXPOSE 8001

# Command to run the FastAPI application
CMD ["uvicorn", "detector:app", "--host", "0.0.0.0", "--port", "8001"]