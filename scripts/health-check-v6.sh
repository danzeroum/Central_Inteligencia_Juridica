#!/usr/bin/env bash
set -euo pipefail

echo "🔍 BuildToFlip v6 - Health Check"

ENDPOINT=${1:-http://localhost:8080}

curl -sf "$ENDPOINT/actuator/health" | jq '.'
curl -sf "$ENDPOINT/actuator/info" | jq '.'
curl -sf "$ENDPOINT/actuator/metrics" | head -n 20 || true
