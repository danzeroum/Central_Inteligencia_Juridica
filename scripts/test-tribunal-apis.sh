#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Smoke Test - Tribunal APIs"
echo "=============================="

tribunals=("TJSP" "TJMG" "TJRS" "TJRJ" "STF")

for tribunal in "${tribunals[@]}"; do
    echo ""
    echo "Testing $tribunal..."
    echo "-------------------"

    python - <<PYTHON
from src.tools.tribunal_api_adapter import TribunalAPIAdapter

adapter = TribunalAPIAdapter("$tribunal")

status = adapter.get_status()
print("📊 Status:")
print(f"   Source: {status['_metadata']['source']}")
print(f"   Status: {status['status']}")

cb_state = adapter.get_circuit_breaker_state()
print("🔌 Circuit Breaker:")
print(f"   State: {cb_state['state']}")
print(f"   Can execute: {cb_state['can_execute']}")

adapter.close()
PYTHON
done

echo ""
echo "✅ Smoke test completed!"
