# Changelog - Central de Inteligência Jurídica

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
- Documentação completa (11 ADRs)
- Testes com 92% coverage

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
- BuildToFlip v6 Certificate

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
**Methodology**: BuildToFlip v6.1
