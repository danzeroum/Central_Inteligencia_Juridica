# Guia de Uso — Central de Inteligência Jurídica

Guia prático de **instalação, autenticação e teste** das funcionalidades da
plataforma. Para o passo a passo guiado pela interface, veja também o
[Manual do Estudante](MANUAL_ESTUDANTE.md).

---

## 1. Pré-requisitos

- **Python 3.11+**
- **Node 18+** (apenas para desenvolver o frontend; a SPA já vem pré-buildada)
- **Docker + Docker Compose** (opcional, recomendado)
- `git`

---

## 2. Instalação

### Caminho A — Docker (recomendado, sobe a stack completa)

```bash
git clone https://github.com/danzeroum/Central_Inteligencia_Juridica.git
cd Central_Inteligencia_Juridica

# 1. Configurar variáveis de ambiente (OBRIGATÓRIO)
cp .env.example .env
```

Edite o `.env` e preencha os **dois campos obrigatórios** (o resto tem default sensato):

```bash
# Segredo JWT (mín. 32 caracteres) — gere com:
python -c "import secrets; print(secrets.token_urlsafe(48))"
# cole o valor em JWT_SECRET=...

# Senha do Grafana (o serviço não sobe sem ela):
GF_SECURITY_ADMIN_PASSWORD=algumaSenhaForte
```

```bash
# 2. Subir a stack (API + Redis + Prometheus + Grafana + Alertmanager)
docker-compose up -d

# 3. Verificar saúde
curl http://localhost:8000/health
```

| Serviço | URL |
|---|---|
| **API + UI** | http://localhost:8000 |
| **Swagger (API interativa)** | http://localhost:8000/docs |
| **SPA (interface React)** | http://localhost:8000/app |
| Health | http://localhost:8000/health |
| Métricas Prometheus | http://localhost:8000/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (usuário/senha do `.env`) |

### Caminho B — Local sem Docker (desenvolvimento rápido)

```bash
git clone https://github.com/danzeroum/Central_Inteligencia_Juridica.git
cd Central_Inteligencia_Juridica

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Modo dev: autenticação relaxada (ENVIRONMENT=test)
export ENVIRONMENT=test          # PowerShell: $env:ENVIRONMENT="test"
uvicorn src.api.main:app --reload --port 8000
```

> Sem Redis/ChromaDB, o sistema usa **fallback em memória** automaticamente.
> Sem `OPENAI_API_KEY`, a classificação de intenção usa **heurística determinística**.

#### Frontend (opcional — a SPA já vem pré-buildada e versionada)

```bash
cd frontend
npm install
npm run build        # regenera src/api/static/spa, servido em /app
# ou, com hot-reload:
npm run dev          # http://localhost:5173 (proxy /api -> :8000)
```

---

## 3. Autenticação

Em produção (`AUTH_REQUIRED=true`) os endpoints exigem um JWT. Há usuários demo
em `development`/`test`; em produção, configure o store via variável `AUTH_USERS`.

| Usuário | Senha | Papel | Pode |
|---|---|---|---|
| `admin` | `admin` | admin | tudo |
| `operator` | `operator` | operator | HITL, consultas |
| `auditor` | `auditor` | auditor | ledger, LGPD (leitura) |

```bash
# Obter token
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
# -> {"access_token":"eyJ...","token_type":"bearer","user_id":"admin","roles":["admin"]}

# Guardar o token numa variável (bash)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

> Pela interface (`/app`), clique em **"Demo: Admin"** ou **"Demo: Operador"** na tela de login.

---

## 4. Casos de teste das funcionalidades

> Use o Swagger (`/docs`) para clicar, ou os `curl` abaixo. Em `ENVIRONMENT=test`
> você pode omitir o header `Authorization`.

### Caso 1 — Consulta jurídica (roteamento para tribunal) — *função principal*

Valida: o SupervisorAgent identifica o tribunal, delega e responde.

```bash
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task_description":"Qual o andamento do processo no TJSP sobre dano moral?"}'
```

✅ Esperado: JSON com `status: success`, `tribunals_used: ["TJSP"]`, `task_id`, `execution_time`.
Variações: troque por **TJMG**, **TJRS**, **TJRJ**, **STF**.

### Caso 2 — Consulta multi-tribunal (consenso ponderado)

Valida: paralelismo + WeightedConsensusEngine.

```bash
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task_description":"Compare a jurisprudência sobre dano moral no TJSP e no TJMG"}'
```

✅ Esperado: `tribunals_used` com dois tribunais.

### Caso 3 — Modo avançado (orquestração completa)

Valida: UnifiedOrchestrator (CoT + planejamento + consenso).

```bash
curl -s -X POST http://localhost:8000/api/v1/tasks/advanced \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task_description":"Elabore estratégia para recurso de apelação cível no TJRS"}'
```

✅ Esperado: payload com `mode: advanced`, `reasoning`, `consensus`.

### Caso 4 — Segurança: limite de entrada (anti-DoS) — deve **falhar**

Valida: validação de `task_description` (máx. 5000 caracteres).

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"task_description\":\"$(python -c 'print("a"*6000)')\"}"
```

✅ Esperado: **422** (payload rejeitado).

### Caso 5 — Segurança: XSS sanitizado

Valida: InputSanitizer na borda da API.

```bash
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task_description":"<script>alert(1)</script> processo TJSP"}'
```

✅ Esperado: 200, e o `<script>` **não** aparece refletido na resposta.

### Caso 6 — Segurança: RBAC (autorização) — deve **bloquear**

Valida: papel insuficiente → 403. Rode com `AUTH_REQUIRED=true`.

```bash
# token de auditor (não possui agents:manage)
AUD=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"auditor","password":"auditor"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/v1/training/train \
  -H "Authorization: Bearer $AUD" -H "Content-Type: application/json" \
  -d '{"agent_type":"TJSP"}'
```

✅ Esperado: **403**. (Sem token nenhum → **401**.)

### Caso 7 — Consulta legislativa (API da Câmara dos Deputados)

```bash
curl -s "http://localhost:8000/consultar-projetos-lei/?q=inteligencia%20artificial" \
  -H "Authorization: Bearer $TOKEN"
```

✅ Esperado: lista de projetos de lei (ou erro 502 amigável se a API externa estiver indisponível).

### Caso 8 — Análise legislativa por IA

```bash
curl -s -X POST http://localhost:8000/analise-legislativa/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tema":"proteção de dados"}'
```

✅ Esperado: `analise_ia` com um resumo (usa Ollama se disponível; degrada com mensagem se não).

### Caso 9 — Fluxo HITL (Human-in-the-Loop) — *pela interface*

1. Acesse `http://localhost:8000/app` → login **Demo: Admin** → menu **Aprovações**.
2. Dispare uma tarefa de baixo consenso (Caso 2/3) que caia em revisão humana.
3. Veja o card aparecer em tempo real (WebSocket) e use **Aprovar / Modificar / Rejeitar**.

✅ Esperado: a decisão é registrada no Ledger sob **o seu usuário autenticado**
(não mais um operador fixo hardcoded).

### Caso 10 — Autonomia (DMN) — alterar limiares

```bash
curl -s -X PUT http://localhost:8000/api/v1/autonomy/config \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"consensus_threshold":0.7}'
```

✅ Esperado: config atualizada + `decision_table`. Na UI (menu **Autonomia**), os
campos só aceitam números entre 0 e 1.

### Caso 11 — Auditoria (Decision Ledger)

```bash
curl -s "http://localhost:8000/api/v1/ledger?limit=20" -H "Authorization: Bearer $TOKEN"

# Exportar CSV:
curl -s "http://localhost:8000/api/v1/ledger/export.csv" \
  -H "Authorization: Bearer $TOKEN" -o ledger.csv
```

✅ Esperado: entradas de auditoria (quem decidiu, quando, aprovado).
Requer papel `ledger:read` (admin/auditor).

### Caso 12 — LGPD (direitos do titular)

```bash
# Acesso aos dados de um titular
curl -s "http://localhost:8000/api/v1/lgpd/data/cliente123" -H "Authorization: Bearer $TOKEN"

# Exclusão/anonimização (admin)
curl -s -X DELETE "http://localhost:8000/api/v1/lgpd/data/cliente123?justification=pedido%20do%20titular" \
  -H "Authorization: Bearer $TOKEN"
```

✅ Esperado: registros do titular / confirmação de anonimização preservando a trilha de auditoria.

### Caso 13 — Treinamento contínuo (feedback)

```bash
curl -s -X POST http://localhost:8000/api/v1/training/feedback \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent_type":"TJSP","task_result":{"ok":true},"user_rating":0.9}'
```

✅ Esperado: `202 Accepted` (feedback enfileirado). Veja estatísticas em
`GET /api/v1/training/stats`.

### Caso 14 — Observabilidade

```bash
curl -s http://localhost:8000/metrics | head            # métricas Prometheus
curl -s "http://localhost:8000/health?verbose=true" -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/monitoring/health -H "Authorization: Bearer $TOKEN"
```

✅ Esperado: métricas no formato Prometheus; saúde de circuit breakers, fila HITL e canal A2A.

### Caso 15 — Rodar a suíte de testes (validação técnica)

```bash
ENVIRONMENT=test pytest tests/unit tests/integration -q

# Frontend:
cd frontend && npm test && npm run lint
```

✅ Esperado: suíte backend verde + testes de frontend; ESLint sem erros.

---

## 5. Solução de problemas

| Sintoma | Causa / Solução |
|---|---|
| Boot falha: `JWT_SECRET must be set` | Defina `JWT_SECRET` no `.env` (ou `export ENVIRONMENT=test` em dev). |
| Quero explorar sem login | Rode local com `ENVIRONMENT=test` (autenticação relaxada). |
| Grafana não sobe | Falta `GF_SECURITY_ADMIN_PASSWORD` no `.env`. |
| `429 Too Many Requests` | Rate limiting (60/min por padrão); ajuste `RATE_LIMIT_PER_MINUTE`. |
| `401` em todos os endpoints | Falta o header `Authorization: Bearer <token>` (veja a seção 3). |
| `403` num endpoint | Seu papel não tem a permissão exigida (use `admin` para tudo). |
| Referência de todos os endpoints | http://localhost:8000/docs |

---

## 6. Documentação relacionada

- [Manual do Estudante](MANUAL_ESTUDANTE.md) — roteiro guiado pela interface
- [Primeiros passos](tutorials/getting_started.md)
- [Arquitetura C4](ARCHITECTURE_C4.md)
- [ADRs](ADRs/README.md) — decisões arquiteturais
- [Troubleshooting](troubleshooting.md)
