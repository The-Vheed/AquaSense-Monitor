# api_service/Dockerfile
FROM python:3.10-slim-buster

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY api_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities and config
COPY common/ /app/common/

# Copy API service code
COPY api_service/*.py .

# Create shared data directory
RUN mkdir -p /app/data

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
