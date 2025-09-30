#!/bin/bash
set -euo pipefail

echo "🏆 BuildToFlip v6.1 - Certificação Oficial"
echo "=========================================="
echo ""

SCORE=0
MAX_SCORE=0

# Função de teste
check() {
    local description="$1"
    local command="$2"
    ((MAX_SCORE+=1))

    if eval "$command" > /dev/null 2>&1; then
        echo "✅ $description"
        ((SCORE+=1))
        return 0
    else
        echo "❌ $description"
        return 1
    fi
}

echo "📋 FASE 1: FOUNDATION"
check "Guardrails presentes" "grep -q 'class SafeAgentBase' src/core/safe_agent_base.py"
check "Ledger funcionando" "grep -q 'class DecisionLedger' src/utils/ledger.py"
check "SupervisorAgent operacional" "python -c 'from src.agents.supervisor_agent import SupervisorAgent; SupervisorAgent()'"
check "TribunalAgent operacional" "python -c 'from src.agents.tribunal_agent import TribunalAgent; TribunalAgent(\"TJSP\")'"

echo ""
echo "📋 FASE 2: CAPABILITIES"
check "RAG integrado" "grep -q 'self.memory = memory_system' src/agents/tribunal_agent.py"
check "ArchitectAgent com CoT" "grep -q 'reason_with_cot' src/agents/architect_agent.py"
check "process_task_advanced implementado" "grep -q 'async def process_task_advanced' src/agents/supervisor_agent.py"
check "AgentMemorySystem presente" "python -c 'from src.memory.agent_memory import AgentMemorySystem'"

echo ""
echo "📋 FASE 3: COLLABORATION"
check "WeightedConsensusEngine presente" "grep -q 'class WeightedConsensusEngine' src/consensus/weighted_voting.py"
check "Consensus no supervisor" "grep -q 'self.consensus_engine' src/agents/supervisor_agent.py"
check "Multi-tribunal detection" "grep -q '_extract_tribunals_from_reasoning' src/agents/supervisor_agent.py"
check "UnifiedOrchestrator disponível" "python -c 'from src.orchestration.unified_orchestrator import UnifiedOrchestrator'"

echo ""
echo "📋 FASE 4: INTELLIGENCE"
check "UnifiedOrchestrator exposto" "grep -q 'unified_orchestrator = UnifiedOrchestrator' src/api/main.py"
check "Endpoint /advanced presente" "grep -q '/api/v1/tasks/advanced' src/api/main.py"
check "Endpoint /compare presente" "grep -q '/api/v1/tasks/compare' src/api/main.py"
check "A/B Testing disponível" "test -f src/evaluation/ab_testing.py"

echo ""
echo "📋 TESTES FUNCIONAIS"

# Iniciar servidor temporário
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 > /tmp/cert_server.log 2>&1 &
CERT_PID=$!
sleep 5

check "Servidor responde /health" "curl -sf http://localhost:8001/health"
check "Endpoint simples funciona" "curl -sf -X POST http://localhost:8001/api/v1/tasks -H 'Content-Type: application/json' -d '{\"task_description\":\"teste\"}'"
check "Endpoint avançado funciona" "curl -sf -X POST http://localhost:8001/api/v1/tasks/advanced -H 'Content-Type: application/json' -d '{\"task_description\":\"teste\"}'"

# Parar servidor
kill $CERT_PID 2>/dev/null
wait $CERT_PID 2>/dev/null || true

echo ""
echo "=========================================="
echo "RESULTADO DA CERTIFICAÇÃO"
echo "=========================================="
echo "Pontuação: $SCORE / $MAX_SCORE"
echo ""

PERCENT=$((SCORE * 100 / MAX_SCORE))

if [ $PERCENT -ge 95 ]; then
    echo "🏆 CERTIFICADO v6.1 - EXCELENTE ($PERCENT%)"
    echo "   Status: PRODUÇÃO"
    exit 0
elif [ $PERCENT -ge 80 ]; then
    echo "✅ CERTIFICADO v6.1 - BOM ($PERCENT%)"
    echo "   Status: STAGING"
    exit 0
else
    echo "❌ REPROVADO ($PERCENT%)"
    echo "   Status: Corrigir falhas"
    exit 1
fi
