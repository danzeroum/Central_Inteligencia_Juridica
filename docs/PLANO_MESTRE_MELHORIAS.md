# Plano Mestre de Melhorias — Central de Inteligência Jurídica

> **Documento consolidado e validado.** Reúne cinco análises de áreas distintas
> (Plano Mestre, BPM, Arquitetura Docker, Diagnóstico de API Design e uma análise
> externa "Criptotrade") num único plano, **validado linha a linha contra o código
> real** do repositório. As notas de reconciliação separam o que é trabalho real
> e acionável do que foi importado de outros codebases ou já está implementado.

## Contexto

Cinco documentos de análise foram produzidos por agentes/avaliadores diferentes e
pediam consolidação. Ao validar cada alegação contra o repositório real
(`src/api/main.py`, `src/agents/*`, `docker-compose.yml`, ADRs, CHANGELOG, `tests/`),
o achado central — e a sugestão mais significativa — é que **boa parte do conteúdo
dos documentos não corresponde a este repositório**. Ironicamente, é exatamente o gap
"processo documentado vs. processo real" que o documento de BPM alertava.

Este plano consolida tudo, mas com **notas de reconciliação** que distinguem o real do
importado/já-feito, e ordena o trabalho genuinamente acionável.

---

## 1. Matriz de Reconciliação (a validação — leia primeiro)

| Bloco da análise | Veredicto | Evidência no repo |
|---|---|---|
| **Auditoria "Z.AI Skills"** (57 skills, 0% cobertura, God Modules `pdf.py` 11.5k LOC, `web-reader.ts`, `image-generation.ts`, Quiz Mastery, Stock Analysis, SEC-01…05) | ❌ **Codebase errado** | Este repo é Python/FastAPI puro. Não há sistema de skills, nem TypeScript, nem engines PDF/DOCX/XLSX. Nada de SEC-01…05 existe aqui. |
| **Documento "Criptotrade"** (exchange_client, strategy/risk/execution agents, DCA, Binance/Kraken, ledger de trades) | ❌ **Projeto diferente** | Zero referências a crypto/trading. `ledger.py` aqui é auditoria LGPD de decisões; `recovery_agent.py` é remediação do sistema jurídico. |
| **"Implementar cache / observabilidade / LGPD / structured logging do zero"** | ⚠️ **Já implementado** | `src/utils/cache_manager.py` (Redis+circuit breaker), `logging_config.py` (JSON+correlation_id), `tracing.py` (OTel), Prometheus/Grafana/Alertmanager/Jaeger no compose, `src/api/lgpd_endpoints.py`, `src/safety/pii.py`. |
| **"Anti-pattern LLM-como-fonte-de-dados"** | ⚠️ **Já é ADR** | ADR-008 (Tool Use + `TribunalAPIAdapter` com fallback). Princípio já codificado. |
| **"Padrões de API REST / versionamento"** | ⚠️ **Já é ADR** | ADR-003 (padrões, "Aceita") + ADR-004 (API do SupervisorAgent, RFC 7807) — **documentos distintos e complementares**; ler ADR-004 antes da §2. |
| **Diagnóstico de API Design (doc 5): API-01…07** | ✅ **REAL e verificado** | Confirmado linha a linha em `src/api/main.py` (912 linhas) e `supervisor_agent.py`. Ver §2. |
| **`task_history` em memória** | ✅ **REAL** | `supervisor_agent.py:37` — `List[Dict]`, perde-se no restart. |
| **Cobertura "0%"** | ❌ **Impreciso** | É **~30% overall**; `learning_router` 100%, `architect_agent` 96%, `weighted_voting` 90%, `cache_manager` 80%, `tribunal_agent` 76%. 38 arquivos de teste. |
| **Postgres/MinIO/nginx/Loki no design Docker** | ⚠️ **Proposto, não existe** | Compose atual: app + Redis + observabilidade. Postgres é ADR-002 (status "Proposta", checkboxes desmarcados). |
| **Skill "Busca de Jurisprudência"** | ⚠️ **Parcial, já existe** | `src/agents/agente_jurisprudencia.py` + `agente_legislativo.py` + `TribunalAgents`. Falta API real (CHANGELOG "Planned for Standard Level"). |

**Sugestão significativa nº 1:** Antes de executar qualquer item, descartar os dois blocos
importados (Z.AI Skills e Criptotrade). Eles inflam o escopo em ~12 meses de trabalho
fictício. O trabalho **real e acionável** está concentrado no doc 5 (API), na persistência
do histórico e na elevação de cobertura.

---

## 2. Frente A — Correções de API Design (prioridade real, doc 5 validado)

Único bloco 100% aplicável. Arquivo central: `src/api/main.py`. **Atenção de
reconciliação:** ADR-003/D12 declara `/tasks`, `/consultar-projetos-lei/` e
`/analise-legislativa/` como **exceções legadas conscientes**. A abordagem é
*aditiva e não-destrutiva*, não "renomear e quebrar".

**Pré-requisito:** ler `docs/ADRs/ADR-004-api-design.md` integralmente antes de criar
`schemas/responses.py` — é documento separado do ADR-003 e pode conter decisões de contrato
(schema de sucesso, RFC 7807) que não devem ser contraditas.

| ID | Correção | Abordagem segura |
|---|---|---|
| API-01 | `/tasks` vs `/api/v1/tasks` duplicados | Manter ambos; `/tasks` vira *deprecated* (header `Deprecation` + doc). Não remover sem ciclo de comunicação. |
| API-02 | Verbo + trailing-slash | Adicionar aliases canônicos `/api/v1/proposicoes-legislativas` e `/api/v1/analises-legislativas`; legados permanecem como exceção ADR-003. |
| API-03 | `sender_id` query param em POST `/a2a/send` | Mover para o body (`A2AMessageRequest`). **Já existe** `_enforce_agent_identity()` amarrando sender ao principal — reutilizar. Baixo risco (sem clientes de produção). |
| API-04 | `/agents/by-capability/{capability}` | Adicionar `GET /api/v1/agents?capability=` como forma canônica; manter path atual se necessário p/ bookmarks. |
| API-05 **(🔴 Crítico — eleva de "Alta")** | GETs com `Dict[str, Any]` sem `response_model` — **viola ADR-003 vigente** (linha 13 exige "OpenAPI com exemplos request/response + erros `application/problem+json`"). É dívida técnica contra decisão **aceita**, não só anti-pattern. | Criar `src/api/schemas/responses.py` com Pydantic models (`AgentListResponse`, `A2AMessageResponse`, `HistoryResponse`, etc.) **com exemplos** (`json_schema_extra`). Declarar `response_model` nos endpoints. |
| API-06 | `/tasks/compare` sem role (2× custo LLM) | Exigir permissão `tasks:compare` via `require_permissions()` (RBAC **já existe** em `src/api/rbac.py`). |
| API-07 | `task_history` em memória | Persistir — ver Frente B. |

Reutilizar: `ProblemDetail` (já em `main.py`), `current_principal`/`require_permissions`
(`rbac.py`), `enforce_rate_limit`. Não recriar infra de auth.

Testes: `tests/integration/test_api_contract.py` — um teste por API-01…07 garantindo
não-regressão (rota canônica existe, 422 quando `sender_id` ausente do body, 403 sem
`tasks:compare`, `response_model` presente no `/openapi.json`).

---

## 3. Frente B — Persistência do Histórico (API-07 + auditoria)

`task_history` em memória é incompatível com auditoria jurídica (LGPD art. 37, Res. CNJ
324/2020). **Nota de reconciliação:** o repo **não tem Postgres** hoje (ADR-002 é
"Proposta"), mas **tem o `DecisionLedger`** (`src/utils/ledger.py`) append-only com backend
`file` ou `redis`.

**Sugestão significativa nº 2 — não introduzir Postgres só por isto.** Duas opções, em ordem
de preferência:

- **B1 (recomendado, baixo custo):** rotear o histórico de tarefas para o `DecisionLedger`
  existente (já redige PII, já tem correlation_id, já tem backend Redis para escala
  horizontal). `GET /api/v1/history` passa a ler do ledger com paginação por cursor.
- **B2 (se houver demanda real de SQL/relatórios):** introduzir Postgres + migration
  `task_history` (UUID, user_id, status check, correlation_id, índices para cursor e
  process-mining). **Pré-requisitos:** (a) ADR-002 está como **"Proposta"** com os 3 checkboxes
  (arquiteto/dev/ops) **desmarcados** — fechá-los antes de provisionar; (b) o ADR-002 já
  pressupõe IaC (cita "módulo de monitoring do **Terraform**"), logo B2 não é "+1 serviço no
  compose" — implica estratégia de deploy mais ampla.

Decisão B1 vs B2 fica para o momento da execução, conforme necessidade de query relacional.

---

## 4. Frente C — Qualidade e Cobertura (reality-checked)

Não é "0% → 80%". É **~30% → meta progressiva**, focando módulos críticos hoje subtestados.

- Elevar cobertura dos caminhos críticos da API (`main.py`, endpoints) e
  `supervisor_agent.py` (orquestração) — hoje os menos cobertos.
- Frameworks já no projeto: `pytest` + `pytest-asyncio` + `pytest-cov` (pyproject).
- Gate de cobertura no CI (`.github/workflows/ci.yml` já roda Black/Bandit/pytest/gitleaks).
- **Descartar** toda a estratégia "testar skills PPT/PDF/XLSX/Quiz" — não existem aqui.

---

## 5. Frente D — Camada BPM/DMN (doc 2, aplicável seletivamente)

- **DMN-02 (roteamento de fonte de dados):** já é a essência do ADR-008 + `TribunalAPIAdapter`.
  Externalizar as regras de fonte para `config/` (YAML), reutilizando o padrão que
  `tribunal_identifier.py` já usa. Codificar como guardrail no `SafetyProtocol` existente.
- **DMN-03 (tolerância a falhas):** o `CircuitBreaker` (`src/tools/circuit_breaker.py`, 89%
  coberto) já implementa CLOSED→OPEN→HALF-OPEN. Não recriar; documentar como a realização
  concreta da DMN-03.
- **Process Mining (BPMN AS-IS/TO-BE):** logs estruturados + correlation_id já existem
  (`logging_config.py`). Emitir eventos compatíveis com XES sobre o ledger para permitir
  mineração futura (ProM/Celonis). Baixo esforço, alto valor analítico.
- **Descartar:** os swimlanes de "Geração de Peça/Áudio/Contrato" — dependem de skills
  inexistentes (ver §7).

---

## 6. Frente E — Arquitetura/Infra (doc 3 reconciliado)

O design Docker proposto descreve um sistema que **em ~70% já existe** de outra forma.

- ✅ **Já existe:** Redis, Prometheus, Grafana, Alertmanager, Jaeger/OTel, FastAPI,
  healthchecks, rate-limit Redis, cache Redis, structured logging.
- ⚠️ **Proposto e ausente, avaliar custo/benefício real:** **Postgres** (só se Frente B2),
  **MinIO** (só se surgir geração de artefatos pesados — ver §7), **nginx** (só se houver
  necessidade de TLS termination/redirects 301 dos endpoints legados), **Loki** (logs hoje
  vão a stdout; adicionar só se faltar agregação).
- ❌ **Descartar:** a decomposição em microsserviços `worker-docs/audio/research/training` —
  pressupõe os God Modules e skills do projeto Z.AI, que não existem.
- ✅ **Documentação C4:** já existe `docs/ARCHITECTURE_C4.md`. Incorporar os diagramas de
  sequência úteis do doc 3 a esse arquivo, em vez de criar novo.

---

## 7. Frente F — Roadmap de Skills Jurídicas (posicionamento por maturidade real)

Cada "skill" tem maturidade diferente. Ordenado por alinhamento com o DNA + presença no
roadmap oficial (CHANGELOG):

1. **Busca de Jurisprudência — ✅ já parcial, prioridade imediata.**
   Existe `agente_jurisprudencia.py` + `agente_legislativo.py` + `TribunalAgents`; a SPA já tem
   a tela. Falta **integração com APIs reais** (PJe/e-SAJ/CNJ/Jusbrasil) — já está em CHANGELOG
   "Planned for Standard Level". Infra pronta (`TribunalAPIAdapter` + `CircuitBreaker`). Esforço
   baixo, risco médio (resultado desatualizado).
   **Pré-requisito:** `ADR-008-real-apis.md` tem **20,7 KB — é de longe o maior ADR do projeto**
   (o próximo tem 9 KB). Quase certamente define contratos de integração, estratégias de fallback
   e critérios de aceitação dos tribunais. Ler **integralmente** antes desta frente; ele **guia**
   a implementação da `TribunalAPIAdapter`, não o contrário.

2. **Geração de Petições — ⚠️ ausente, coerente com DNA.**
   Não há `agente_peticao`/`/api/v1/peticoes`. Construir `AgenteDocumentos` reutilizando
   `ArchitectAgent` (CoT), `VectorMemory` (templates+jurisprudência) e LLM. **HITL obrigatório**
   (`ProgressiveAutonomyManager` já existe) antes de qualquer output. Risco alto (responsabilidade
   profissional). Se gerar arquivos pesados → aí sim avaliar MinIO (§6).
   **Ajuste de risco (obrigatório):** o `response_model` deve conter um campo `disclaimer` fixo —
   *"Rascunho gerado por IA; não substitui revisão de advogado habilitado (OAB)."* — por exigência
   do Estatuto da OAB (Lei 8.906/94, art. 1º), evitando caracterização de exercício ilegal da
   advocacia pela plataforma.

3. **Análise de Contratos — ⚠️ ausente, coerente com DNA.**
   Hoje cairia genericamente em `POST /api/v1/tasks`. Skill dedicada exige ontologia contratual
   (cláusulas abusivas CDC art. 51 / CC art. 424) e schema de output estruturado. Risco alto
   (cláusula perdida). HITL obrigatório.

4. **Calculadora de Prazos — ❌ ausente, fora do DNA atual, alto valor / alto risco.**
   É **determinística, não-LLM**. Lib separada da stack de agentes, com calendário de feriados por
   comarca (CNJ) e testes exaustivos. Erro = preclusão. NÃO usar LLM para o cálculo; LLM no máximo
   interpreta o resultado. HITL obrigatório.
   **Ajuste de risco (mecanismo, não só intenção):** enquanto a lib determinística não existir e
   for auditada, adicionar regra de **bloqueio explícito** no `IntentClassifier`
   (`src/routing/intent_classifier.py`, já estruturado com `ClassifiedIntent.operacao`): a intenção
   `prazo_processual` deve retornar `{"error": "Consulte um advogado ou o sistema do tribunal para
   prazos processuais"}` — impede que o `SupervisorAgent.process_task` roteie a pergunta ao LLM por
   engano.

5. **Briefing em Áudio — ❌ ausente, é modalidade de entrega, não skill jurídica.**
   Pós-processador TTS sobre `SuccessfulTaskResponse.supervisor_result`. Ortogonal aos agentes,
   menor acoplamento, menor impacto no valor jurídico. Opcional/última prioridade.

**Regra transversal:** dados normativos sempre via API real (ADR-008); output jurídico sempre passa
por HITL; disclaimer obrigatório sobre limitações.

---

## 8. Sequenciamento Consolidado

| Fase | Conteúdo | Base no repo |
|---|---|---|
| **F0 — Validação** | Internalizar a matriz de reconciliação; descartar Z.AI/Criptotrade | Este documento |
| **F1 — API (Frente A+B)** | API-01…07 de forma aditiva; histórico no DecisionLedger | `main.py`, `ledger.py`, `rbac.py` |
| **F2 — Qualidade (Frente C)** | Cobertura ~30% → alvo nos caminhos críticos; gate no CI | `tests/`, `ci.yml` |
| **F3 — Jurisprudência real (Frente F.1)** | Conectar APIs reais dos tribunais | `agente_jurisprudencia.py`, `TribunalAPIAdapter` |
| **F4 — BPM/DMN explícito (Frente D)** | Externalizar regras de fonte; eventos XES | `SafetyProtocol`, `config/`, `ledger.py` |
| **F5 — Skills novas (Frente F.2–F.5)** | Petições → Contratos → Prazos → Áudio, com HITL | novos agentes sobre infra existente |
| **F6 — Infra sob demanda (Frente E)** | Postgres/MinIO/nginx/Loki **só quando justificado** | `docker-compose.yml`, ADR-002 |

---

## 9. Verificação

- **API:** `pytest tests/integration/test_api_contract.py -v`; subir app
  (`uvicorn src.api.main:app --port 8000`) e validar que `/openapi.json` tem `response_model`
  nos GETs; `curl` em `/api/v1/agents?capability=...`; 403 em `/tasks/compare` sem role.
- **Histórico:** reiniciar o container e confirmar que `GET /api/v1/history` persiste (não zera).
- **Cobertura:** `pytest tests/unit --cov=src --cov-report=term-missing` e comparar com a
  baseline ~30% do README.
- **Jurisprudência:** teste de integração com `TribunalAPIAdapter` em modo real + fallback.
- **Regressão geral:** CI (`.github/workflows/ci.yml`) verde (Black, Bandit, gitleaks, pytest).

## 10. Arquivos-chave a modificar (quando executar)

- `src/api/main.py` — endpoints canônicos, `response_model`, role em `/tasks/compare`.
- `src/api/schemas/responses.py` — **novo**, Pydantic response models.
- `src/api/main.py` + `src/agents/supervisor_agent.py` — histórico via `DecisionLedger`.
- `src/utils/ledger.py` — leitura paginada por cursor para `/history`.
- `src/agents/agente_jurisprudencia.py` + `src/tools/tribunal_api_adapter.py` — APIs reais.
- `config/` (YAML) — regras DMN-02 de fonte de dados externalizadas.
- `tests/integration/test_api_contract.py` — **novo**.
- `docs/ARCHITECTURE_C4.md` — incorporar diagramas de sequência úteis (não criar doc novo).
