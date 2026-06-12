# Ações Pendentes do Dono

Itens que requerem ação do proprietário do repositório para funcionamento pleno.
O agente autônomo prossegue nas demais implementações independentemente.
Atualizado automaticamente a cada sprint concluído.

---

## 🔴 BLOQUEANTE PARA PRODUÇÃO

### AP-01 — Secrets do Docker Registry (DT-13)
**O quê:** `cd-deploy.yml` está gateado em `workflow_dispatch` porque as secrets de registry não existem.
**Ação:** Configurar nos Secrets do repositório GitHub:
```
DOCKER_REGISTRY=<seu-registry>
DOCKER_USERNAME=<usuario>
DOCKER_PASSWORD=<senha ou token>
STAGING_URL=<url-da-staging>
```
**Depois:** Reverter trigger de `workflow_dispatch` para `push: branches: [master]` em `.github/workflows/cd-deploy.yml`.
**Referência:** PR #110, DT-13.

### AP-02 — PostgreSQL em produção
**O quê:** Todo o pipeline fiscal (escriturações, registros, apurações, auditoria) requer Postgres 15.
**Ação:**
1. Provisionar instância PostgreSQL 15 (Docker, RDS, Supabase, etc.)
2. Configurar variável de ambiente `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db`
3. Rodar `alembic upgrade head` para criar as tabelas
4. Configurar no compose: `docker compose up -d postgres`
**Referência:** S-0.1 (roadmap), `src/db/` (modelos já implementados).

### AP-03 — MinIO / S3 para armazenamento de arquivos SPED
**O quê:** Uploads SPED grandes (até 500MB) precisam de storage persistente.
**Ação:**
1. Provisionar MinIO (ou AWS S3/GCS)
2. Configurar:
```
MINIO_ENDPOINT=<host>
MINIO_ACCESS_KEY=<key>
MINIO_SECRET_KEY=<secret>
MINIO_BUCKET=sped-uploads
```
**Referência:** S-0.5 (roadmap).

### AP-04 — Celery Worker em produção
**O quê:** Processamento assíncrono de SPED (parse/validate/apuração) usa Celery.
**Ação:**
1. Garantir Redis rodando (já no compose): `REDIS_URL=redis://localhost:6379/0`
2. Configurar: `CELERY_BROKER_URL=redis://localhost:6379/0`
3. Subir worker: `celery -A src.workers.celery_app worker --loglevel=info`
**Referência:** `src/workers/`, S-0.5.

---

## 🟡 NECESSÁRIO PARA S-F (PER/DCOMP — capstone)

### AP-05 — Certificado Digital A1/A3 (homologação e-CAC)
**O quê:** S-F.1/F.3 requerem certificado para assinar e transmitir PER/DCOMP.
**Ação:**
1. Obter certificado A1 (arquivo `.pfx`) de uma AC credenciada pela ICP-Brasil
2. **NUNCA** colocar o .pfx em repositório, variável de ambiente ou imagem Docker
3. Configurar como volume/secret cifrado (Vault ou Docker secret):
   ```
   CERT_PATH=/run/secrets/cert.pfx
   CERT_PASSWORD=<senha>  # via secret, não env
   ```
4. Registrar AC e validade no vault (será implementado em S-F.1)
**Referência:** S-F.1/F.3 (roadmap).

### AP-06 — Acesso e-CAC homologação (Receita Federal)
**O quê:** S-F.3 transmite PER/DCOMP via webservice do e-CAC.
**Ação:**
1. Cadastrar certificado na Receita Federal (ambiente de homologação)
2. Verificar credenciais no portal e-CAC: https://cav.receita.fazenda.gov.br/
3. URL do webservice de homologação:
   `https://homolog.cav.receita.fazenda.gov.br/...` (a ser configurada em `config/`)
**Referência:** S-F.3 (roadmap).

---

## 🟢 RECOMENDADO (qualidade / observabilidade)

### AP-07 — Grafana + Prometheus em produção
**O quê:** Stack de observabilidade já existe no compose; precisa de provisionamento de dashboards.
**Ação:**
1. `docker compose up -d prometheus grafana alertmanager`
2. Acessar Grafana em `http://localhost:3000` (admin/admin por padrão)
3. Importar dashboards provisioned (serão adicionados em S-E.1)
**Referência:** S-E.1 (roadmap).

### AP-08 — Configurar RBAC de produção
**O quê:** Papéis fiscais (admin, auditor, perito, contador, cliente) precisam ser configurados para usuários reais.
**Ação:**
1. Revisar `src/api/auth.py` e `src/rbac/`
2. Criar usuários com papéis adequados via endpoint de administração (a ser implementado)
3. Configurar `JWT_SECRET_KEY` como secret seguro (não o valor padrão de desenvolvimento)
**Referência:** Faixas transversais — Segurança/LGPD (roadmap).

### AP-09 — Testar E2E com Postgres local antes de cada merge (protocolo)
**O quê:** Testes E2E (`test_golden_thread.py TestGoldenThreadE2E`) requerem Postgres real.
**Ação opcional (validação adicional local):**
```bash
docker run -d --name pg-test \
  -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=cij_test \
  -p 5432:5432 postgres:15-alpine

DATABASE_URL=postgresql+asyncpg://postgres:test@localhost:5432/cij_test \
  alembic upgrade head

DATABASE_URL=postgresql+asyncpg://postgres:test@localhost:5432/cij_test \
  pytest tests/integration/test_golden_thread.py -k E2E -v
```
**Referência:** Protocolo de trabalho (COORDENACAO_ONDA2.md seção 1).

---

## Histórico de ações concluídas pelo dono

| Ação | Data | PR |
|---|---|---|
| Merge PR #107 (S-C.3) antes do aval | 2026-06-12 | #107 |
| Merge PR #111 (S-C.4) antes do aval | 2026-06-12 | #111 |
| Sancionou S-D.1 e modo autônomo completo | 2026-06-12 | conversa |

## Sprints entregues em modo autônomo (2026-06-12)

| Sprint | Descrição | PR | Status |
|---|---|---|---|
| S-D.1 | SpedWriter + Retificação + HITL gate | #114 | ✅ merged |
| S-E.1 | Dashboards fiscais + KPIs | #116 | ✅ merged |
| S-F.1 | Cofre de credenciais & assinatura digital RSA-PSS | #118 | ✅ merged |
| S-F.2 | Gerador PER/DCOMP (Factory) + validação de layout | #119 | ✅ merged |
| S-E.2 | Relatórios premium + SQL Workbench seguro | #117 | ✅ merged |
| S-F.3 | Transmissão e-CAC + Circuit Breaker + Observer | #120 | ✅ merged |
| S-D.2 | Retificação SPED ponta-a-ponta (comparador, layout validator, nota de correção) | #121 | ✅ merged |
| S-G.1 | Painel operacional Escriturações SPED (upload, achados, registros, apuração) | #123 | ✅ merged |
| S-G.2 | Frontend: RetificacaoScreen + PERDCOMPScreen + TransmissaoScreen | #124 | 🔄 CI |

---

*Documento mantido automaticamente pelo agente. Última atualização: S-G.2 (2026-06-12).*
