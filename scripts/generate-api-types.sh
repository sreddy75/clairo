#!/bin/bash
# Generate TypeScript types from OpenAPI schema
#
# Usage: ./scripts/generate-api-types.sh
#
# Prerequisites:
# - Backend must be running (for OpenAPI schema)
# - npm packages installed in frontend/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OPENAPI_URL="$BACKEND_URL/openapi.json"
OUTPUT_FILE="$FRONTEND_DIR/src/types/api.ts"

echo "Generating API types from OpenAPI schema..."
echo "Backend URL: $BACKEND_URL"

# Check if backend is running
if ! curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo "Error: Backend is not running at $BACKEND_URL"
    echo "Start the backend with: docker-compose up -d backend"
    echo "Or: cd backend && uvicorn app.main:app --reload"
    exit 1
fi

# Check if openapi-typescript is installed
if ! command -v npx &> /dev/null; then
    echo "Error: npx not found. Please install Node.js"
    exit 1
fi

# Generate types
echo "Fetching OpenAPI schema from $OPENAPI_URL..."
cd "$FRONTEND_DIR"

npx openapi-typescript "$OPENAPI_URL" -o "$OUTPUT_FILE"

echo "Types generated successfully at: $OUTPUT_FILE"
echo ""
echo "Don't forget to run 'npm run type-check' to verify the types."
