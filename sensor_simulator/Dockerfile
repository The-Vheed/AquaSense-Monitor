# sensor_simulator/Dockerfile
FROM python:3.10-slim-buster

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY sensor_simulator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities and config
COPY common/ /app/common/

# Copy simulator code
COPY sensor_simulator/*.py .

EXPOSE 8002

# Command to run the simulator as a FastAPI application using uvicorn
CMD ["uvicorn", "simulator:app", "--host", "0.0.0.0", "--port", "8002"]
