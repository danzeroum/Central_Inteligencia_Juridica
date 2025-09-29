#!/usr/bin/env bash
set -euo pipefail

echo "🔍 BuildToFlip Standard Upgrade - Onda 2.2 Validation"
echo "================================================================"

PASS=0
FAIL=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
  exit 1
}

maybe_warn() {
  echo "⚠️  $1"
}

needs_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Comando obrigatório não encontrado: $1"
  fi
}

echo
echo "📋 Gate 1: Environment Prerequisites"
echo "------------------------------------"

needs_command docker
needs_command curl

if ! docker ps >/dev/null 2>&1; then
  fail "Docker não está acessível. Verifique instalação/permissões."
fi

if docker ps | grep -q "tribunal-chromadb"; then
  pass "ChromaDB container em execução"
else
  fail "ChromaDB NÃO está rodando. Execute: docker-compose up -d chromadb"
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  fail "OPENAI_API_KEY não configurada. Exporte a variável antes do script."
else
  pass "OPENAI_API_KEY configurada"
fi

if curl -sf http://localhost:8000/api/v1/heartbeat >/dev/null 2>&1; then
  pass "ChromaDB responde heartbeat"
else
  fail "ChromaDB não responde em http://localhost:8000/api/v1/heartbeat"
fi

echo
echo "📁 Gate 2: Code Structure"
echo "-------------------------"

required_files=(
  "src/memory/vector_memory.py"
  "tests/integration/test_vector_memory.py"
  "tests/emergent/test_memory_learning.py"
  "docs/ADRs/ADR-007-vector-memory.md"
)

for file in "${required_files[@]}"; do
  if [[ -f "$file" ]]; then
    pass "Arquivo presente: $file"
  else
    fail "Arquivo obrigatório ausente: $file"
  fi
done

echo
echo "🧪 Gate 3: Integration Tests"
echo "-----------------------------"

needs_command pytest

if pytest tests/integration/test_vector_memory.py -v --tb=short; then
  pass "Testes de integração concluídos"
else
  fail "Falha nos testes de integração"
fi

echo
echo "🧠 Gate 4: Emergent Learning Validation"
echo "----------------------------------------"

if pytest tests/emergent/test_memory_learning.py -v --tb=short -k "test_learning_effect_latency_reduction"; then
  pass "Efeito de aprendizado (latência) validado"
else
  fail "Efeito de aprendizado não observado"
fi

echo
echo "💾 Gate 5: Memory System Health"
echo "--------------------------------"

python - <<'PYCODE'
from src.memory.vector_memory import VectorMemory

memory = VectorMemory()

if not memory.is_available():
    raise SystemExit("VectorMemory indisponível")

stats = memory.get_stats()

if stats.get("status") != "healthy":
    raise SystemExit(f"Estado inesperado: {stats}")

print(f"✅ Memory system healthy (total={stats.get('total_memories')})")
PYCODE

echo
echo "⚡ Gate 6: Performance Benchmarks"
echo "----------------------------------"

python - <<'PYCODE'
import time
from src.memory.vector_memory import VectorMemory

memory = VectorMemory()

if not memory.is_available():
    raise SystemExit("VectorMemory indisponível para benchmark")

start = time.perf_counter()
memory.recall_similar("benchmark query", k=3)
recall_latency = time.perf_counter() - start

if recall_latency > 0.3:
    raise SystemExit(f"Recall muito lento: {recall_latency:.3f}s (target <300ms)")

print(f"✅ Recall latency OK: {recall_latency*1000:.0f}ms")

start = time.perf_counter()
ok = memory.remember("benchmark task", {"benchmark": True}, {"tribunals": ["TJB"]})
remember_latency = time.perf_counter() - start

if not ok or remember_latency > 0.5:
    raise SystemExit(f"Remember falhou ou lento: {remember_latency:.3f}s")

print(f"✅ Remember latency OK: {remember_latency*1000:.0f}ms")
PYCODE

echo
echo "🌐 Gate 7: API Integration (End-to-End)"
echo "----------------------------------------"

if ! command -v jq >/dev/null 2>&1; then
  maybe_warn "jq não encontrado; validação E2E parcial."
else
  if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    maybe_warn "API principal não respondeu /health. Tente iniciar com docker-compose up -d agent-system"
  fi

  response=$(curl -sf -X POST http://localhost:8000/api/v1/tasks \
    -H "Content-Type: application/json" \
    -d '{"task_description": "Status do TJSP"}' || true)

  if [[ -n "$response" ]] && echo "$response" | jq -e '.memory.recalled_count >= 0' >/dev/null 2>&1; then
    pass "API retornou métricas de memória"
  else
    maybe_warn "Não foi possível validar API end-to-end"
  fi
fi

echo
echo "================================================================"
echo "🎯 VALIDATION SUMMARY"
echo "================================================================"
echo "✅ Passed: $PASS"
echo "❌ Failed: $FAIL"

if [[ $FAIL -eq 0 ]]; then
  echo
  echo "🎉 ONDA 2.2 VALIDATED SUCCESSFULLY!"
  echo "   Vector Memory operacional e pronto para merge."
  exit 0
else
  echo
  echo "💥 VALIDATION FAILED"
  echo "   Revise as mensagens acima antes de prosseguir."
  exit 1
fi
