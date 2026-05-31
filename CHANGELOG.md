# Changelog - Central de Inteligência Jurídica

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Não lançado] - Remediação da auditoria técnica

### 🔒 Security
- **AuthZ/RBAC** em todos os endpoints sensíveis antes desprotegidos: training,
  autonomy `PUT /config`, ledger (lista/export), A2A messages/history, agent
  discovery, HITL pending/stats e o handshake do WebSocket HITL; consultas
  legislativas e histórico passam a exigir autenticação (CRÍTICO-01..04, H02–H04).
- **Login real** da SPA via novo `POST /auth/login` (emite JWT com papéis/timeout);
  remove o login fake e o `OPERATOR_ID` hardcoded (CRÍTICO-09/10). O frontend
  injeta `Authorization: Bearer`, limpa a sessão no 401 e envia o token no WS (FH01).
- **XSS** eliminado nas páginas estáticas (`hitl.html`, `index.html`,
  `training-dashboard.html`) via `escapeHtml()` (CRÍTICO-11/12/13).
- `SafetyProtocol.validate_output` deixa de ser no-op (redação de PII + truncamento)
  (CRÍTICO-14); segredo JWT nunca mais vazio em `ENVIRONMENT=test` (H01).
- Handler global de exceções (sem vazar stack trace), CORS com métodos/headers
  explícitos por env, validação/limite de entrada (task/payload/subject_id) e
  rate limiting estendido a mais endpoints (H07/H08/H14/H15/H17/M01/M05/M07/M09/M10).

### 🐛 Fixed
- `llm_client`: `NameError` (`_OLLAMA_CLIENT` indefinido) → cliente lazy + fallback
  gracioso (CRÍTICO-05). `AdaptiveReplanner` agora replaneja de fato (CRÍTICO-07).
- Colisões de nome de classe resolvidas (`AdaptiveReplanner`, `TrajectoryEvaluator`)
  (CRÍTICO-08); `asyncio.get_running_loop()` no A2A (CRÍTICO-15).
- `VectorMemory` instanciado preguiçosamente (não bloqueia o startup) (H10);
  `tribunal_api_client` fecha o HTTP client (context manager) (H12);
  `datetime.now(timezone.utc)` em observability (M06).

### ✅ Added
- Endpoint `/metrics` (Prometheus). Tooling de frontend: Vitest + ESLint
  (regra anti-`innerHTML`/`no-danger`). Acessibilidade: focus trap no Modal e
  inputs numéricos no DMN (M12/M15).

### 🧹 Removed
- Código morto: `src/config.py`, `src/protocols/squad_orchestrator.py`,
  `src/memory/intelligent_forgetting.py`, `config/prompts/advanced_agent_prompts.py`,
  `config/agents/constitution.yaml` (D06 e correlatos).

### 📝 Docs
- Auditoria reavaliada: itens já resolvidos confirmados com testes de regressão
  (validação de `agent_id`, **CI/CD existente** — corrige a alegação D11 de que
  `.github/` não existiria).

---

## [1.1.0] - 2026-05-30

### ✅ Added
- **SPA React + Vite** com 12 telas (Espaço de Trabalho + Administração), servida
  pelo FastAPI em `/app`; substitui as páginas estáticas isoladas.
- Endpoints de suporte à UI: `/api/v1/ledger` (+ export CSV), `/api/v1/autonomy/config`
  (GET/PUT), `/api/v1/monitoring/health`, `/api/v1/hitl/stats`, `/api/v1/history`;
  `/api/v1/agents` enriquecido com trust score e nível de autonomia.
- Console HITL acessível (aria-live, foco, atalhos) com "Modificar" funcional,
  confirmação proporcional ao risco e rejeição com justificativa.
- Registro global de circuit breakers (consumido pelo monitoramento).
- Manual do Estudante (`docs/MANUAL_ESTUDANTE.md`) e arquitetura C4
  (`docs/ARCHITECTURE_C4.md`).

### 🐛 Fixed
- `IntentClassifier`: `NameError` no fallback (`process_keywords` indefinido) que
  derrubava buscas de jurisprudência e consultas genéricas sem LLM.

### 🔧 Changed
- Trilha de auditoria e gestor de autonomia agora usam singletons compartilhados
  (`get_ledger()`, `get_autonomy_manager()`).
- Documentação: consolidação dos ADRs numa única pasta `docs/ADRs/`, reescrita do
  getting-started e dos user-flows, OpenAPI gerada do app (`/docs`), limpeza de
  scaffolding (`scripts/dev/`).

### 🧪 Tests
- Suíte ampliada para 231 casos (+ `test_intent_classifier`, `test_hitl_queue`;
  reforço de consenso, autonomia, circuit breaker e endpoints da SPA).

---

## [1.0.0] - 2025-09-30

### ✅ Added
- Sistema multi-agente completo (SupervisorAgent + TribunalAgents)
- API REST com FastAPI
- Circuit Breaker pattern (ADR-010)
- Cache resiliente (Redis + in-memory fallback)
- Input sanitization e guardrails
- Rate limiting por IP
- Autenticação JWT opcional
- Métricas Prometheus
- Dashboard Grafana completo
- Decision ledger para auditoria
- UI web interativa
- Documentação completa (ADRs)
- Suíte de testes unitários e de integração

### 🔧 Changed
- Movido sandbox para `experimental/security/` (ADR-011)
- Atualizado troubleshooting guide com procedimentos de Circuit Breaker

### 🐛 Fixed
- **[FASE 1]** Bug de roteamento com query params não sanitizados (ADR-010)
- **[FASE 2]** Implementado Circuit Breaker para resiliência (ADR-010)
- **[FASE 3]** Fixado NumPy < 2.0 para compatibilidade com ChromaDB (ADR-012)

### 📚 Documentation
- ADR-001 a ADR-012 completas
- OpenAPI specification
- UI Kit e mockups
- Executive summary

### 🔒 Security
- Input sanitization contra XSS, SQL injection, path traversal
- Rate limiting configurável
- JWT authentication
- Guardrails ativos
- Audit logging

---

## [Unreleased] - Future Work

### Planned for Standard Level
- [ ] Integração com APIs reais dos tribunais
- [ ] OAuth2 completo
- [ ] Webhooks para notificações
- [ ] Cache distribuído (Redis Cluster)
- [ ] Dashboard de analytics avançado

### Planned for Enterprise Level
- [ ] Multi-region deployment
- [ ] Event sourcing / CQRS
- [ ] Machine Learning para predição de resultados
- [ ] Service mesh (Istio/Linkerd)
- [ ] Chaos engineering tests

### Technical Debt
- [ ] Upgrade ChromaDB para 0.5.0+ (aguardando estabilidade) - veja ADR-012
- [ ] Upgrade NumPy para 2.0+ após upgrade ChromaDB
- [ ] Refatorar `src/tools/rag_tool.py` para nova API ChromaDB

---

## Dependencies Constraints

| Package | Version | Reason |
|---------|---------|--------|
| numpy | <2.0.0 | ChromaDB compatibility (ADR-012) |
| fastapi | 0.111.0 | Stable production version |
| pytest | 7.4.0 | Test framework compatibility |

---

## Notes

### ChromaDB / NumPy Compatibility (2025-09-30)
ChromaDB versões < 0.5.0 são incompatíveis com NumPy 2.0+ devido ao uso de `np.float_` (deprecated).

**Workaround atual**: NumPy fixado em < 2.0.0  
**Solution permanente**: Aguardar ChromaDB 0.5.0 stable e refatorar código  
**Tracking**: ADR-012

### Circuit Breaker Configuration
Circuit breakers configurados com:
- **failure_threshold**: 5 falhas
- **recovery_timeout**: 60 segundos
- **success_threshold**: 2 sucessos (half-open → closed)

Ajustar via environment variables se necessário.

---

**Last Updated**: 2025-09-30  
**Project Version**: 1.0.0  
**Project**: Central de Inteligência Jurídica
