#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Validando implementação de Parallelization (Onda 1)"
echo "=========================================="

PASS=0
FAIL=0

pass() { echo "✅ $1"; ((PASS++)); }
fail() { echo "❌ $1"; ((FAIL++)); exit 1; }

# Gate 1: Testes emergentes passam
echo ""
echo "Gate 1: Testes de comportamento emergente"
if pytest tests/emergent/test_parallel_execution.py -v; then
    pass "Testes emergentes de paralelização"
else
    fail "Testes emergentes falharam"
fi

# Gate 2: Backward compatibility
echo ""
echo "Gate 2: Backward compatibility"
if pytest tests/integration/test_full_flow.py -v; then
    pass "Testes de integração existentes"
else
    fail "Backward compatibility quebrada"
fi

# Gate 3: Performance benchmark
echo ""
echo "Gate 3: Performance benchmark"
python - <<'PY'
import asyncio
import time
from src.agents.supervisor_agent import SupervisorAgent

async def benchmark():
    supervisor = SupervisorAgent()

    # Benchmark paralelo
    start = time.perf_counter()
    result = await supervisor.process_task("Status TJSP, TJMG e TJRS")
    elapsed = time.perf_counter() - start

    print(f"⚡ Tempo de execução: {elapsed:.3f}s")

    if result["parallel"] and elapsed < 2.0:
        print("✅ Performance OK (< 2s para 3 tribunais)")
        return True
    else:
        print(f"❌ Performance abaixo do esperado")
        return False

if asyncio.run(benchmark()):
    exit(0)
else:
    exit(1)
PY

if [ $? -eq 0 ]; then
    pass "Benchmark de performance"
else
    fail "Performance abaixo do esperado"
fi

# Gate 4: Cobertura de código
echo ""
echo "Gate 4: Cobertura de código"
coverage run -m pytest tests/ -q
coverage report --fail-under=90

if [ $? -eq 0 ]; then
    pass "Cobertura mantida >90%"
else
    fail "Cobertura abaixo de 90%"
fi

# Resultado final
echo ""
echo "=========================================="
echo "✅ Passed: $PASS"
echo "❌ Failed: $FAIL"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo "🎉 ONDA 1 (Parallelization) VALIDADA COM SUCESSO"
    exit 0
else
    echo "💥 VALIDAÇÃO FALHOU - CORRIGIR ANTES DE PROSSEGUIR"
    exit 1
fi
