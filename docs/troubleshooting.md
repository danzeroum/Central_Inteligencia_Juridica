<<<<<<< HEAD
# 🔧 BuildToFlip v6 - Troubleshooting

## Problemas Comuns

### 1. Gates falhando sem motivo aparente
**Sintoma**: `./scripts/gates-v6.sh` retorna erro mas testes passam localmente

**Solução**:
```bash
rm -rf .buildtoflip/cache/*
docker-compose down -v
docker-compose up -d
VERBOSE=true ./scripts/gates-v6.sh
```
Registrar override se necessário:
```bash
echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","type":"gate_override","gate":"[nome]","reason":"[motivo]"}' >> .buildtoflip/ledger/overrides.log
```

### 2. Performance abaixo da meta
**Sintoma**: P95 > 800ms

**Diagnóstico**:
```bash
./mvnw spring-boot:run -Dspring-boot.run.jvmArguments="-Xmx1024m -XX:+FlightRecorder"
grep "SQL" logs/application.log | tail -100
```
**Soluções comuns**: adicionar índices, implementar cache (Redis), otimizar queries N+1, ajustar pool de conexões.

### 3. Conflito de consenso entre IAs
**Sintoma**: IAs não chegam a consenso após 3 rodadas

**Solução**: ativar fallback humano, registrar decisão manual:
```bash
echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","event":"human_fallback","decision":"[escolha]","reason":"[justificativa]"}' >> .buildtoflip/ledger/decisions.log
```

### 4. Mock data não marcado
**Sintoma**: Dados de teste aparecem em produção

**Soluções**:
```java
if (mockEnabled) {
    response.addHeader("X-BTF-Mock", "true");
}
```
```javascript
if (response.headers.get('X-BTF-Mock')) {
    showMockIndicator();
}
```

## Comandos de Diagnóstico
```bash
./scripts/health-check-v6.sh
jq '.level == "ERROR"' < logs/application.json | tail -20
curl -s http://localhost:8080/actuator/prometheus | grep -E "p95|error_rate"
grep "traceId=ABC123" logs/*.log
jq '.event' < .buildtoflip/ledger/decisions.log | sort | uniq -c
```

## Contatos de Emergência
- On-call Engineer: oncall@buildtoflip.com
- Squad Lead: squad@buildtoflip.com
- SRE Team: sre@buildtoflip.com
- Status Page: https://status.buildtoflip.com

## 📚 Glossário
| Termo | Definição |
|-------|-----------|
| ADR | Architecture Decision Record |
| Crisp Pragmatist | Filosofia com disciplina mínima e valor máximo |
| Fast Consensus | Método de decisão por maioria simples entre IAs |
| Foundation Level | Nível de complexidade do projeto |
| Gates | Critérios de qualidade obrigatórios |
| Ledger | Registro imutável de decisões e overrides |
| Mock Data | Dados sintéticos marcados com X-BTF-Mock |
| Must Have | Funcionalidades essenciais |
| P95 | Percentil 95 de latência |
| RFC 7807 | Padrão Problem Details |
| Squad | Conjunto de IAs especializadas |
| TraceId | Identificador de rastreamento |
| Vendor Readiness | Preparação para venda/entrega |

## 🏁 Conclusão
BuildToFlip v6 entrega valor real rápido, com rastreabilidade total e foco em vendabilidade.
=======
# 🔧 BuildToFlip v6 - Troubleshooting (Atualizado com Circuit Breaker)

## Problemas Comuns

### 1. Circuit Breaker Aberto (🔴 Status RED)

**Sintoma**: Logs mostram `circuit_breaker_state=1` (OPEN) para um serviço

**Causa**: O serviço (Redis ou API de Tribunal) teve múltiplas falhas consecutivas

**Diagnóstico**:
```bash
# Verificar estado atual dos circuit breakers
curl -s http://localhost:8000/metrics | grep circuit_breaker_state

# Ver falhas recentes
curl -s http://localhost:8000/metrics | grep circuit_breaker_failures

# Logs detalhados
docker-compose logs agent-system | grep "CircuitBreaker"
```

**Soluções**:

**Para Redis:**
```bash
# Verificar se Redis está rodando
docker-compose ps redis

# Reiniciar Redis se necessário
docker-compose restart redis

# O sistema automaticamente failará para cache in-memory
# Verifique nos logs: "Falling back to in-memory cache"
```

**Para API de Tribunal:**
```bash
# Verificar conectividade
curl -I https://api.tjsp.jus.br/v2/status

# Se API externa estiver offline, o sistema usará dados simulados
# Verifique no response: "meta": {"source": "simulated", "fallback": true}

# O circuit breaker tentará reabrir após 60 segundos (half-open)
```

**Recuperação Automática**:
- Após `recovery_timeout` (60s), circuit breaker entra em HALF_OPEN
- Próxima requisição testa o serviço
- Se sucesso: volta para CLOSED
- Se falha: volta para OPEN por mais 60s

---

### 2. Alta Latência (P95 > 1500ms)

**Sintoma**: Dashboard mostra P95 acima da meta

**Diagnóstico**:
```bash
# Verificar se circuit breakers estão funcionando
curl -s http://localhost:8000/metrics | grep circuit_breaker_state

# Analisar distribuição de latência
curl -s http://localhost:8000/metrics | grep tribunal_task_duration_seconds

# Verificar cache hit rate
curl -s http://localhost:8000/metrics | grep cache_hits_total
```

**Soluções**:
- Se circuit breakers estão OPEN: aguarde recuperação ou investigue serviço
- Se cache hit rate baixo (<50%): aumentar TTL ou investigar padrões de consulta
- Se APIs externas lentas: considerar aumentar timeout ou adicionar fallback

---

### 3. Erros Intermitentes de Cache

**Sintoma**: Logs mostram alternância entre Redis e in-memory

**Causa**: Instabilidade na conexão Redis

**Diagnóstico**:
```bash
# Status do circuit breaker do cache
curl -s http://localhost:8000/metrics | grep 'circuit_breaker_state{name="cache-redis"}'

# Logs de fallback
docker-compose logs agent-system | grep -E "(Falling back|degraded)"
```

**Solução**:
```bash
# Verificar health do Redis
docker-compose exec redis redis-cli ping

# Verificar conectividade de rede
docker-compose exec agent-system ping redis

# Se problema persistir, o sistema continuará operando em modo in-memory
# Dados em memória serão perdidos no restart - considere persistir cache crítico
```

---

### 4. Dashboard Grafana Sem Dados

**Sintoma**: Painéis vazios no Grafana

**Diagnóstico**:
```bash
# Verificar se Prometheus está scrapando métricas
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Verificar se app está expondo métricas
curl -s http://localhost:8000/metrics | head -20
```

**Solução**:
```bash
# Reiniciar stack de monitoramento
docker-compose restart prometheus grafana

# Verificar configuração do Prometheus
cat docker/prometheus.yml

# Recarregar dashboard no Grafana
# Grafana UI > Dashboards > Import > monitoring/dashboards/complete-operations-dashboard.json
```

---

## Comandos de Diagnóstico Rápido

```bash
# Status geral do sistema
./scripts/health-check-v6.sh

# Métricas de circuit breaker
curl -s http://localhost:8000/metrics | grep -E "circuit_breaker_(state|failures|successes)"

# Top 5 erros recentes
docker-compose logs agent-system --tail=100 | grep ERROR | tail -5

# Verificar ledger de decisões
cat .buildtoflip/ledger/decisions.log | jq -r 'select(.level=="ERROR")'

# Performance snapshot
curl -s http://localhost:8000/metrics | grep -E "(p95|p99|duration_seconds)"
```

---

## Contatos de Emergência

- **On-call Engineer**: oncall@buildtoflip.com
- **SRE Team**: sre@buildtoflip.com  
- **Status Page**: https://status.buildtoflip.com

---

## 📚 Referências Técnicas

- **ADR-010**: Circuit Breaker Implementation
- **ADR-011**: Sandbox Security Decision
- **Métricas Prometheus**: `monitoring/dashboards/complete-operations-dashboard.json`
- **Logs Estruturados**: `logs/agent_decisions.json`
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
