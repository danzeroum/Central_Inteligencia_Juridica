# Cloud-Readiness — Docker hoje, nuvem amanhã

Este documento descreve as costuras (*seams*) introduzidas para que o sistema
rode em **Docker single-node hoje** e **escale horizontalmente na nuvem amanhã**
sem retrabalho. O princípio: todo estado em processo fica atrás de uma interface
com **backend selecionável por variável de ambiente**. O padrão preserva o
comportamento atual; ligar o modo compartilhado é só mudar uma env.

## Por que isto importa

Rodar N réplicas atrás de um load balancer quebra qualquer estado guardado na
memória de um único processo. Os três pontos críticos foram externalizáveis:

| Componente | Padrão (single-node) | Cloud (multi-réplica) | Env |
|---|---|---|---|
| Rate limiter | `memory` (deque em processo) | `redis` (sorted-set compartilhado) | `RATE_LIMIT_BACKEND` |
| Decision Ledger | `file` (JSONL local) | `redis` (lista compartilhada) | `LEDGER_BACKEND` |
| Fila HITL | `memory` (asyncio em processo) | `redis` (hash + polling) | `HITL_BACKEND` |

Sem isto: o limite de requisições seria multiplicado pelo nº de réplicas; a
trilha de auditoria e a fila de aprovação humana ficariam fragmentadas entre
réplicas.

## Mapa das costuras

- **Cliente Redis único** — `src/utils/redis_client.py`. Toda conexão Redis
  (cache, rate limiter, ledger, HITL) vem daqui. Migrar para ElastiCache/MemoryStore
  é só ajustar `REDIS_URL`/`REDIS_HOST`/`REDIS_PASSWORD`.
- **Rate limiter** — `src/api/rate_limiter.py`. `redis` usa janela deslizante via
  sorted-set; degrada para memória se o Redis cair (não bloqueia o tráfego).
- **Decision Ledger** — `src/utils/ledger.py`. `LedgerStore` com `FileLedgerStore`
  (default) e `RedisLedgerStore`. Inclui `anonymize_entries(...)` como costura LGPD
  (direito de exclusão preservando append-only).
- **Fila HITL** — `src/hitl/hitl_queue.py`. `HITLStore` com `MemoryHITLStore`
  (default, orientado a eventos) e `RedisHITLStore` (polling como wake-up entre
  réplicas; próximo passo natural é pub/sub).
- **Logging estruturado + correlation-ID** — `src/utils/logging_config.py` e
  `src/api/middleware/request_context.py`. `LOG_FORMAT=json` emite logs prontos
  para agregadores (CloudWatch/Loki/Datadog). O `X-Request-ID` é lido/gerado por
  requisição, propagado para logs, ledger e tracing.
- **Tracing distribuído** — `src/utils/tracing.py`. OTLP **inerte** sem
  `OTEL_EXPORTER_OTLP_ENDPOINT`. Localmente: `docker compose --profile tracing up`
  (Jaeger em `http://jaeger:4318`). Na nuvem: apontar a env para X-Ray/Tempo/Datadog.
- **Cifragem do cache + chave KMS-ready** — `src/utils/key_provider.py` e
  `CacheManager`. `CACHE_ENCRYPTION_ENABLED=true` cifra valores sensíveis (Fernet);
  a chave vem do `KeyProvider` (`EnvKeyProvider` hoje, `KmsKeyProvider`/`VaultKeyProvider`
  depois — sem tocar no `CacheManager`).
- **Segurança de transporte** — `src/api/middleware/security_headers.py`. HSTS
  ativa com `ENABLE_HSTS=true` (quando há TLS terminado por proxy/ingress).
- **Container** — `docker-compose.yml`: Redis com `--requirepass`, imagens
  fixadas, `deploy.resources.limits` (mapeiam para requests/limits do K8s),
  `read_only` + `cap_drop: ALL` + `no-new-privileges`.

## Como ligar o modo nuvem (quando escalar)

```bash
# Estado compartilhado entre réplicas
RATE_LIMIT_BACKEND=redis
LEDGER_BACKEND=redis
HITL_BACKEND=redis

# Observabilidade para agregadores/tracing gerenciados
LOG_FORMAT=json
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318

# TLS terminado por proxy/ingress à frente
ENABLE_HSTS=true

# Cifragem em repouso (chave de um segredo gerenciado)
CACHE_ENCRYPTION_ENABLED=true
CACHE_ENCRYPTION_KEY=<fernet-key>
```

O `ChromaDB` já suporta modo `HttpClient` (`VECTOR_MEMORY_MODE=remote`), então a
memória vetorial vira um serviço gerenciado sem mudança de código. O JWT é
stateless por design.

## Fora de escopo (próximos passos, exigem nuvem real)

Módulos Terraform/K8s + HPA/auto-scaling; KMS/Vault de fato (a interface já
existe); serviços gerenciados (ElastiCache/Pinecone); pub/sub para wake-up HITL
entre réplicas; multi-region/DR; CD canary/blue-green. Camada de compliance
ampla (RBAC, endpoints LGPD, PII no input, bind de `operator_id`/`sender_id` ao
JWT) também fica para uma entrega seguinte.
