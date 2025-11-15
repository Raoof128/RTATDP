#!/bin/bash
# Quick start script for the AI Threat Detection System

set -e

echo "=========================================="
echo "AI Threat Detection System - Quick Start"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Create necessary directories
echo "1. Creating directories..."
mkdir -p models/ensemble models/anomaly data logs

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "2. Creating .env file from template..."
    cp .env.example .env
    echo "   ✓ .env created (edit this file to configure your environment)"
else
    echo "2. .env file already exists"
fi

# Start Docker containers
echo "3. Starting Docker containers..."
docker-compose up -d

# Wait for services to be ready
echo "4. Waiting for services to start (30 seconds)..."
sleep 30

# Create Kafka topics
echo "5. Creating Kafka topics..."
docker-compose exec -T kafka kafka-topics --create --bootstrap-server localhost:9092 \
    --topic security.events.network --partitions 10 --replication-factor 1 \
    --if-not-exists 2>/dev/null || true

docker-compose exec -T kafka kafka-topics --create --bootstrap-server localhost:9092 \
    --topic security.events.endpoint --partitions 10 --replication-factor 1 \
    --if-not-exists 2>/dev/null || true

docker-compose exec -T kafka kafka-topics --create --bootstrap-server localhost:9092 \
    --topic security.events.application --partitions 10 --replication-factor 1 \
    --if-not-exists 2>/dev/null || true

echo ""
echo "=========================================="
echo "✓ Quick Start Complete!"
echo "=========================================="
echo ""
echo "Services are now running:"
echo "  • Inference API:  http://localhost:8000"
echo "  • API Docs:       http://localhost:8000/docs"
echo "  • Prometheus:     http://localhost:9090"
echo "  • Grafana:        http://localhost:3000 (admin/admin)"
echo "  • Kafka:          localhost:9092"
echo "  • Redis:          localhost:6379"
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies: pip install -r requirements.txt"
echo "  2. Train models: jupyter notebook notebooks/01_model_training_demo.ipynb"
echo "  3. Run health check: bash scripts/health_check.sh"
echo "  4. View logs: docker-compose logs -f"
echo ""
echo "To stop: docker-compose down"
echo "=========================================="
