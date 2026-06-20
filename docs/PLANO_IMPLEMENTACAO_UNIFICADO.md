# Plano de Implementação Unificado + Validação — Central de Inteligência Jurídica

## Contexto

O dono pediu (2026-06-15): unir **minha análise** (eixo "real‑ou‑simulado / infra‑gated") com a de **outro analista ("Super Z", 20/06/2026)** (eixo "profundidade do núcleo multiagente + UX") em **um único plano de implementação**, e **ao final validar os apontamentos do analista e revalidar os meus** — com evidência em `arquivo:linha`.

Verifiquei diretamente no código todos os apontamentos críticos do outro analista (C1–C5) e os importantes (I1–I6), além de reconfirmar os meus. **Resultado da validação: o relatório do analista é preciso e ancorado em código — nenhum achado falso entre os verificados**, apenas ressalvas pontuais. As duas análises são **complementares**.

**Atualização (2026-06-15):** o dono autorizou **execução autônoma completa** do plano — eu verifico, recomendo e aprovo; divido em PRs, aguardo CI, corrijo até verde, faço merge; registro progresso em `docs/roadmap_v1.md` e pendências do dono em `docs/pendencia_v1.md`; sigo até o fim.

---

## ⚙️ Execução Autônoma — Metodologia & Sequência (v1)

**Mandato:** autonomia total nesta sessão — auto-revisão + auto-aprovação + merge. Sem pausar para aval por PR.

**Loop por PR (de‑risk: itens fáceis/CI‑amigáveis primeiro):**
1. Branch `claude/<onda>-<slug>` a partir de `master` (padrão do repo; git log confirma `claude/*`→PR→merge).
2. Implementar + **testes** (cobertura unitária deve ficar **≥50%** — gate real do CI, apesar do README dizer 30%).
3. **Pré‑validar local** antes do push (maximiza CI verde de primeira):
   `black src/ tests/` · `bandit -r src/ -x tests/ --severity-level high --confidence-level high` · `pytest tests/unit/ --cov=src --cov-fail-under=50` · `cd frontend && npm run lint && npm test && npm run build`.
   *Limitação:* `alembic upgrade head` e `tests/integration/` exigem Postgres (pode não existir neste container) → confio no CI + loop de correção para esses.
4. Se mudei frontend: **rebuild do bundle** (`npm run build`) e **commitar** `src/api/static/spa`.
5. Push → abrir PR (via `mcp__github__create_pull_request`) → acompanhar CI (`actions_list`/`get_job_logs`) → se vermelho, diagnosticar e corrigir até verde → **auto‑review** (skill `code-review` no diff) → **merge** (`merge_pull_request`).
6. Atualizar `docs/roadmap_v1.md` (log vivo: ticket, PR#, status, CI) a cada PR.

**Gates bloqueantes do CI a satisfazer:** compileall · alembic · bandit high · `black --check` · unit cov≥50 · integration · docker‑build · gitleaks · frontend eslint(0 warn)+vitest+build. (mypy/pip‑audit/Trivy não bloqueiam.) **Não** disparar `cd-deploy.yml` (permanece `workflow_dispatch`).

**Docs de controle:**
- `docs/roadmap_v1.md` — sequência viva; marco/ticket/PR/status; novos gaps inseridos na posição adequada.
- `docs/pendencia_v1.md` — tudo que exige decisão/configuração/credencial do dono (Onda 0 infra; certificado A1/e‑CAC; chaves DATAJUD; captcha CRC/CADIN/ONR). Registro e **pulo para a próxima tarefa**.

**Itens bloqueados por credencial/infra externa:** implemento a parte de **código** atrás das flags/stubs existentes (com testes via mock), e anoto a credencial/infra faltante em `docs/pendencia_v1.md`. Não invento segredos nem transmito a sistemas reais.

**Novos gaps:** se pequenos, resolvo no PR corrente; senão, anoto em `docs/roadmap_v1.md` na posição adequada e resolvo na vez.

**Sequência de PRs (ordem de execução):**
- **PR0 — Scaffolding & persistência do plano:** criar `docs/roadmap_v1.md`, `docs/pendencia_v1.md` e `docs/PLANO_IMPLEMENTACAO_UNIFICADO.md` (cópia deste plano, pois `/root/.claude/plans` é efêmero). Docs‑only → CI trivialmente verde; valida o loop.
- **PR1 — Onda 1 higiene (O1‑4/5/6, O4‑5):** remover botões Demo (guard `DEV`), botão morto Invest360, default `INTEGRATIONS_*=real` em prod, ortografia README, renomear `handoff/`→`design-handoff/` (ajustar refs). + rebuild bundle.
- **PR2 — Onda 1 streaming (O1‑1/2/3):** endpoint SSE `/api/v1/tasks/stream` reusando eventos do `DecisionLedger`; timeline + painel "Agentes ativos" + card de consenso no `AssistantScreen`. + testes + rebuild bundle.
- **PR3 — Onda 2 núcleo (O2‑1..4):** consenso semântico (embedding/LLM‑judge) + recalibrar `consensus_strength`/gate HITL + modo CoT‑LLM plugável no ArchitectAgent + regressões.
- **PR4 — Onda 3 persistência (O3‑1..4):** migrations `decision_ledger/hitl_requests/training_sessions/a2a_messages`; training real (agent_factory, sem baseline fake); embeddings reais no VectorMemory; A2A pub/sub `await`.
- **PR5 — Onda 4 fontes/fiscal (O4‑1..4):** e‑CAC real atrás do stub (assinatura+webservice, testado por mock; credencial→pendência); CRC/CADIN/ONR (código real onde possível, senão marcar roadmap explícito na UI); wiring do Vault; handlers Celery.
- **PR6 — Onda 5 diferenciais (UX‑1..5):** "Contradição encontrada" (reusa `dissenting_opinions`), Modo Explorador, badges, mapa de conhecimento (MVP). XL — entregues como MVPs incrementais.
- **Transversal:** segurança/LGPD (rate‑limit, erro genérico+correlation_id, redact_pii em DataJud/VectorMemory, gates CI bloqueantes, sincronizar `constitution.yaml`) tecidos nos PRs relevantes.

---

## Síntese: o sistema tem DUAS camadas de gap

| Camada | Eixo | Natureza | Custo de fechar |
|---|---|---|---|
| **A — "Ligar"** (minha análise) | Infra‑gated / simulado | Quase toda etapa que toca o mundo real roda `stub`/`mock`/`simulado` até provisionar infra (Postgres, MinIO, Celery, Ollama) e credenciais (DATAJUD_API_KEY, certificado A1, e‑CAC). Reversível por **configuração + poucas completudes de código**. | Baixo‑médio |
| **B — "Tornar real"** (analista Super Z) | Algoritmo + UX do "núcleo de inteligência" | Mesmo provisionado: o "consenso" é votação por igualdade de JSON; o "Chain‑of‑Thought" é heurística de keywords; o "aprendizado contínuo" é bookkeeping; e a UX **esconde** a natureza multiagente. Exige **trabalho algorítmico real**, não só config. | Médio‑alto |

> **Tese unificada:** a engenharia de plataforma é séria e real (orquestrador, A2A, HITL, ledger, RBAC/JWT, schema fiscal, parser SPED, observabilidade, 122 arquivos de teste). Mas os **diferenciais prometidos** estão parcialmente ocos em dois sentidos distintos — (A) desligados por falta de infra/credencial e (B) rasos no algoritmo/UX. O plano abaixo ataca os dois.

---

## Decisão estratégica (recomendação)

Recomendo executar **B‑núcleo + UX primeiro** (maior "wow" por menor custo, destrava o diferencial competitivo) em **paralelo** com o provisionamento de infra da Camada A (que depende do dono e não bloqueia o time de código). A correção fiscal "dura" (e‑CAC real, fontes credenciadas) entra depois, pois depende de certificados/credenciais externas.

---

## Plano de implementação (ondas)

Legenda ator: 👤 dono (infra/credencial) · 🤖 agente/dev (código). Esforço: XS/S/M/L/XL.

### Onda 0 — Pré‑requisitos do dono (paralelo, não bloqueia código)
*Fecha a Camada A "ligando" dados/serviços reais. Fonte: `docs/acaoPendenteDono.md` AP‑01..06 + minha análise.*

| ID | Item | Ator | Ref |
|---|---|---|---|
| O0‑1 | PostgreSQL 15 (`DATABASE_URL` + `alembic upgrade head`) — destrava todo o fiscal e tira `analytics.py` do modo `stub (sem DATABASE_URL)` | 👤 | AP‑02 |
| O0‑2 | MinIO/S3 (uploads SPED) + Celery worker (parse assíncrono) | 👤 | AP‑03/04 |
| O0‑3 | `DATAJUD_API_KEY`, acesso Câmara → tira tribunais/jurisprudência do `source=simulated` | 👤 | — |
| O0‑4 | Ollama+`llama3` (`OLLAMA_BASE_URL`) e/ou `OPENAI_API_KEY` → IA real em vez de heurística/erro | 👤 | — |
| O0‑5 | Certificado A1 (.pfx) + acesso e‑CAC homologação → transmissão real | 👤 | AP‑05/06 |

### Onda 1 — "Streaming Visível" + quick wins (Camada B‑UX + higiene)
*Fonte: analista QW‑01..10 + meus itens de verificação.*

| ID | Ticket | Esforço | Arquivos‑chave |
|---|---|---|---|
| O1‑1 | Endpoint `POST /api/v1/tasks/stream` (SSE via `sse-starlette`) emitindo eventos que o `DecisionLedger.log_decision` já gera (`INTENT_CLASSIFIED`, `MEMORY_RECALLED`, `DELEGATED…`, `CONSENSUS_REACHED`) | M | `src/api/routes/tasks.py`, `src/agents/supervisor_agent.py` |
| O1‑2 | `AssistantScreen` consome SSE e renderiza **timeline de raciocínio** + painel "Agentes ativos" | M | `frontend/src/screens/user/AssistantScreen.jsx` (hoje POST síncrono em `:186-203`), `frontend/src/api/client.js` (`submitTask` `:67`) |
| O1‑3 | Card "Como chegamos a esta resposta" (decision_maker, supporting_agents, **dissenting_opinions** — já existem no payload de consenso) | S | `AssistantScreen.jsx` |
| O1‑4 | Remover botões **Demo: Operador/Admin** de produção (guard `import.meta.env.DEV`) | XS | `frontend/src/App.jsx:158-163` |
| O1‑5 | Renomear `handoff/` → `design-handoff/` (é design‑handoff, não runtime) | XS | `handoff/` |
| O1‑6 | Default `INTEGRATIONS_*_MODE=real` quando `ENVIRONMENT=production`; revisão ortográfica do README | XS | `docker-compose.yml`, `README.md` |
| O1‑7 | **Verificar Camada A pós‑provisionamento**: smoke E2E confirmando que selos viram `source=real_api` / `is_stub=false` | S | `tests/integration/test_golden_thread.py` |

### Onda 2 — "Consenso & Raciocínio Reais" (Camada B‑núcleo)
*Fonte: analista C1, C2 + meus testes de regressão.*

| ID | Ticket | Esforço | Arquivos‑chave |
|---|---|---|---|
| O2‑1 | **Consenso semântico** (corrige C1): substituir clustering por `json.dumps` por (a) embedding das propostas + cosine ≥ threshold, ou (b) LLM‑as‑judge `agree/partial/disagree`, ou (c) extração estruturada (`classe_processual + tese`) para jurisprudência | L | `src/consensus/weighted_voting.py:91-93,167-174` |
| O2‑2 | Recalibrar `consensus_strength` para não tratar "1 agente confiante" como "consenso" (hoje `min(1.0, winning_score)` em `:139`); garantir gate HITL quando há divergência semântica | M | `weighted_voting.py:139`; gate em `supervisor_agent.py` |
| O2‑3 | **CoT real** (corrige C2): modo LLM plugável no `ArchitectAgent` (o próprio código já prevê via `IntentClassifier`), com fallback à heurística atual; ou renomear honestamente o termo "Chain‑of‑Thought" | L | `src/agents/architect_agent.py:79-185` |
| O2‑4 | Testes de regressão de consenso (propostas diferentes → não "concordam"; divergência → HITL) | S | `tests/integration/test_consensus_mechanism.py` |

### Onda 3 — "Aprendizado & Persistência Reais"
*Fonte: analista C3, I3 + minha observação de persistência.*

| ID | Ticket | Esforço | Arquivos‑chave |
|---|---|---|---|
| O3‑1 | **Training real** (corrige C3): injetar `agent_factory` para A/B test comparar versões reais (hoje usa `type("Agent",(),{...})` fake) e remover baseline hardcoded | L | `src/training/training_manager.py:252-261,388-395` |
| O3‑2 | **Migrations do núcleo multiagente** (corrige I3): `decision_ledger`, `hitl_requests`, `training_sessions`, `a2a_messages` — hoje só há 4 migrations fiscais; estado não sobrevive a restart | M | `alembic/versions/` |
| O3‑3 | VectorMemory com embeddings reais (corrige I2): `sentence-transformers`/BGE‑m3 ou embeddings Ollama, em vez de `HashEmbeddingFunction` | M | `src/memory/vector_memory.py:32-68` |
| O3‑4 | A2A request‑response por pub/sub `await` em vez de polling 100ms (corrige I4) | S | `src/protocols/a2a_channel.py:298-305` |

### Onda 4 — "Fontes & Fiscal Reais" (fecha lacunas duras da Camada A)
*Fonte: minha análise (stubs fiscais, e‑CAC) + analista (fontes mock).*

| ID | Ticket | Esforço | Arquivos‑chave |
|---|---|---|---|
| O4‑1 | Implementar (ou marcar explicitamente como roadmap na UI) os adapters **CRC Protestos / CADIN / ONR** — hoje `fetch_real` levanta `NotImplementedError`, sempre mock | L | `src/integrations/adapters/{crc_protestos,cadin,onr_imoveis}_adapter.py` |
| O4‑2 | **Transmissão e‑CAC real** atrás do stub (assinatura + webservice) — hoje retorna protocolo falso `STUB-<uuid>`, **não transmite à Receita** | L | `src/api/routes/transmissao.py:95,113`, `src/integrations/ecac/adapter.py` |
| O4‑3 | Ligar o **Vault** quando `VAULT_MASTER_KEY` existir (hoje `is_stub`/esqueleto) | M | `src/integrations/vault.py`, `src/api/routes/vault.py` |
| O4‑4 | Completar handlers Celery de parse/validação/apuração (hoje enfileira; completude parcial) | M | `src/workers/` |
| O4‑5 | Botão morto "Abrir na consulta processual" | XS | `frontend/src/screens/user/Invest360Screen.jsx:288` |

### Onda 5 — "Curiosidade & Diferenciais" (Camada B‑UX avançada)
*Fonte: analista UX‑1..5 / H2 / H3.* Mapa de conhecimento jurídico (grafo), Modo Explorador (3 perguntas relacionadas), badges de expertise, "Contradição encontrada" (reaproveita `dissenting_opinions`), modo "Advogado do Diabo". Esforço L–XL; valor de retenção/diferenciação.

### Faixa transversal — Segurança, LGPD e qualidade (contínuo)
*Fonte: minha auditoria + a interna (`docs/AUDITORIA_CONFORMIDADE.md`) + LGPD do analista.*

- **Reverificar itens da auditoria de maio** (auth já corrigido): rate limiting aplicado via `Depends`? mensagem de erro genérica + `correlation_id`? gates de CI bloqueantes (remover `|| echo "WARNING"`)? sincronizar `config/agents/constitution.yaml` (3 declarados × 5‑12 reais)? cobertura 30%→70%.
- **LGPD**: aplicar `redact_pii` no `_parse` do `DataJudClient` e no snapshot do `VectorMemory` (PII de terceiros em processos públicos); TTL/rotação do `DecisionLedger` em file; hash de senhas `AUTH_USERS` com `passlib[bcrypt]`.

---

## Tabela consolidada de origem dos achados

| Achado | Minha análise | Analista Super Z | Status |
|---|---|---|---|
| Stub/simulado infra‑gated (fiscal, analytics, e‑CAC, vault) | ✅ central | parcial (transmissão) | **camada A** |
| Auth bypass **corrigido** | ✅ | ✅ (confirma RBAC/JWT bom) | resolvido |
| CRC/CADIN/ONR sem dado real | ✅ (`NotImplementedError`) | ✅ (mock) | reconciliado |
| Consenso por igualdade de JSON (C1) | ✗ não vi | ✅ central | **camada B** |
| CoT = heurística keyword (C2) | ✗ não vi | ✅ central | **camada B** |
| Training = bookkeeping/fake A/B (C3) | parcial ("incerto") | ✅ central | **camada B** |
| UX esconde multiagente / sem streaming (C4/C5) | ✗ não vi | ✅ central | **camada B** |
| A2A = notificação, não coordenação (I4) | ✗ não vi | ✅ | confirmado |
| Migrations só fiscais / persistência (I3) | parcial | ✅ | confirmado |

---

## ✅ Validação dos apontamentos do analista (verificada em código)

Verdito: ✅ confirmado · ⚠️ confirmado com ressalva · ❌ refutado · 🔵 não verificável aqui

| # | Apontamento do analista | Verdito | Evidência (arquivo:linha) — verificada por mim |
|---|---|---|---|
| C1 | Consenso clusteriza por igualdade de JSON; 1 agente "concorda consigo" e burla HITL | ⚠️ | **Confirmado**: `weighted_voting.py:172` `json.dumps(..., sort_keys=True)`; cluster `:91-93`; `consensus_strength=min(1.0,winning_score)` `:139`. **Ressalva**: "HITL nunca dispara" é exagero — dispara se `conf×weight<0,6` ou por regra DMN (ações críticas). O defeito estrutural (igualdade byte‑a‑byte impede consenso semântico) é real. |
| C2 | "Chain‑of‑Thought" do ArchitectAgent é heurística por keyword, não LLM | ⚠️ | **Confirmado e autodocumentado**: docstring `architect_agent.py:82-88` ("heurística DETERMINÍSTICA… não uma chamada a LLM"); metadata `:40` `"deterministic_keyword_heuristic"`; passos estáticos `:94-161`. **Ressalva**: é intencional (reprodutibilidade), não oculto — o gap é vs. o termo de marketing "CoT". |
| C3 | TrainingManager.run_ab_test usa agentes sintéticos fake; sem treino real | ✅ | `training_manager.py:252-261` `type("Agent",(),{"execute":lambda…})`; baseline fixo `_get_current_metrics` `:388-395`; "treino" = agregação `:331-356` + pesos de rota `:358-373`. |
| C4 | Frontend não expõe a natureza multiagente | ✅ | `AssistantScreen.jsx:186-203` (POST síncrono, troca placeholder pelo resultado final; sem progresso por agente). |
| C5 | Sem streaming de respostas | ✅ | `client.js:67` `submitTask` = POST simples; único WebSocket é HITL (`wsUrl` `:52-59`). |
| I1 | UnifiedOrchestrator usa só 3 dos 5 agentes do squad | ✅ | `unified_orchestrator.py:112-145` só chama `architect/developer/auditor`. |
| I2 | VectorMemory usa HashEmbeddingFunction (semântica fraca) | ✅ | `vector_memory.py:32-68` (buckets SHA‑256/byte‑sum). |
| I3 | Alembic só cobre domínio fiscal; estado multiagente não persiste | ✅ | 4 migrations, todas fiscais (`0001`–`0004`); Ledger/HITL/Training em file/memória. |
| I4 | A2A request‑response usa polling de 100ms | ✅ | `a2a_channel.py:298-305` `while…: await asyncio.sleep(0.1)`. |
| I5 | Botões Demo com credenciais hardcoded | ✅ | `App.jsx:160-162` `doLogin('operator','operator')` / `('admin','admin')`, sem guard `DEV`. |
| I6 | `handoff/` é design‑handoff, não runtime | ✅ | `handoff/` contém HTML/CSS/JSX de protótipo; runtime A2A está em `src/protocols/`. |
| — | A2A é notificação; delegação real é chamada síncrona | ✅ | `supervisor_agent.py:1031` `run_in_executor(None, agent.execute_task, task)` vs. `send_to_agent(...consultation_request)` `:1061`. |
| — | DataJud/Câmara/BrasilAPI/TSE/DJEN são integrações **reais** | ⚠️ | Confirmado que os adapters chamam HTTP real; **mas** degradam silenciosamente p/ mock sem credencial (`datajud_client.py` `if not self.configured: return self._mock_result`). "Real" ⇔ com chave. |
| — | 1.150 testes, 1.125 passam / 25 falham | 🔵 | **Não reexecutei** (modo somente‑leitura). Contei 122 arquivos `test_*.py`. Tratar números como reportados, não verificados por mim. |
| — | LGPD (§8) e comparação competitiva (§9) | 🔵 | Riscos LGPD são plausíveis e úteis; scores competitivos são **opinião**, não fato de código. |
| — | Refs de linha do `supervisor_agent` (ex.: `:983-988`) | ⚠️ | Claim correto, **linhas deslocadas** no HEAD atual (`run_in_executor` em `:1031`, `send_to_agent` em `:1061`). Não invalida o achado. |

**Conclusão da validação:** entre todos os apontamentos verificáveis em código, **nenhum foi refutado**; as ressalvas são de grau/enquadramento, não de fato. Auditoria do analista é de alta qualidade.

---

## 🔁 Revalidação dos meus apontamentos

| Meu apontamento (turno anterior) | Verdito | Evidência / ajuste |
|---|---|---|
| Padrão "real‑ou‑simulado" (ADR‑008) domina o app; default simulado | ✅ | `integrations/base.py:70-111`, `settings.py:42`, `datajud_client.py:128,153`. |
| Pipeline fiscal roda **stub** sem `DATABASE_URL` | ✅ | `analytics.py:115,189,251,318` `"stub (sem DATABASE_URL)"`. |
| Transmissão e‑CAC é **stub por padrão** (protocolo falso) | ✅ | `transmissao.py:95,113-114`; `ecac/adapter.py` `STUB-<uuid>`. |
| PER/DCOMP e Retificação retornam stub/`simulado` sem banco | ✅ | `per_dcomp.py:175 _stub_ficha…`; `retificacao.py:217 "simulado":True`. |
| CRC/CADIN/ONR = `NotImplementedError` (stub fixo) | ✅ | `crc_protestos_adapter.py:47-50` (+ `fetch_mock` hardcoded). |
| LLM é Ollama local; sem Ollama, devolve string de erro | ✅ | `llm_client.py:39-41`. Sem nuvem Claude/Anthropic. |
| Auth bypass de maio **corrigido** (`AUTH_REQUIRED=True`) | ✅ | `config.py:32`; o analista corrobora (RBAC/JWT sólidos). |
| "Treinamento: profundidade incerta" | ⚠️ | **Subdimensionei** — o analista provou (C3) que é bookkeeping com A/B fake. Incorporo como achado firme. |
| Núcleo de governança (HITL/Ledger/DMN) "genuinamente sólido" | ⚠️ | Mantém‑se p/ HITL/Ledger/RBAC; **mas** o "consenso" que alimenta o HITL tem o defeito C1 — sólido na mecânica, raso no algoritmo. Ajuste necessário. |
| Equívoco inicial "Supabase" | ❌ (meu) | Era premissa minha do ambiente; o app é Postgres/SQLAlchemy/FastAPI. Descartado. |

---

## Verificação (como testar ponta‑a‑ponta)

1. **Estado atual (sem infra):** `uvicorn src.api.main:app` → `/app`; exercitar Assistente/Jurisprudência/Investigação 360°/fluxo fiscal e observar selos `simulated/mock/is_stub` + logs `"stub (sem DATABASE_URL)"`.
2. **Após Onda 0:** seguir `docs/acaoPendenteDono.md`; setar `DATAJUD_API_KEY`/`OLLAMA_BASE_URL`; confirmar `source=real_api` / `is_stub=false`.
3. **Testes:** `pytest tests/unit tests/integration -q`; consenso `tests/integration/test_consensus_mechanism.py`; E2E `tests/integration/test_golden_thread.py -k E2E` (exige Postgres). *(Reexecutar para confirmar os números reportados pelo analista.)*
4. **Greps de evidência:** `json.dumps(proposal`, `deterministic_keyword_heuristic`, `type(\n    "Agent"`, `is_stub`, `source="simulated"`, `NotImplementedError`, `asyncio.sleep(0.1)`, `doLogin('operator'`.
