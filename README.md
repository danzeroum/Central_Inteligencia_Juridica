# Central de Inteligência Jurídica

Plataforma multiagente de inteligência jurídica com coordenação autônoma, consenso ponderado e aprendizado contínuo.

## Arquitetura

Sistema baseado em agentes especializados coordenados por um SupervisorAgent:

- **SupervisorAgent** — Orquestrador principal (identifica tribunais, delega tarefas)
- **TribunalAgent** — Agentes especializados por tribunal (TJSP, TJMG, TJRS, TJRJ, STF)
- **ArchitectAgent** — Raciocínio Chain-of-Thought para planejamento estratégico
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

## Stack Técnica

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

## Setup Rápido

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

Stack mínimo (app + Postgres + Redis + observabilidade):

```bash
docker-compose up -d
curl http://localhost:8000/health
```

### Rodar TUDO em Docker (modo real) e escalar

Sobe o stack completo — sem modo simulado: Postgres (persistência), ChromaDB
(RAG), MinIO (documentos), Celery (jobs), **Ollama (IA local)** — e publica a
porta do app para acesso local.

```bash
# 1. Preset turnkey (edite as senhas TROQUE_*)
cp .env.docker.example .env

# 2. Rede externa exigida pelo compose base + tabelas do banco
docker network create btv-prod-net
docker compose --profile migrate run --rm migrate          # alembic upgrade head

# 3. Stack completo (app publicado em :8000 via override local)
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  --profile chromadb --profile storage --profile workers --profile llm up -d

# 4. Baixe o modelo de IA e acesse
docker compose exec ollama ollama pull llama3
open http://localhost:8000/app      # operator/operator (demo só em dev)
```

### Pronto para escalar (horizontal)

O estado é externalizável: com `RATE_LIMIT_BACKEND=redis`, `LEDGER_BACKEND=redis`
e `HITL_BACKEND=redis` (já no `.env.docker.example`), o app fica **stateless** e
várias réplicas compartilham fila HITL, rate-limit e ledger via Redis; a memória
vetorial vai para o ChromaDB remoto e os arquivos para o MinIO/S3.

```bash
# N réplicas do app atrás do ingress (estado no Redis/Postgres/Chroma/MinIO):
docker compose -f docker-compose.yml --profile chromadb --profile storage \
  --profile workers up -d --scale agent-system=3
```

Para nuvem, troque os serviços `postgres`/`redis`/`minio` do compose por
endpoints gerenciados (RDS/ElastiCache/S3) apontando as mesmas variáveis do
`.env` — o app não muda.

## Testes

```bash
# Testes unitarios
pytest tests/unit/ -v

# Unit + integracao
pytest tests/unit tests/integration -q

# Com cobertura (relatorio HTML em htmlcov/index.html)
pytest tests/unit --cov=src --cov-report=term-missing --cov-report=html
```

## Documentação

| Documento | Conteudo |
|---|---|
| [Guia de Uso](docs/GUIA_DE_USO.md) | Instalacao + autenticacao + 15 casos de teste (curl) |
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

## Estrutura de Diretórios

```
Central_Inteligencia_Juridica/
+-- src/
|   +-- agents/          # Supervisor, Tribunal, Architect agents
|   +-- consensus/       # WeightedConsensusEngine
|   +-- orchestration/   # UnifiedOrchestrator (orquestração em produção)
|   +-- planning/        # AdaptivePlanner / AdaptiveReplanner
|   +-- evaluation/      # ContinuousEvaluator, TrajectoryEvaluator
|   +-- parallel/        # execução paralela de tarefas
|   +-- chains/          # cadeias de raciocínio/prompts
|   +-- core/            # SafeAgentBase e primitivas de execução
|   +-- safety/          # detecção/redação de PII, guardrails
|   +-- hitl/            # ProgressiveAutonomyManager, HITL Queue
|   +-- memory/          # VectorMemory, AgentMemorySystem
|   +-- protocols/       # A2A protocol, SafetyProtocol
|   +-- routing/         # IntentClassifier, LearningRouter, TribunalIdentifier
|   +-- services/        # clientes externos (Câmara, Ollama)
|   +-- training/        # TrainingManager (treinamento contínuo)
|   +-- tools/           # TribunalAPIAdapter, CircuitBreaker, sandbox, schemas
|   +-- api/             # FastAPI (endpoints + auth + static/spa servida em /app)
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
+-- pyproject.toml
```

## Monitoramento

| Servico | URL |
|---|---|
| Health Check | http://localhost:8000/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (usuário/senha via `GF_SECURITY_ADMIN_USER`/`GF_SECURITY_ADMIN_PASSWORD` no `.env`) |

## Cobertura de Código (30% overall)

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

## Licença

Distribuído sob a licença [Apache License 2.0](LICENSE).
