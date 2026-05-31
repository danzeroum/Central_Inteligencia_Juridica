# Relatório de Auditoria de Conformidade de Validações e Controles

**Repositório:** `danzeroum/Central_Inteligencia_Juridica`
**Documento-fonte auditado:** `analise_central_inteligencia_juridica_final.pdf` (Relatório de Análise de Qualidade, 31/05/2026)
**Branch auditada:** `claude/confident-hopper-cBzPt`
**Data da auditoria:** 31 de maio de 2026
**Natureza:** Auditoria de conformidade documentação × código real (independente)

---

## 1. Sumário Executivo

Este relatório audita criticamente o *Relatório de Análise de Qualidade* (PDF) contra o
estado **real** do código-fonte. Para cada validação, controle ou regra de negócio
descrita, verificamos se está **efetivamente aplicada**, classificamos o status de
conformidade, registramos a **evidência** (`arquivo:linha`), descrevemos o **gap** e
propomos uma **solução integrada** ancorada nas melhores práticas **já existentes no
projeto** (CircuitBreaker, CacheManager, A2A, DecisionLedger, HITL, externalização YAML).

Diferentemente de uma simples releitura do PDF, esta auditoria mantém **independência**:
confirma o que é verdadeiro, **refuta** o que o PDF afirma incorretamente e registra um
**achado novo** não destacado pela análise original (dependências LangChain ausentes do
`requirements.txt`).

### Metodologia

- Verificação *claim-by-claim* contra o código, com rastreio até `arquivo:linha`.
- Três frentes de verificação: Segurança · Qualidade/Arquitetura · Testes/CI/Dependências.
- Classificação de conformidade em três estados: **Comprovada** (controle existe e está
  aplicado), **Parcial** (existe mas com lacuna ou aplicação incompleta), **Não comprovada**
  (documentado/esperado mas sem aplicação efetiva no fluxo).

### Placar de Conformidade

Sobre **40 controles mapeados** nas tabelas das §2.1–§2.4:

| Estado | Qtde. | % | Significado |
|---|---|---|---|
| ✅ Comprovada | 7 | 17,5% | Controle implementado e efetivamente em uso (§2.4) |
| 🟡 Parcial | 10 | 25% | Implementado parcialmente ou com lacuna conhecida |
| ❌ Não comprovada | 23 | 57,5% | Esperado/documentado, mas **sem aplicação efetiva** (risco) |

> Detalhamento: §2.1 Segurança (8 ❌, 2 🟡) · §2.2 Qualidade (7 ❌, 3 🟡) · §2.3 Testes/CI/Deps
> (8 ❌, 5 🟡) · §2.4 Fortalezas (7 ✅).

> **Conclusão executiva:** a base arquitetural é sólida e há controles exemplares prontos
> para produção, porém os controles de **segurança de borda mais importantes** (autenticação,
> rate limiting, tratamento de erro, isolamento de imagem) estão **codificados mas
> desconectados do fluxo** — ou seja, existem no repositório mas não protegem o sistema. O
> caminho de correção é de **baixo esforço e alto impacto**: na maioria dos casos o código
> correto já existe e basta "ligá-lo".

---

## 2. Tabela Mestra de Validações Mapeadas

Legenda de status: ✅ Comprovada · 🟡 Parcial · ❌ Não comprovada

### 2.1 Segurança

| Validação / Controle | Status | Evidência (`arquivo:linha`) | Gap Identificado | Solução Integrada (melhores práticas do projeto) |
|---|---|---|---|---|
| Autenticação JWT em endpoints (SEC-001 / CWE-306) | ❌ | `src/api/main.py:101-104` (stub `verify_token()` → `"anonymous"`); usado em `Depends` em 213/285/352/454/465/493/543. Real em `src/api/auth.py:77-104` nunca importado. `AUTH_REQUIRED=False` em `main.py:36` | Bypass total: todos os endpoints aceitam requisição anônima | **Ligar** o `AuthManager` real (`auth.py`) como dependência FastAPI, removendo o stub. Código JWT completo já existe — é integração, não desenvolvimento |
| Limitação de taxa / rate limiting (SEC-002 / CWE-770) | ❌ | `src/api/main.py:107-108` (`enforce_rate_limit()` → `None`); `RateLimiter` funcional em `src/api/rate_limiter.py:12-50` nunca instanciado | Sistema exposto a brute-force, DDoS e abuso de API | Instanciar `RateLimiter` (já implementado, sliding window por IP) e aplicar via `Depends` nos endpoints, removendo o placeholder |
| Não divulgação de erro interno (SEC-004 / CWE-209) | ❌ | `src/api/main.py:531` (`detail=f"... {str(exc)}"` em HTTP 500) | Stack traces / caminhos / segredos podem vazar ao cliente | Retornar mensagem genérica + `correlation_id`; logar detalhe internamente, reaproveitando o padrão de `correlation_id` já usado no A2A |
| Gestão segura de credenciais Grafana (QAL-001 / CWE-798) | ❌ | `docker-compose.yml:56-57` (`admin/admin` fixos) | Credenciais default sem override por ambiente | `${GF_SECURITY_ADMIN_PASSWORD:?}` via `.env`, mesmo padrão de externalização já usado para Redis |
| Exclusão de artefatos sensíveis da imagem (P0-4 / MED-003) | ❌ | `.dockerignore` inexistente; `Dockerfile:11` faz `COPY . /app/` | `.env`, `.git`, `logs/` copiados para a imagem | Criar `.dockerignore` (`.env`, `.git`, `__pycache__`, `logs`, `.DS_Store`) — complementa a boa prática de container não-root já adotada |
| Sanitização de identificadores A2A (P0-5 / CWE-20) | ❌ | `src/api/main.py:211,217` (`sender_id` query param sem validação) | Injeção de identificadores arbitrários agente-agente | Validar formato/comprimento com o `InputSanitizer` já existente antes de repassar ao canal |
| Validação de chamada de ferramenta (`validate_tool_call`) | ❌ | `src/safety/security_config.py:38-48` definido; só chamado em `secure_executor.py:56`, dentro de `execute_tool_sandboxed()` nunca invocado | Guardrail de tool-call existe mas está fora do fluxo | Rotear execuções de ferramenta pelo `SecureToolSandbox` no orquestrador |
| Sanitização de entrada (pipeline 5 estágios) | 🟡 | `src/utils/input_sanitizer.py:31` (`union.*select` com `re.DOTALL`), `40-45` (`$ % &` permitidos) | Bypass `union\nselect` **NÃO** ocorre (DOTALL cobre newline — PDF impreciso); porém `$ % &` ainda permitidos abrem vetores DBMS-específicos | Endurecer `allowed_chars` por contexto e adicionar testes de variação (ver §2.3) — o pipeline-base já é uma fortaleza |
| Comunicação Redis com TLS/senha (CWE-319) | 🟡 | `docker-compose.yml:24-31` (sem senha/TLS); `src/utils/cache_manager.py:202-208` (`password` opcional, sem TLS) | Tráfego em texto claro, auth opcional na config padrão | Tornar `REDIS_PASSWORD` obrigatório e habilitar TLS em `docker-compose.prod.yml`; o `CacheManager` já suporta `password` por env |
| Coerência da doc de segredo (`.env.example` × `auth.py`) | ❌ | `.env.example:13-15` ("opcional") vs `src/api/auth.py:40-46` (`RuntimeError` se `JWT_SECRET` < 32 chars) | Doc enganosa pode levar a deploy sem auth | Corrigir `.env.example` para refletir obrigatoriedade real (≥ 32 chars) |

### 2.2 Qualidade de Código e Arquitetura

| Validação / Controle | Status | Evidência (`arquivo:linha`) | Gap Identificado | Solução Integrada |
|---|---|---|---|---|
| Responsabilidade única no núcleo (SEC-003) | 🟡 | `src/agents/supervisor_agent.py:290-841` — `process_task()` com **551 linhas** (pior que os "300+" do PDF); arquivo com 1119 linhas | God Method: 7+ responsabilidades, impossível testar isoladamente | Decompor em `classify_and_route()`, `execute_consensus()`, `aggregate_results()` — habilita testes unitários por etapa |
| Cálculo confiável de tempo decorrido | ❌ | `supervisor_agent.py:296` (`time.time()`), reatribuído em `585` e `664` (`asyncio...time()`), usado em `801` | Mistura de fontes de relógio → métricas de latência não confiáveis | Padronizar uma única fonte de tempo monotônica por execução |
| Tratamento específico de exceções (QAL-003) | ❌ | `supervisor_agent.py:221,821` (`except Exception` → dict `status:"error"`) | Falhas reais ocultadas, depuração prejudicada | Capturar exceções específicas e registrar no `DecisionLedger` (auditoria já existente) |
| Encapsulamento API × Agente (QAL-002) | ❌ | `src/api/main.py:362-363,385` invoca `_identify_all_tribunals` / `_delegate_to_tribunal_agent` (privados) | API acoplada a internals do agente | Expor métodos públicos no `SupervisorAgent` e consumir apenas a interface |
| Integração do `SafeAgentBase`/guardrails (MED-008) | ❌ | `src/orchestrator.py:7,38` instancia `SafeAgentBase()`, mas o fluxo principal via `SupervisorAgent` o ignora | Guardrails implementados mas desconectados | Fazer o caminho principal passar pelos guardrails do `SafeAgentBase` |
| Unicidade do subsistema de memória (MED-007) | 🟡 | `supervisor_agent.py:66-67` (`VectorMemory` + `AgentMemorySystem`); este último só passado ao `TribunalAgent` em `855` | Dois sistemas paralelos sem integração clara | Definir contrato único de memória ou documentar fronteiras explícitas |
| Injeção de dependências × singletons (QAL-006) | 🟡 | `src/protocols/a2a_channel.py:238-244`, `src/hitl/hitl_queue.py:167-176`, `src/api/main.py:111-114` | Estado global dificulta testes | Migrar singletons para DI via `Depends`, como já se faz para outros recursos FastAPI |
| Padronização de keywords de consenso (LOW-004) | ❌ | `supervisor_agent.py:47-48` (`"crítico"` e `"critico"` duplicados) | Lista não normalizada | Normalizar acentuação na comparação (`unicodedata`) |
| Fonte única de verdade para auth (LOW-005) | ❌ | `src/api/main.py:36` (`AUTH_REQUIRED=False`) × `src/api/auth.py:32` (`REQUIRED=True`) | Dois sinais conflitantes | Eliminar `AUTH_REQUIRED` global; usar somente `AuthManager` |
| Eficiência do registro de agentes (LOW-006) | ❌ | `src/api/main.py:120-131` reconstrói registro; chamado em 7 handlers | Registro reconstruído a cada request | Construir uma vez no startup e cachear |

### 2.3 Testes, CI/CD e Dependências

| Validação / Controle | Status | Evidência (`arquivo:linha`) | Gap Identificado | Solução Integrada |
|---|---|---|---|---|
| Gates de qualidade bloqueantes no CI (QAL-004) | ❌ | `.github/workflows/ci.yml:46,51,56` (`bandit`/`black`/`mypy` com `|| echo "WARNING"`) | Violações de formato/tipo/segurança nunca quebram o build | Remover `|| echo "WARNING"` tornando os passos bloqueantes (mesma estrutura de job já existente) |
| Cobertura de testes adequada (QAL-005 / P2-1) | 🟡 | `ci.yml:65` (`--cov-fail-under=30`); `pyproject.toml` (coverage) | Limiar de 30% baixo para domínio jurídico | Elevar gradualmente para 70% começando por `auth`, consenso e `TrainingManager` |
| Validação real de JWT em testes | ❌ | `tests/unit/test_security_hardening.py` testa apenas `configure()`/round-trip; sem token expirado/inválido; sem teste do bypass de `main.py` | Caminho de auth crítico não coberto | Adicionar testes de token expirado/inválido e regressão do bypass |
| Cobertura de sanitização de entrada | 🟡 | `tests/unit/test_input_sanitizer.py` (5 testes); sem path traversal, double-encoding, null byte, Unicode | Vetores comuns sem teste | Acrescentar casos seguindo o estilo dos testes já existentes |
| Testes do `TrainingManager` | ❌ | `src/.../training_manager.py` (~398 linhas) sem `tests/unit/test_training_manager.py` | Módulo inteiro sem teste unitário dedicado | Criar suíte unitária (lógica só coberta em integração) |
| Testes de contrato de schema YAML | ❌ | Sem teste validando `constitution.yaml`/`tribunals.yaml` | Config morta passa despercebida | Teste pytest validando agentes/tribunais declarados × reais |
| Isolamento do marker `integration` | 🟡 | `pyproject.toml` define marker; testes de integração sem `@pytest.mark.integration` (isolam por diretório) | `pytest` sem alvo roda ~200 testes juntos | Aplicar o decorator e `addopts = -m "not integration"` por padrão |
| Secret scanning no CI (MED-009) | ❌ | Ausente em `.github/workflows/*.yml` | Segredos comitados não detectados | Adicionar `gitleaks`/`trufflehog` como step no `ci.yml` |
| Dependency scanning no CI (MED-010) | ❌ | Ausente em `.github/workflows/*.yml` | CVEs em dependências não detectados | Adicionar `pip-audit`/`safety` como step no `ci.yml` |
| Completude do `requirements.txt` | ❌ | `src/routing/intent_classifier.py:20-22` importa `langchain`/`langchain_openai`, ausentes em `requirements.txt` | **Achado novo** — risco de `ImportError` em runtime/deploy limpo | Pinar `langchain`/`langchain-openai` no `requirements.txt` |
| Atualização de dependências (P2-2) | 🟡 | `requirements.txt`: `httpx>=0.27,<0.28`, `numpy<2.0`, `fastapi 0.111.0`, `uvicorn 0.29.0`, `chromadb 0.4.18`, `redis 4.6.0`, `sentence-transformers 2.2.2` | Pacotes desatualizados e pins extremos bloqueiam upgrades | Atualizar em ondas, com o dep-scanning acima validando cada bump |
| Request ID / logs estruturados (MED-011) | 🟡 | `correlation_id` em `src/protocols/a2a_mixin.py`; `request_id` em `src/hitl/hitl_queue.py`; logs `logger.info` em string | Sem middleware central nem JSON | Middleware FastAPI propagando `correlation_id` (já usado no A2A) + logs JSON |
| Coerência das configs de governança | ❌ | `config/agents/constitution.yaml` declara 3 agentes vs. 5-12 reais; `tribunals.yaml` referencia TJBA/TJPE/TJCE sem agentes | Configuração desatualizada/morta | Sincronizar YAML ao estado real; teste de contrato (acima) garante regressão |

### 2.4 Controles Comprovados (Fortalezas — Status ✅)

| Controle | Evidência | Mérito |
|---|---|---|
| Circuit Breaker | `CircuitBreaker` (thread-safe, RLock, estados, métricas Prometheus) | Implementação de referência, pronta para produção |
| Cache distribuído com fallback | `src/utils/cache_manager.py` (Redis→memória, SHA-256, TTL, namespaces) | Resiliente e thread-safe |
| HITL (human-in-the-loop) | `src/hitl/` (trust scoring, thresholds, aprovação) | Maduro para o domínio jurídico |
| Decision Ledger | Trilha de auditoria de decisões | Essencial para conformidade jurídica |
| Protocolo A2A | `src/protocols/a2a_channel.py` (pub/sub Redis, DLQ, request-response) | Comunicação agente-agente padronizada |
| Container não-root | `Dockerfile` (`appuser`, imagem slim) | Boa prática de containerização |
| Externalização de config | `tribunals.yaml` (roteamento externo) | Aderente ao Open/Closed Principle |

---

## 3. Discrepâncias do Relatório-Fonte (Independência da Auditoria)

A auditoria identificou pontos em que o PDF **diverge do código real**. Registrá-los é
parte do princípio de independência e evita decisões baseadas em premissas erradas.

| Afirmação do PDF | Veredito | Realidade verificada |
|---|---|---|
| `BaseAgent` é *dead code*, nunca herdado (LOW-002 / código morto) | ❌ **FALSO** | Herdado por `AuditorAgent`, `RecoveryAgent`, `ExplorationAgent` (`src/agents/*.py`) |
| `process_task_advanced()` tem "4+ try/except aninhados" | ❌ **FALSO** | Há **1** nível (`supervisor_agent.py:147,221`) |
| `process_task()` tem "300+ linhas" | ⚠️ **SUBDIMENSIONADO** | Tem **551 linhas** — problema maior que o relatado |
| "78 testes unitários + 12 de integração" | ⚠️ **IMPRECISO** | Aproximadamente **120 unit + 80 integração** |
| "12 ADRs" / constitution "3 vs 7+" | ⚠️ **IMPRECISO** | **11** ADRs; 3 declarados vs **5-12** ativos conforme contexto |
| Bypass de sanitizador via `union\nselect` (CWE-185) | ⚠️ **PARCIAL** | O bypass **não** ocorre (flag `re.DOTALL`); o gap real é `$ % &` em `allowed_chars` |
| (não destacado) Dependências LangChain | ➕ **ACHADO NOVO** | `langchain`/`langchain-openai` importados em `intent_classifier.py:20-22`, **ausentes** do `requirements.txt` |

---

## 4. Recomendações Prioritárias

Reaproveitando a taxonomia P0/P1/P2 do documento-fonte, com foco em **integração ao fluxo
e pipeline existentes** (baixo esforço, alto impacto).

### P0 — Correção Imediata (Segurança)
1. Ligar o `AuthManager` real (`auth.py`) como `Depends`, removendo o stub de `main.py`.
2. Instanciar e aplicar o `RateLimiter` real nos endpoints.
3. Substituir `str(exc)` por mensagem genérica + `correlation_id` (logar detalhe interno).
4. Criar `.dockerignore` (`.env`, `.git`, `__pycache__`, `logs`, `.DS_Store`).
5. Validar `sender_id`/`receiver_id` A2A com o `InputSanitizer` existente.
6. Externalizar credenciais do Grafana e corrigir `.env.example` (JWT obrigatório).

### P1 — Curto Prazo (Arquitetura & Pipeline)
1. Tornar `black`/`mypy`/`bandit` bloqueantes no CI (remover `|| echo "WARNING"`).
2. Decompor `process_task()` em métodos testáveis.
3. Adicionar `langchain`/`langchain-openai` ao `requirements.txt` (**achado novo**).
4. Migrar singletons para injeção de dependências.
5. Conectar `SafeAgentBase`/`validate_tool_call` ao fluxo principal.

### P2 — Médio Prazo (Qualidade & Observabilidade)
1. Elevar cobertura de 30% → 70% (auth JWT, consenso, `TrainingManager`).
2. Adicionar secret scanning (`gitleaks`) e dep scanning (`pip-audit`) ao CI.
3. Atualizar dependências em ondas validadas pelo dep-scanning.
4. Middleware de `correlation_id` + logs JSON em todas as camadas.
5. Sincronizar `constitution.yaml`/`tribunals.yaml` + testes de contrato de schema.

---

## 5. Recomendações Gerais — Cultura de Validação e Conformidade

- **"Implementado" ≠ "Aplicado":** o padrão recorrente mais grave é o controle existir no
  repositório mas **não estar conectado ao fluxo** (auth, rate limiter, guardrails,
  sandbox). Adotar uma checklist de PR que exija prova de *aplicação efetiva* (teste que
  exercite o controle), não apenas a existência da classe.
- **CI como porta de qualidade, não relatório opcional:** gates que nunca falham dão falsa
  sensação de segurança. Tornar lint/tipos/segurança/segredos/CVE bloqueantes.
- **Teste de regressão para cada bypass conhecido:** o bypass de auth deve ter um teste que
  falhe caso o stub retorne. Isso transforma achados de auditoria em garantias permanentes.
- **Documentação como contrato verificável:** divergências `.env.example` × `auth.py` e
  `constitution.yaml` × agentes reais mostram que docs não testadas envelhecem. Testes de
  contrato de schema mantêm a documentação honesta.
- **Reaproveitar fortalezas existentes:** as soluções aqui propostas deliberadamente
  reutilizam padrões já maduros no projeto (`correlation_id`, `DecisionLedger`,
  externalização YAML, `InputSanitizer`), minimizando custo de adoção pela equipe.

---

*Relatório gerado por auditoria automatizada de conformidade documentação × código, com
verificação rastreável até `arquivo:linha`. Os vereditos refletem o estado da branch
`claude/confident-hopper-cBzPt` na data indicada.*
