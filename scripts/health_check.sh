#!/bin/bash
# Health check script for the threat detection system

set -e

echo "=== Threat Detection System Health Check ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    local service=$1
    local url=$2
    local expected_code=${3:-200}

    echo -n "Checking $service... "

    if response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>&1); then
        if [ "$response" -eq "$expected_code" ]; then
            echo -e "${GREEN}✓ OK${NC} (HTTP $response)"
            return 0
        else
            echo -e "${YELLOW}⚠ Warning${NC} (HTTP $response, expected $expected_code)"
            return 1
        fi
    else
        echo -e "${RED}✗ Failed${NC} (Connection error)"
        return 1
    fi
}

check_port() {
    local service=$1
    local host=$2
    local port=$3

    echo -n "Checking $service port... "

    if nc -z -w5 "$host" "$port" 2>/dev/null; then
        echo -e "${GREEN}✓ OK${NC} (Port $port open)"
        return 0
    else
        echo -e "${RED}✗ Failed${NC} (Port $port not accessible)"
        return 1
    fi
}

# Check Inference API
echo "--- API Services ---"
check_service "Inference API Health" "http://localhost:8000/health" 200
check_service "Inference API Docs" "http://localhost:8000/docs" 200
check_service "Metrics Endpoint" "http://localhost:8000/metrics" 200
echo ""

# Check Backend Services
echo "--- Backend Services ---"
check_port "Redis" "localhost" 6379
check_port "Kafka" "localhost" 9092
check_port "PostgreSQL" "localhost" 5432
echo ""

# Check Monitoring
echo "--- Monitoring Services ---"
check_service "Prometheus" "http://localhost:9090/-/healthy" 200
check_service "Grafana" "http://localhost:3000/api/health" 200
echo ""

# Check models
echo "--- Model Files ---"
if [ -f "models/ensemble/ensemble.pkl" ]; then
    echo -e "Ensemble models: ${GREEN}✓ Found${NC}"
else
    echo -e "Ensemble models: ${YELLOW}⚠ Not found${NC} (needs training)"
fi

if [ -f "models/anomaly/isolation_forest.pkl" ]; then
    echo -e "Anomaly models: ${GREEN}✓ Found${NC}"
else
    echo -e "Anomaly models: ${YELLOW}⚠ Not found${NC} (needs training)"
fi
echo ""

# Summary
echo "=== Health Check Complete ==="
