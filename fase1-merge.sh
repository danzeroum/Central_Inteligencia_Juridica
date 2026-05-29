#!/usr/bin/env bash
# =============================================================================
#  FASE 1 - PARTE 2: Resolucao dos conflitos de merge nos arquivos maiores
#  Esses arquivos exigem decisao de qual branch manter para cada um.
#
#  RECOMENDACAO: Manter origin/codex para supervisor_agent e api/main
#  (funcionalidade avancada) e HEAD para tribunal_agent (API client robusto).
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
#  ESTRATEGIA DE RESOLUCAO POR ARQUIVO
# =============================================================================
# Cada arquivo abaixo usa git checkout para escolher UMA versao limpa,
# eliminando os marcadores de conflito.

echo "=========================================================================="
echo -e "${BLUE} FASE 1 - PARTE 2: Resolucao de conflitos de merge${NC}"
echo "=========================================================================="
echo ""
echo "Estrategia recomendada para cada arquivo:"
echo ""
echo "  ARQUIVO                          | BRANCH RECOMENDADO"
echo "  ----------------------------------|-------------------------------"
echo "  src/agents/supervisor_agent.py    | origin/codex (funcionalidade)"
echo "  src/agents/tribunal_agent.py     | HEAD (API client robusto)"
echo "  src/agents/architect_agent.py     | origin/codex (standalone)"
echo "  src/api/main.py                   | origin/codex (endpoints avancados)"
echo "  src/consensus/weighted_voting.py  | origin/codex (clustering)"
echo "  src/memory/agent_memory.py        | origin/codex (wrapper limpo)"
echo "  src/tools/rag_tool.py             | origin/codex (wrapper limpo)"
echo "  src/routing/learning_router.py    | origin/codex (RouteStats)"
echo "  src/utils/cache_manager.py        | origin/codex (circuit breaker)"
echo "  src/utils/ledger.py               | HEAD (persistencia JSONL)"
echo "  src/utils/metrics_collector.py   | HEAD (Prometheus real)"
echo "  src/orchestration/unified_orch    | origin/codex (wrapper limpo)"
echo "  src/hitl/progressive_autonomy.py | origin/codex (HITL queue)"
echo "  tests/integration/test_full_flow  | origin/codex (async pytest)"
echo "  docs/troubleshooting.md           | origin/codex (Python nativo)"
echo ""

read -p "Deseja aplicar todas as resolucoes automaticas? [y/N]: " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Operacao cancelada. Aplique manualmente com: git checkout --theirs/ours <arquivo>"
    exit 0
fi

# =============================================================================
#  Resolucoes - Origin/Codex Branch (funcionalidade avancada)
# =============================================================================
log_info "Resolvendo conflitos - escolhendo origin/codex onde indicado..."

# Supervisor - origin/codex tem A2A, consensus, memory, parallel
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/agents/supervisor_agent.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/agents/supervisor_agent.py 2>/dev/null || true
    git add src/agents/supervisor_agent.py 2>/dev/null || true
    log_ok "supervisor_agent.py -> origin/codex (A2A, consensus, parallel)"
else
    log_warn "Branch origin/codex nao disponivel para supervisor_agent.py"
    log_warn "Resolva manualmente: git mergetool"
fi

# Architect - origin/codex e standalone com CoT legal
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/agents/architect_agent.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/agents/architect_agent.py 2>/dev/null || true
    git add src/agents/architect_agent.py 2>/dev/null || true
    log_ok "architect_agent.py -> origin/codex (standalone com CoT)"
fi

# API main - origin/codex tem HITL, training, A2A, MCP
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/api/main.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/api/main.py 2>/dev/null || true
    git add src/api/main.py 2>/dev/null || true
    log_ok "api/main.py -> origin/codex (HITL, training, A2A, MCP)"
fi

# Consensus - origin/codex tem clustering
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/consensus/weighted_voting.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/consensus/weighted_voting.py 2>/dev/null || true
    git add src/consensus/weighted_voting.py 2>/dev/null || true
    log_ok "weighted_voting.py -> origin/codex (proposal clustering)"
fi

# Agent Memory - origin/codex usa wrapper limpo
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/memory/agent_memory.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/memory/agent_memory.py 2>/dev/null || true
    git add src/memory/agent_memory.py 2>/dev/null || true
    log_ok "agent_memory.py -> origin/codex (VectorMemory wrapper)"
fi

# RAG Tool - origin/codex usa wrapper limpo
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/tools/rag_tool.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/tools/rag_tool.py 2>/dev/null || true
    git add src/tools/rag_tool.py 2>/dev/null || true
    log_ok "rag_tool.py -> origin/codex (VectorMemory wrapper)"
fi

# Learning Router - origin/codex com RouteStats
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/routing/learning_router.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/routing/learning_router.py 2>/dev/null || true
    git add src/routing/learning_router.py 2>/dev/null || true
    log_ok "learning_router.py -> origin/codex (RouteStats)"
fi

# Cache Manager - origin/codex com circuit breaker
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/utils/cache_manager.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/utils/cache_manager.py 2>/dev/null || true
    git add src/utils/cache_manager.py 2>/dev/null || true
    log_ok "cache_manager.py -> origin/codex (circuit breaker)"
fi

# Unified Orchestrator - origin/codex wrapper limpo
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/orchestration/unified_orchestrator.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/orchestration/unified_orchestrator.py 2>/dev/null || true
    git add src/orchestration/unified_orchestrator.py 2>/dev/null || true
    log_ok "unified_orchestrator.py -> origin/codex (wrapper)"
fi

# Progressive Autonomy - origin/codex com HITL queue integration
if git show origin/codex/implementar-central-de-inteligencia-juridica:src/hitl/progressive_autonomy.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- src/hitl/progressive_autonomy.py 2>/dev/null || true
    git add src/hitl/progressive_autonomy.py 2>/dev/null || true
    log_ok "progressive_autonomy.py -> origin/codex (HITL queue)"
fi

# Test full flow - origin/codex async tests
if git show origin/codex/implementar-central-de-inteligencia-juridica:tests/integration/test_full_flow.py > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- tests/integration/test_full_flow.py 2>/dev/null || true
    git add tests/integration/test_full_flow.py 2>/dev/null || true
    log_ok "test_full_flow.py -> origin/codex (async pytest)"
fi

# Troubleshooting - origin/codex Python nativo
if git show origin/codex/implementar-central-de-inteligencia-juridica:docs/troubleshooting.md > /dev/null 2>&1; then
    git checkout origin/codex/implementar-central-de-inteligencia-juridica -- docs/troubleshooting.md 2>/dev/null || true
    git add docs/troubleshooting.md 2>/dev/null || true
    log_ok "troubleshooting.md -> origin/codex (Python nativo)"
fi

# =============================================================================
#  Resolucoes - HEAD Branch (melhor implementacao)
# =============================================================================
log_info "Resolvendo conflitos - escolhendo HEAD onde indicado..."

# Tribunal Agent - HEAD tem API client robusto com caching
git checkout HEAD -- src/agents/tribunal_agent.py 2>/dev/null || true
git add src/agents/tribunal_agent.py 2>/dev/null || true
log_ok "tribunal_agent.py -> HEAD (API client com caching)"

# Ledger - HEAD tem persistencia JSONL
git checkout HEAD -- src/utils/ledger.py 2>/dev/null || true
git add src/utils/ledger.py 2>/dev/null || true
log_ok "ledger.py -> HEAD (persistencia JSONL)"

# Metrics Collector - HEAD tem Prometheus real
git checkout HEAD -- src/utils/metrics_collector.py 2>/dev/null || true
git add src/utils/metrics_collector.py 2>/dev/null || true
log_ok "metrics_collector.py -> HEAD (Prometheus real)"

# =============================================================================
#  VALIDACAO FINAL
# =============================================================================
echo ""
log_info "Verificando se restam conflitos..."

REMAINING=$(grep -rl "<<<<<<< HEAD" --include="*.py" --include="*.txt" --include="*.md" . 2>/dev/null || true)
if [ -z "$REMAINING" ]; then
    log_ok "Todos os conflitos foram resolvidos!"
else
    log_warn "Ainda existem conflitos nos seguintes arquivos:"
    for f in $REMAINING; do
        echo "    - $f"
    done
    echo ""
    echo "    Execute: git mergetool"
fi

echo ""
echo "=========================================================================="
echo -e "${GREEN}  PROXIMOS PASSOS:${NC}"
echo "=========================================================================="
echo ""
echo "  1. git status  # Verificar estado"
echo "  2. python -c 'import src'  # Testar import"
echo "  3. python -m pytest tests/ -x  # Rodar testes"
echo "  4. git add -A"
echo "  5. git commit -m 'fix(phase1): resolve all merge conflicts'"
echo ""
echo "=========================================================================="
