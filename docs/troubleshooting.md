# 🔧 Troubleshooting (Circuit Breaker)

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
cat monitoring/prometheus.yml

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
cat logs/agent_decisions.json | jq -r 'select(.level=="ERROR")'

# Performance snapshot
curl -s http://localhost:8000/metrics | grep -E "(p95|p99|duration_seconds)"
```

---

## Contatos de Emergência

- **On-call Engineer**: oncall@example.com
- **SRE Team**: sre@example.com  
- **Status Page**: https://status.example.com

---

## 📚 Referências Técnicas

- **ADR-010**: Circuit Breaker Implementation
- **ADR-011**: Sandbox Security Decision
- **Métricas Prometheus**: `monitoring/dashboards/complete-operations-dashboard.json`
- **Logs Estruturados**: `logs/agent_decisions.json`
