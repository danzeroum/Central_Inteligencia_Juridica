#!/usr/bin/env bash
set -euo pipefail

echo "🔍 BuildToFlip Standard Upgrade - Onda 2.2 Validation"
echo "================================================================"

PASS=0
FAIL=0

pass() { echo "✅ $1"; ((PASS++)); }
fail() { echo "❌ $1"; ((FAIL++)); exit 1; }

# Gate 1: Pré-requisitos
echo ""
echo "📋 Gate 1: Environment Prerequisites"
echo "------------------------------------"

if docker ps | grep -q "tribunal-chromadb"; then
    pass "ChromaDB container running"
else
    fail "ChromaDB NOT running. Execute: docker-compose up -d chromadb"
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
    pass "OPENAI_API_KEY configured"
else
    fail "OPENAI_API_KEY not set. Execute: export OPENAI_API_KEY='sk-...'"
fi

if curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
    pass "ChromaDB responding to heartbeat"
else
    fail "ChromaDB not responding. Check: docker-compose logs chromadb"
fi

# Gate 2: Code Structure
echo ""
echo "📁 Gate 2: Code Structure"
echo "-------------------------"

required_files=(
    "src/memory/vector_memory.py"
    "tests/integration/test_vector_memory.py"
    "tests/emergent/test_memory_learning.py"
    "docs/ADRs/ADR-007-vector-memory.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        pass "File exists: $file"
    else
        fail "Missing file: $file"
    fi
done

# Gate 3: Integration Tests
echo ""
echo "🧪 Gate 3: Integration Tests"
echo "-----------------------------"

if pytest tests/integration/test_vector_memory.py -v --tb=short; then
    pass "Integration tests passed"
else
    fail "Integration tests failed"
fi

# Gate 4: Emergent Behavior Tests
echo ""
echo "🧠 Gate 4: Emergent Learning Validation"
echo "----------------------------------------"

if pytest tests/emergent/test_memory_learning.py -v --tb=short -k "test_learning_effect_latency_reduction"; then
    pass "Learning effect validated (latency reduction)"
else
    fail "Learning effect NOT observed"
fi

# Gate 5: Memory System Health
echo ""
echo "💾 Gate 5: Memory System Health"
echo "--------------------------------"

python - <<'PYTHON'
import sys
from src.memory.vector_memory import VectorMemory

memory = VectorMemory()

if not memory.is_available():
    print("❌ VectorMemory not available")
    sys.exit(1)

stats = memory.get_stats()

if stats["status"] != "healthy":
    print(f"❌ Memory status: {stats['status']}")
    sys.exit(1)

print(f"✅ Memory system healthy (total={stats['total_memories']})")
PYTHON

if [ $? -eq 0 ]; then
    ((PASS++))
else
    fail "Memory system unhealthy"
fi

# Gate 6: Performance Benchmarks
echo ""
echo "⚡ Gate 6: Performance Benchmarks"
echo "----------------------------------"

python - <<'PYTHON'
import sys
import time
from src.memory.vector_memory import VectorMemory

memory = VectorMemory()

# Benchmark 1: Recall latency
start = time.perf_counter()
recalled = memory.recall_similar("test query", k=3)
recall_latency = time.perf_counter() - start

if recall_latency > 0.3:
    print(f"❌ Recall too slow: {recall_latency:.3f}s (target <300ms)")
    sys.exit(1)

print(f"✅ Recall latency OK: {recall_latency*1000:.0f}ms")

# Benchmark 2: Remember latency
start = time.perf_counter()
success = memory.remember(
    "test task",
    {"test": True},
    {"tribunals": ["TEST"]}
)
remember_latency = time.perf_counter() - start

if not success or remember_latency > 0.5:
    print(f"❌ Remember failed or too slow: {remember_latency:.3f}s")
    sys.exit(1)

print(f"✅ Remember latency OK: {remember_latency*1000:.0f}ms")
PYTHON

if [ $? -eq 0 ]; then
    ((PASS++))
else
    fail "Performance benchmarks failed"
fi

# Gate 7: API Integration
echo ""
echo "🌐 Gate 7: API Integration (End-to-End)"
echo "----------------------------------------"

# Inicia a API em background (se não estiver rodando)
if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "   Starting API server..."
    docker-compose up -d agent-system
    sleep 10
fi

# Teste E2E: Task com memória
response=$(curl -sf -X POST http://localhost:8000/api/v1/tasks \
    -H "Content-Type: application/json" \
    -d '{"task_description": "Status do TJSP"}')

if echo "$response" | jq -e '.memory.recalled_count >= 0' > /dev/null 2>&1; then
    pass "API returning memory metrics"
else
    fail "API not returning memory metrics"
fi

# Resultado Final
echo ""
echo "================================================================"
echo "🎯 VALIDATION SUMMARY"
echo "================================================================"
echo "✅ Passed: $PASS"
echo "❌ Failed: $FAIL"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "🎉 ONDA 2.2 VALIDATED SUCCESSFULLY!"
    echo "   Vector Memory está funcionando conforme esperado."
    echo ""
    echo "📊 Next Steps:"
    echo "   1. Monitor memory growth: docker-compose logs chromadb"
    echo "   2. Test in production staging"
    echo "   3. Merge to main: git checkout main && git merge feature/standard-upgrade-wave2.2-vector-memory"
    exit 0
else
    echo ""
    echo "💥 VALIDATION FAILED"
    echo "   Review errors above and retry."
    exit 1
fi
