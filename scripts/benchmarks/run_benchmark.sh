#!/bin/bash
# Benchmark runner script for AI Threat Detection Pipeline

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT_DIR="benchmark_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "AI Threat Detection - Performance Benchmark"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "Timestamp: $TIMESTAMP"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if API is accessible
echo -n "Checking API health... "
if curl -sf "$API_URL/health" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "Error: API at $API_URL is not accessible"
    exit 1
fi

# Run benchmark based on argument
BENCHMARK_TYPE="${1:-full}"

case "$BENCHMARK_TYPE" in
    quick)
        echo ""
        echo "Running QUICK benchmark (reduced iterations)..."
        echo ""
        python scripts/benchmarks/performance_benchmark.py \
            --url "$API_URL" \
            --output "$OUTPUT_DIR/quick_benchmark_$TIMESTAMP.json" \
            --quick
        ;;

    full)
        echo ""
        echo "Running FULL benchmark suite..."
        echo ""
        python scripts/benchmarks/performance_benchmark.py \
            --url "$API_URL" \
            --output "$OUTPUT_DIR/full_benchmark_$TIMESTAMP.json"
        ;;

    locust)
        echo ""
        echo "Running Locust load test..."
        echo ""
        USERS="${2:-100}"
        SPAWN_RATE="${3:-10}"
        DURATION="${4:-5m}"

        echo "Configuration:"
        echo "  Users: $USERS"
        echo "  Spawn rate: $SPAWN_RATE"
        echo "  Duration: $DURATION"
        echo ""

        locust -f scripts/benchmarks/locustfile.py \
            --host="$API_URL" \
            --users "$USERS" \
            --spawn-rate "$SPAWN_RATE" \
            --run-time "$DURATION" \
            --headless \
            --html "$OUTPUT_DIR/locust_report_$TIMESTAMP.html" \
            --csv "$OUTPUT_DIR/locust_stats_$TIMESTAMP"
        ;;

    stress)
        echo ""
        echo "Running STRESS test (high load)..."
        echo ""

        locust -f scripts/benchmarks/locustfile.py \
            --host="$API_URL" \
            --users 500 \
            --spawn-rate 50 \
            --run-time 10m \
            --headless \
            --tags stress \
            --html "$OUTPUT_DIR/stress_test_$TIMESTAMP.html" \
            --csv "$OUTPUT_DIR/stress_stats_$TIMESTAMP"
        ;;

    realistic)
        echo ""
        echo "Running REALISTIC usage test..."
        echo ""

        locust -f scripts/benchmarks/locustfile.py \
            --host="$API_URL" \
            --users 50 \
            --spawn-rate 5 \
            --run-time 15m \
            --headless \
            --tags realistic \
            --html "$OUTPUT_DIR/realistic_test_$TIMESTAMP.html" \
            --csv "$OUTPUT_DIR/realistic_stats_$TIMESTAMP"
        ;;

    continuous)
        echo ""
        echo "Running CONTINUOUS benchmark (for monitoring)..."
        echo ""
        echo "This will run benchmarks every 5 minutes. Press Ctrl+C to stop."
        echo ""

        while true; do
            echo "$(date): Running benchmark..."
            python scripts/benchmarks/performance_benchmark.py \
                --url "$API_URL" \
                --output "$OUTPUT_DIR/continuous_$(date +%Y%m%d_%H%M%S).json" \
                --quick

            echo "Sleeping for 5 minutes..."
            sleep 300
        done
        ;;

    *)
        echo "Usage: $0 {quick|full|locust|stress|realistic|continuous} [locust-args]"
        echo ""
        echo "Benchmark types:"
        echo "  quick      - Quick benchmark with reduced iterations"
        echo "  full       - Full benchmark suite (default)"
        echo "  locust     - Locust load test (args: users spawn-rate duration)"
        echo "  stress     - Stress test with 500 concurrent users"
        echo "  realistic  - Realistic usage patterns"
        echo "  continuous - Run benchmarks continuously every 5 minutes"
        echo ""
        echo "Examples:"
        echo "  $0 quick"
        echo "  $0 full"
        echo "  $0 locust 200 20 10m"
        echo "  $0 stress"
        echo "  API_URL=http://prod.example.com:8000 $0 full"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}=========================================="
echo "Benchmark complete!"
echo -e "==========================================${NC}"
echo ""
echo "Results saved to: $OUTPUT_DIR/"
ls -lh "$OUTPUT_DIR/" | tail -5
echo ""
