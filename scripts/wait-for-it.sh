#!/bin/bash
# Wait for a service to become available
#
# Usage: ./scripts/wait-for-it.sh host:port [-t timeout] [-- command]
#
# Examples:
#   ./scripts/wait-for-it.sh localhost:5432
#   ./scripts/wait-for-it.sh localhost:5432 -t 60
#   ./scripts/wait-for-it.sh localhost:5432 -- echo "PostgreSQL is ready"

set -e

TIMEOUT=30
HOST=""
PORT=""
CMD=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --)
            shift
            CMD="$@"
            break
            ;;
        *:*)
            HOST="${1%%:*}"
            PORT="${1##*:}"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "Usage: $0 host:port [-t timeout] [-- command]"
    exit 1
fi

echo "Waiting for $HOST:$PORT (timeout: ${TIMEOUT}s)..."

start_time=$(date +%s)
while true; do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "$HOST:$PORT is available!"
        break
    fi

    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    if [ $elapsed -ge $TIMEOUT ]; then
        echo "Timeout after ${TIMEOUT}s waiting for $HOST:$PORT"
        exit 1
    fi

    sleep 1
done

# Execute command if provided
if [ -n "$CMD" ]; then
    exec $CMD
fi
