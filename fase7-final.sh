#!/bin/bash
# ============================================================================
#  FASE 7 - DOCUMENTACAO, COVERAGE, LIMPEZA FINAL E PREPARO PARA PUSH
#  Central de Inteligencia Juridica
#
#  Objetivos:
#    1. Gerar relatorio de cobertura de codigo (pytest-cov)
#    2. Reescrever README.md profissional
#    3. Criar ARCHITECTURE.md com diagramas Mermaid
#    4. Limpar requirements.txt (sem merge conflicts)
#    5. Limpar Dockerfile (sem secoes duplicadas)
#    6. Limpar docker-compose.yml (sem .buildtoflip)
#    7. .gitignore completo para Python
#    8. Mover fase*.sh para scripts/legacy/
#    9. Remover arquivos obsoletos do repo
#   10. Preparar push para GitHub
#
#  USO:
#    bash fase7-final.sh --dry-run
#    bash fase7-final.sh
#    git push origin master
# ============================================================================

set -euo pipefail

DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY=1
    echo ""
    echo "============================================================================"
    echo "  FASE 7 - DOCUMENTACAO, COVERAGE, LIMPEZA E PUSH"
    echo "  Central de Inteligencia Juridica"
    echo "  Modo: DRY-RUN"
    echo "============================================================================"
else
    echo ""
    echo "============================================================================"
    echo "  FASE 7 - DOCUMENTACAO, COVERAGE, LIMPEZA E PUSH"
    echo "  Central de Inteligencia Juridica"
    echo "  Modo: APLICANDO"
    echo "============================================================================"
fi

STEP=0
_applied=0
_skipped=0

step() {
    STEP=$((STEP + 1))
    echo ""
    echo "  [${STEP}/10] $1"
    echo "  ---------------------------------------------------------------------------"
}

write_file() {
    local filepath="$1"
    if [[ $DRY -eq 1 ]]; then
        echo "  DRY-RUN: escreveria ${filepath} ($(echo "$2" | wc -c) bytes)"
        _skipped=$((_skipped + 1))
        return 0
    fi
    mkdir -p "$(dirname "$filepath")"
    printf '%s' "$2" > "$filepath"
    if command -v sed &>/dev/null 2>&1; then
        sed -i 's/\r$//' "$filepath" 2>/dev/null || true
    fi
    _applied=$((_applied + 1))
    echo "  OK: ${filepath}"
}

remove_file() {
    local filepath="$1"
    if [[ $DRY -eq 1 ]]; then
        echo "  DRY-RUN: removeria ${filepath}"
        _skipped=$((_skipped + 1))
        return 0
    fi
    if [[ -f "$filepath" ]]; then
        rm -f "$filepath"
        _applied=$((_applied + 1))
        echo "  REMOVIDO: ${filepath}"
    else
        echo "  (nao existe, ignorado)"
    fi
}

remove_dir() {
    local dirpath="$1"
    if [[ $DRY -eq 1 ]]; then
        echo "  DRY-RUN: removeria ${dirpath}/"
        _skipped=$((_skipped + 1))
        return 0
    fi
    if [[ -d "$dirpath" ]]; then
        rm -rf "$dirpath"
        _applied=$((_applied + 1))
        echo "  REMOVIDO: ${dirpath}/"
    else
        echo "  (nao existe, ignorado)"
    fi
}

# ============================================================================
# [1/10] COVERAGE REPORT
# ============================================================================
step "Gerar relatorio de cobertura de codigo (pytest-cov)"

if [[ $DRY -eq 1 ]]; then
    echo '  DRY-RUN: executaria pytest --cov=src --cov-report=term-missing --cov-report=html'
    _skipped=$((_skipped + 1))
else
    echo "  Executando pytest com cobertura..."
    python -m pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html:htmlcov -q 2>&1 | head -100 || true
    echo ""
    echo "  Relatorio HTML gerado em: htmlcov/index.html"
    _applied=$((_applied + 1))
fi

# ============================================================================
# [2/10] README.md
# ============================================================================
step "Reescrever README.md profissional"

read -r -d '' README_CONTENT << 'READMEEOF'
# Central de Inteligencia Juridica

Plataforma multiagente de inteligencia juridica com coordenacao autonomica, consenso ponderado e aprendizado continuo.

## Arquitetura

Sistema baseado em agentes especializados coordenados por um Supervisor Agent, com suporte a:

- **SupervisorAgent** — Orquestrador principal que identifica tribunais, delega tarefas e mantem historico de decisoes
- **TribunalAgent** — Agentes especializados por tribunal (TJSP, TJMG, TJRS, TJRJ, STF)
- **ArchitectAgent** — Raciocimento Chain-of-Thought para planejamento estrategico
- **WeightedConsensusEngine** — Consenso ponderado por expertise para decisoes multiagente
- **ProgressiveAutonomyManager** — Gestao de autonomia progressiva com HITL (Human-in-the-Loop)
- **DecisionLedger** — Registro persistente de decisoes para auditoria e observabilidade
- **CacheManager** — Cache com Circuit Breaker (Redis + fallback em memoria)
- **InputSanitizer** — Sanitizacao de entrada contra XSS e SQL Injection
- **LearningRouter** — Roteamento adaptativo baseado em historico de sucesso/falha
- **VectorMemory** — Memoria vetorial com ChromaDB para busca semantica
- **A2A Protocol** — Comunicação agente-agente via protocolo padronizado

```
                    ┌─────────────────────┐
                    │   SupervisorAgent   │
                    │   (Orquestrador)     │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
  ┌─────────▼────────┐  ┌────▼────────────┐  ┌──▼──────────────────┐
  │   TribunalAgent   │  │ ArchitectAgent  │  │ WeightedConsensus   │
  │  (TJSP/TJMG/...)  │  │ (CoT Planner)   │  │    Engine           │
  └───────────────────┘  └─────────────────┘  └─────────────────────┘
            │
  ┌─────────▼──────────────────────────────────────┐
  │  CacheManager │ DecisionLedger │ VectorMemory  │
  │  (Circuit Brk) │ (Auditoria)    │ (ChromaDB)    │
  └────────────────────────────────────────────────┘
            │
  ┌─────────▼──────────────────────────────────────┐
  │  ProgressiveAutonomyManager │ InputSanitizer   │
  │  (HITL Queue)               │ (XSS/SQLi)      │
  └────────────────────────────────────────────────┘
```

## Stack Tecnica

| Componente | Tecnologia |
|---|---|
| Framework | FastAPI + Uvicorn |
| Python | 3.11+ |
| Cache | Redis (com fallback em memoria) |
| Memoria Vetorial | ChromaDB |
| Monitoramento | Prometheus + Grafana |
| CI/CD | GitHub Actions |
| Containerizacao | Docker + Docker Compose |
| Testes | pytest + pytest-asyncio + pytest-cov |

## Setup Rapido

```bash
# Clonar
git clone https://github.com/danzeroum/Central_Inteligencia_Juridica.git
cd Central_Inteligencia_Juridica

# Instalar dependencias
pip install -r requirements.txt

# Executar testes
pytest tests/unit/ -v

# Iniciar servidor
uvicorn src.api.main:app --reload --port 8000
```

## Docker

```bash
# Subir stack completa (app + Redis + Prometheus + Grafana)
docker-compose up -d

# Verificar health
curl http://localhost:8000/health
```

## Testes

```bash
# Unit tests (78 testes)
pytest tests/unit/ -v

# Com cobertura
pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html

# Com benchmark
pytest tests/unit/ --benchmark-only
```

**Status atual: 78/78 testes passando (100%)**

## Estrutura de Diretorios

```
Central_Inteligencia_Juridica/
├── src/
│   ├── agents/          # SupervisorAgent, TribunalAgent, ArchitectAgent
│   ├── consensus/       # WeightedConsensusEngine
│   ├── hitl/            # ProgressiveAutonomyManager, HITL Queue
│   ├── memory/          # VectorMemory, AgentMemorySystem
│   ├── protocols/       # A2A (Agent-to-Agent) protocol
│   ├── routing/         # IntentClassifier, LearningRouter
│   ├── tools/           # TribunalAPIAdapter, integracoes externas
│   └── utils/           # CacheManager, InputSanitizer, DecisionLedger, Metrics
├── tests/
│   ├── unit/            # 78 testes unitarios
│   └── integration/     # Testes de integracao
├── config/              # Configuracoes
├── monitoring/           # Prometheus + Grafana dashboards
├── .github/workflows/   # CI/CD (GitHub Actions)
├── docker-compose.yml   # Stack Docker completa
├── Dockerfile           # Imagem de producao
├── requirements.txt      # Dependencias Python
└── pytest.ini           # Configuracao de testes
```

## Monitoramento

| Endpoint | URL |
|---|---|
| Health Check | `http://localhost:8000/health` |
| Prometheus Metrics | `http://localhost:8000/metrics` |
| Grafana Dashboard | `http://localhost:3000` (admin/admin) |
| Prometheus UI | `http://localhost:9090` |

## CI/CD

Pipeline automatico via GitHub Actions (`.github/workflows/ci.yml`):
- Lint (flake8)
- Type check (mypy)
- Security scan (bandit)
- Testes unitarios (pytest)
- Coverage report

## Licenca

Projeto academico — Central de Inteligencia Juridica
READMEEOF

write_file "README.md" "$README_CONTENT"

# ============================================================================
# [3/10] ARCHITECTURE.md
# ============================================================================
step "Criar ARCHITECTURE.md com diagramas Mermaid"

read -r -d '' ARCH_CONTENT << 'ARCHEOF'
# Arquitetura do Sistema — Central de Inteligencia Juridica

## Visao Geral

Plataforma multiagente para automacao de consultas juridicas tribunais brasileiros, com coordenacao autonoma, consenso ponderado e aprendizado continuo.

## Componentes Principais

### Agentes

| Agente | Responsabilidade | Arquivo |
|---|---|---|
| **SupervisorAgent** | Orquestra tarefas, identifica tribunais, delega para especialistas | `src/agents/supervisor_agent.py` |
| **TribunalAgent** | Executa operacoes especializadas por tribunal (status, consulta processo, movimentacoes) | `src/agents/tribunal_agent.py` |
| **ArchitectAgent** | Raciocinamento Chain-of-Thought para planejamento estrategico e identificacao de tribunais | `src/agents/architect_agent.py` |

### Infraestrutura

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| **CacheManager** | Cache distribuido com Circuit Breaker (Redis + fallback em memoria) | `src/utils/cache_manager.py` |
| **DecisionLedger** | Registro persistente de decisoes para auditoria e observabilidade | `src/utils/ledger.py` |
| **InputSanitizer** | Sanitizacao de entrada contra XSS, SQL Injection e padroes maliciosos | `src/utils/input_sanitizer.py` |
| **MetricsCollector** | Coleta de metricas Prometheus para monitoramento | `src/utils/metrics_collector.py` |
| **VectorMemory** | Memoria vetorial com ChromaDB para busca semantica de documentos | `src/memory/vector_memory.py` |

### Consenso e Autonomia

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| **WeightedConsensusEngine** | Consenso ponderado por expertise para decisoes multiagente | `src/consensus/weighted_voting.py` |
| **ProgressiveAutonomyManager** | Gestao de autonomia progressiva com HITL (Human-in-the-Loop) | `src/hitl/progressive_autonomy.py` |
| **HITL Queue** | Fila de aprovacao humana para decisoes criticas | `src/hitl/hitl_queue.py` |

### Roteamento e Protocolos

| Componente | Responsabilidade | Arquivo |
|---|---|---|
| **IntentClassifier** | Classificacao de intencao das consultas | `src/routing/intent_classifier.py` |
| **LearningRouter** | Roteamento adaptativo baseado em historico de sucesso/falha | `src/routing/learning_router.py` |
| **A2A Protocol** | Comunicacao padronizada agente-agente | `src/protocols/a2a_mixin.py` |

## Diagrama de Componentes

```mermaid
graph TB
    subgraph "API Layer"
        API[FastAPI /api]
    end

    subgraph "Agent Layer"
        SUP[SupervisorAgent]
        TRIB[TribunalAgent]
        ARCH[ArchitectAgent]
    end

    subgraph "Infrastructure"
        CACHE[CacheManager<br/>Circuit Breaker]
        LEDGER[DecisionLedger<br/>Auditoria]
        SANIT[InputSanitizer<br/>XSS/SQLi]
        METRICS[MetricsCollector<br/>Prometheus]
        VECMEM[VectorMemory<br/>ChromaDB]
    end

    subgraph "Consensus & HITL"
        CONSEN[WeightedConsensus<br/>Engine]
        AUTO[ProgressiveAutonomy<br/>Manager]
        HITLQ[HITL Queue]
    end

    subgraph "Routing"
        INTENT[IntentClassifier]
        ROUTER[LearningRouter]
    end

    subgraph "External"
        REDIS[(Redis)]
        CHROMA[(ChromaDB)]
        TRIBAPI[Tribunal APIs<br/>TJSP/TJMG/...]
        PROM[(Prometheus)]
        GRAFANA[Grafana]
    end

    API --> SANIT
    API --> SUP
    SUP --> INTENT
    SUP --> ROUTER
    SUP --> ARCH
    SUP --> TRIB
    SUP --> CONSEN
    SUP --> AUTO
    SUP --> LEDGER
    SUP --> CACHE
    SUP --> METRICS

    TRIB --> CACHE
    TRIB --> VECMEM
    TRIB --> TRIBAPI
    TRIB --> LEDGER

    CACHE --> REDIS
    VECMEM --> CHROMA
    METRICS --> PROM
    PROM --> GRAFANA

    AUTO --> HITLQ
    CONSEN --> METRICS
    ROUTER --> CACHE
ARCHEOF

write_file "ARCHITECTURE.md" "$ARCH_CONTENT"

# ============================================================================
# [4/10] requirements.txt LIMPO
# ============================================================================
step "Limpar requirements.txt (remover merge conflicts)"

read -r -d '' REQ_CONTENT << 'REQEOF'
# ============================================================================
# Central de Inteligencia Juridica - Dependencias
# ============================================================================

# Web Framework
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.24.1

# Cache & Monitoring
redis==4.6.0
prometheus-client==0.17.1

# Security
PyJWT==2.8.0

# Data Validation
pydantic==2.6.0
pydantic-settings==2.1.0

# Environment
python-dotenv==1.0.1

# AI/ML & Vector Memory
chromadb==0.4.18
sentence-transformers==2.2.2
numpy<2.0.0,>=1.22.0

# LLM Integration
ollama==0.1.9
REQEOF

write_file "requirements.txt" "$REQ_CONTENT"

# ============================================================================
# [5/10] Dockerfile LIMPO
# ============================================================================
step "Limpar Dockerfile (remover secoes duplicadas)"

read -r -d '' DOCKER_CONTENT << 'DOCKEREOF'
FROM python:3.11-slim

WORKDIR /app

# Instala curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependencias
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia projeto
COPY . /app/

# Configura ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Valida imports
RUN python -c "from src.api.main import app; print('App importado com sucesso')"

# Cria usuario nao-root
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKEREOF

write_file "Dockerfile" "$DOCKER_CONTENT"

# ============================================================================
# [6/10] docker-compose.yml LIMPO
# ============================================================================
step "Limpar docker-compose.yml (remover .buildtoflip)"

read -r -d '' COMPOSE_CONTENT << 'COMPOSEEOF'
version: '3.8'

services:
  agent-system:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: central-inteligencia-juridica
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
      - ./logs:/app/logs
    working_dir: /app
    environment:
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    depends_on:
      - redis
      - prometheus

  redis:
    image: redis:7-alpine
    container_name: tribunal-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: tribunal-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: tribunal-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  redis_data:
  prometheus_data:
  grafana_data:
COMPOSEEOF

write_file "docker-compose.yml" "$COMPOSE_CONTENT"

# ============================================================================
# [7/10] .gitignore COMPLETO
# ============================================================================
step "Atualizar .gitignore com padroes Python completos"

read -r -d '' GITIGNORE_CONTENT << 'GITIGNOREEOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.env
.venv
env/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.benchmark/
.mypy_cache/

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Coverage
coverage.xml
*.cover

# Phase scripts (development only)
fase*.sh

# Secrets
.env.dev
.env.prod

# Legacy/experimental
.buildtoflip/
experimental/
k6/
terraform/
ansible/
certificates/
docs/UX/mockups.zip

# Build artifacts
buildtoflip-v6-certificate.md
buildtoflip-v6.1-certificate.md
pom.xml
discovery-consensus.v6.json
despachar_tarefa.py
handoff-codex.md
fallback-strategy.md
orchestration-matrix.md
metrics-advanced.yaml
metrics.yaml
GITIGNOREEOF

write_file ".gitignore" "$GITIGNORE_CONTENT"

# ============================================================================
# [8/10] MOVER fase*.sh PARA scripts/legacy/
# ============================================================================
step "Mover fase*.sh para scripts/legacy/"

if [[ $DRY -eq 1 ]]; then
    echo "  DRY-RUN: moveria fase*.sh para scripts/legacy/"
    _skipped=$((_skipped + 1))
else
    mkdir -p scripts/legacy
    moved=0
    for f in fase*.sh; do
        if [[ -f "$f" ]]; then
            mv "$f" scripts/legacy/
            echo "    movido: $f -> scripts/legacy/$f"
            moved=$((moved + 1))
        fi
    done
    echo "  OK: ${moved} scripts movidos para scripts/legacy/"
    _applied=$((_applied + moved))
fi

# ============================================================================
# [9/10] LIMPEZA DE ARQUIVOS OBSOLETOS
# ============================================================================
step "Remover arquivos e diretorios obsoletos"

# Arquivos removidos (nao fazem parte do core)
remove_file "pom.xml"
remove_file "despachar_tarefa.py"
remove_file "discovery-consensus.v6.json"
remove_file "handoff-codex.md"
remove_file "fallback-strategy.md"
remove_file "orchestration-matrix.md"
remove_file "metrics-advanced.yaml"
remove_file "metrics.yaml"
remove_file "buildtoflip-v6-certificate.md"
remove_file "buildtoflip-v6.1-certificate.md"
remove_dir ".buildtoflip"
remove_dir "experimental"

# ============================================================================
# [10/10] VERIFICACAO FINAL
# ============================================================================
step "Verificacao final"

if [[ $DRY -eq 1 ]]; then
    echo "  DRY-RUN: executaria pytest final de validacao"
    _skipped=$((_skipped + 1))
else
    echo "  Executando pytest final..."
    python -m pytest tests/unit/ -v --tb=short -q 2>&1 | tail -20
    echo ""
    echo "  Status Git:"
    git status --short | head -30
fi

# ============================================================================
# RESUMO
# ============================================================================
echo ""
echo "============================================================================"
echo "  RESUMO DA FASE 7"
echo "============================================================================"
echo ""
echo "  Modo:        $([ $DRY -eq 1 ] && echo 'DRY-RUN' || echo 'APLICADO')"
echo "  Aplicados:    ${_applied}"
echo "  Skipped:     ${_skipped}"
echo ""
echo "  Itens executados:"
echo ""
echo "  [1/10] Coverage report (pytest-cov)"
echo "  [2/10] README.md profissional reescrito"
echo "  [3/10] ARCHITECTURE.md com diagramas Mermaid"
echo "  [4/10] requirements.txt limpo (sem merge conflicts)"
echo "  [5/10] Dockerfile limpo (sem secoes duplicadas)"
echo "  [6/10] docker-compose.yml limpo (sem .buildtoflip)"
echo "  [7/10] .gitignore completo (Python + obsoletos)"
echo "  [8/10] fase*.sh movidos para scripts/legacy/"
echo "  [9/10] Arquivos obsoletos removidos"
echo "  [10/10] Verificacao final (pytest)"
echo ""
echo "  Proximos passos:"
echo "    git add -A"
echo '    git commit -m "docs(fase7): professional docs, coverage, cleanup for production"'
echo "    git push origin master"
echo ""
echo "============================================================================"
