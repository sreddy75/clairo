#!/bin/bash
# Validate Docker Compose configuration and optionally test services
#
# Usage: ./scripts/validate-compose.sh [--test]
#
# Options:
#   --test    Start services, verify health, then stop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

echo "Validating Docker Compose configuration..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: docker-compose not found"
    exit 1
fi

# Prefer 'docker compose' over 'docker-compose'
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Validate syntax
echo "Checking compose file syntax..."
cd "$PROJECT_ROOT"
$COMPOSE_CMD config > /dev/null
echo "Syntax: OK"

# List services
echo ""
echo "Services defined:"
$COMPOSE_CMD config --services | while read service; do
    echo "  - $service"
done

# If --test flag is passed, start and verify services
if [ "$1" = "--test" ]; then
    echo ""
    echo "Starting services for validation..."

    # Start infrastructure services only (not backend which requires build)
    $COMPOSE_CMD up -d postgres redis qdrant minio minio-init

    echo "Waiting for services to be healthy..."
    sleep 10

    # Check health of each service
    echo ""
    echo "Checking service health..."

    # PostgreSQL
    if $COMPOSE_CMD exec -T postgres pg_isready -U clairo > /dev/null 2>&1; then
        echo "  PostgreSQL: OK"
    else
        echo "  PostgreSQL: FAILED"
    fi

    # Redis
    if $COMPOSE_CMD exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo "  Redis: OK"
    else
        echo "  Redis: FAILED"
    fi

    # Qdrant
    if curl -s http://localhost:6333/readyz > /dev/null 2>&1; then
        echo "  Qdrant: OK"
    else
        echo "  Qdrant: FAILED"
    fi

    # MinIO
    if curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        echo "  MinIO: OK"
    else
        echo "  MinIO: FAILED"
    fi

    echo ""
    echo "Stopping services..."
    $COMPOSE_CMD down

    echo ""
    echo "Validation complete!"
fi
