# Central de Inteligencia Juridica

Plataforma multiagente de inteligencia juridica com coordenacao autonoma, consenso ponderado e aprendizado continuo.

## Arquitetura

Sistema baseado em agentes especializados coordenados por um SupervisorAgent:

- **SupervisorAgent** — Orquestrador principal (identifica tribunais, delega tarefas)
- **TribunalAgent** — Agentes especializados por tribunal (TJSP, TJMG, TJRS, TJRJ, STF)
- **ArchitectAgent** — Raciocimento Chain-of-Thought para planejamento estrategico
- **WeightedConsensusEngine** — Consenso ponderado por expertise
- **ProgressiveAutonomyManager** — Autonomia progressiva com HITL (Human-in-the-Loop)
- **DecisionLedger** — Registro persistente de decisoes para auditoria
- **CacheManager** — Cache com Circuit Breaker (Redis + fallback em memoria)
- **InputSanitizer** — Sanitizacao contra XSS e SQL Injection
- **LearningRouter** — Roteamento adaptativo com historico de sucesso/falha
- **VectorMemory** — Memoria vetorial com ChromaDB
- **A2A Protocol** — Comunicacao agente-agente padronizada

```
                    +---------------------+
                    |   SupervisorAgent    |
                    |   (Orquestrador)     |
                    +----------+----------+
                               |
            +------------------+------------------+
            |                  |                  |
  +---------v----------+ +----v------------+ +--v--------------------+
  |   TribunalAgent    | | ArchitectAgent  | | WeightedConsensus     |
  |  (TJSP/TJMG/...)   | | (CoT Planner)   | |    Engine             |
  +--------------------+ +-----------------+ +----------------------+
            |
  +---------v--------------------------------------------------------+
  |  CacheManager | DecisionLedger | VectorMemory | MetricsCollector  |
  |  (Circuit Brk) | (Auditoria)    | (ChromaDB)    | (Prometheus)      |
  +---------------------------------------------------------------+
            |
  +---------v--------------------------------------------------------+
  |  ProgressiveAutonomyManager | InputSanitizer | LearningRouter     |
  |  (HITL Queue)               | (XSS/SQLi)      | (Adaptive)        |
  +---------------------------------------------------------------+
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
git clone https://github.com/danzeroum/Central_Inteligencia_Juridica.git
cd Central_Inteligencia_Juridica

pip install -r requirements.txt
pytest tests/unit/ -v
uvicorn src.api.main:app --reload --port 8000
```

## Frontend (SPA React + Vite)

A interface fica em `frontend/` (React + Vite). O build é gerado em
`src/api/static/spa/` e servido pelo FastAPI em **`/app`** (mesma origem — sem
CORS em produção). A SPA cobre os dois espaços: *Espaço de Trabalho*
(Assistente, Processos, Jurisprudência, Legislativo, Histórico) e *Administração*
(Aprovações HITL, Treinamento, Agentes, Auditoria/Ledger, Autonomia/DMN,
Monitoramento).

> 📘 Novo por aqui? Veja o **[Manual do Estudante de Direito](docs/MANUAL_ESTUDANTE.md)** —
> guia prático de todas as funcionalidades, com roteiro guiado de 15 minutos.

```bash
cd frontend
npm install
npm run build          # gera src/api/static/spa (servido em http://localhost:8000/app)

# Desenvolvimento com hot-reload (proxy /api -> :8000):
npm run dev            # http://localhost:5173
```

> O build (`src/api/static/spa`) é versionado de propósito: o deploy serve os
> estáticos diretamente, sem pipeline Node. Rode `npm run build` após alterar o
> frontend.

## Docker

```bash
docker-compose up -d
curl http://localhost:8000/health
```

## Testes

```bash
# Testes unitarios
pytest tests/unit/ -v

# Unit + integracao
pytest tests/unit tests/integration -q

# Com cobertura (relatorio HTML em htmlcov/index.html)
pytest tests/unit --cov=src --cov-report=term-missing --cov-report=html
```

## Documentacao

| Documento | Conteudo |
|---|---|
| [Manual do Estudante](docs/MANUAL_ESTUDANTE.md) | Todas as funcionalidades da interface |
| [Primeiros passos](docs/tutorials/getting_started.md) | Setup local + primeira consulta |
| [Arquitetura C4](docs/ARCHITECTURE_C4.md) | Contexto -> Codigo + sequencias |
| [ADRs](docs/ADRs/README.md) | Decisoes arquiteturais |
| [Novo dominio/tribunal](docs/ADICIONAR_NOVO_DOMINIO.md) | Como estender via YAML |
| [Troubleshooting](docs/troubleshooting.md) | Problemas comuns |
| [Como contribuir](CONTRIBUTING.md) | Fluxo, qualidade e convencoes |
| [Politica de seguranca](SECURITY.md) | Como reportar vulnerabilidades |
| **API (Swagger)** | http://localhost:8000/docs (gerado do app) |

> A spec OpenAPI versionada (`docs/API/openapi.json`) e gerada por
> `python scripts/dev/export_openapi.py` — a fonte da verdade e o codigo.

## Estrutura de Diretorios

```
Central_Inteligencia_Juridica/
+-- src/
|   +-- agents/          # Supervisor, Tribunal, Architect agents
|   +-- consensus/       # WeightedConsensusEngine
|   +-- hitl/            # ProgressiveAutonomyManager, HITL Queue
|   +-- memory/          # VectorMemory, AgentMemorySystem
|   +-- protocols/       # A2A protocol
|   +-- routing/         # IntentClassifier, LearningRouter
|   +-- tools/           # TribunalAPIAdapter, CircuitBreaker, schemas
|   +-- api/             # FastAPI (endpoints + static/spa servida em /app)
|   +-- utils/           # CacheManager, InputSanitizer, Ledger, Metrics
+-- frontend/            # SPA React + Vite (build -> src/api/static/spa)
+-- tests/
|   +-- unit/            # testes unitarios
|   +-- integration/     # testes de integracao
+-- docs/                # ADRs, manual, arquitetura C4, tutoriais
+-- examples/            # demos do projeto (+ patterns/ genericos)
+-- scripts/dev/         # utilitarios de dev (export_openapi, etc.)
+-- config/              # Configuracoes (routing, agents)
+-- monitoring/          # Prometheus + Grafana
+-- .github/workflows/   # CI/CD
+-- docker-compose.yml
+-- Dockerfile
+-- requirements.txt
+-- pytest.ini
```

## Monitoramento

| Servico | URL |
|---|---|
| Health Check | http://localhost:8000/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

## Cobertura de Codigo (30% overall)

| Modulo | Coverage |
|---|---|
| learning_router | 100% |
| architect_agent | 96% |
| weighted_voting | 90% |
| circuit_breaker | 89% |
| input_sanitizer | 85% |
| cache_manager | 80% |
| tribunal_agent | 76% |
| ledger | 77% |

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): lint, type-check, security scan, tests.

## Licenca

Projeto academico — Central de Inteligencia Juridica
