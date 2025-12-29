#!/bin/bash
# Quick start script for running Locust performance tests

set -e

# Default values
HOST="${LOCUST_HOST:-http://localhost:8000}"
USERS="${LOCUST_USERS:-10}"
SPAWN_RATE="${LOCUST_SPAWN_RATE:-2}"
RUN_TIME="${LOCUST_RUN_TIME:-5m}"
MODE="${1:-web}"

echo "======================================"
echo "Fallout Shelter Performance Tests"
echo "======================================"
echo "Host: $HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE/s"
echo "Run Time: $RUN_TIME"
echo "======================================"
echo ""

# Load environment variables if .env.locust exists
if [ -f "backend/locust/.env.locust" ]; then
    echo "Loading configuration from .env.locust"
    export $(cat backend/locust/.env.locust | grep -v '^#' | xargs)
fi

case "$MODE" in
    web)
        echo "Starting Locust Web UI..."
        echo "Open http://localhost:8089 in your browser"
        locust -f backend/locust/locustfile.py --host "$HOST"
        ;;

    headless)
        echo "Running headless performance test..."
        locust -f backend/locust/locustfile.py \
            --host "$HOST" \
            --users "$USERS" \
            --spawn-rate "$SPAWN_RATE" \
            --run-time "$RUN_TIME" \
            --headless \
            --html "locust_report_$(date +%Y%m%d_%H%M%S).html"
        ;;

    baseline)
        echo "Running baseline test (10 users, 10 minutes)..."
        locust -f backend/locust/locustfile.py \
            --host "$HOST" \
            --users 10 \
            --spawn-rate 2 \
            --run-time 10m \
            --headless \
            --html "baseline_report_$(date +%Y%m%d_%H%M%S).html" \
            --csv "baseline_data_$(date +%Y%m%d_%H%M%S)"
        ;;

    stress)
        echo "Running stress test (100 users, 15 minutes)..."
        locust -f backend/locust/locustfile.py \
            --host "$HOST" \
            --users 100 \
            --spawn-rate 10 \
            --run-time 15m \
            --headless \
            --html "stress_report_$(date +%Y%m%d_%H%M%S).html" \
            --csv "stress_data_$(date +%Y%m%d_%H%M%S)"
        ;;

    quick)
        echo "Running quick test (5 users, 2 minutes)..."
        locust -f backend/locust/locustfile.py \
            --host "$HOST" \
            --users 5 \
            --spawn-rate 1 \
            --run-time 2m \
            --headless \
            --only-summary
        ;;

    *)
        echo "Usage: $0 {web|headless|baseline|stress|quick}"
        echo ""
        echo "Modes:"
        echo "  web      - Start with web UI (default)"
        echo "  headless - Run without UI"
        echo "  baseline - Run baseline performance test"
        echo "  stress   - Run stress test with high load"
        echo "  quick    - Quick smoke test"
        echo ""
        echo "Environment variables:"
        echo "  LOCUST_HOST        - API host URL"
        echo "  LOCUST_USERS       - Number of simulated users"
        echo "  LOCUST_SPAWN_RATE  - Users spawned per second"
        echo "  LOCUST_RUN_TIME    - Test duration (e.g., 5m, 1h)"
        exit 1
        ;;
esac
