#!/bin/bash

# Install curl for health checks
apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Start Ollama in the background.
/bin/ollama serve &
# Record Process ID.
pid=$!

# Pause for Ollama to start.
sleep 5

echo "🔴 Retrieve Mistral model..."
ollama pull mistral
echo "🟢 Done!"

# Wait for Ollama process to finish.
wait $pid