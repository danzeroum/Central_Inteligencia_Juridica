# Pendências do Dono — v1

> Itens que **exigem decisão, configuração ou credencial do dono** e que eu **não posso
> resolver autonomamente** (não invento segredos nem acesso sistemas reais). Conforme
> combinado, registro aqui e **sigo para a próxima tarefa**. O código correspondente é
> implementado atrás das flags/stubs existentes, ativando quando o item abaixo for provido.

Status: 🔴 bloqueante p/ produção · 🟡 necessário p/ funcionalidade real · 🟢 recomendado

Complementa `docs/acaoPendenteDono.md` (mantido pelo histórico de sprints).

---

## Infraestrutura (Camada A — "ligar" o que está simulado)

| ID | 🔴/🟡 | Item | Efeito enquanto ausente | Como prover |
|---|---|---|---|---|
| PEND-01 | 🔴 | **PostgreSQL 15** (`DATABASE_URL` + `alembic upgrade head`) | Fiscal e `analytics` retornam `stub (sem DATABASE_URL)` | `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db` |
| PEND-02 | 🔴 | **MinIO/S3** + **Celery worker** | Uploads SPED grandes e parse assíncrono não persistem | `MINIO_*`, `CELERY_BROKER_URL`, subir worker |
| PEND-03 | 🟡 | **`DATAJUD_API_KEY`** + acesso Câmara | Jurisprudência/tribunais ficam `source=simulated` | chave da API pública DataJud/CNJ |
| PEND-04 | 🟡 | **Ollama+`llama3`** (`OLLAMA_BASE_URL`) e/ou **`OPENAI_API_KEY`** | IA (assistente, consultoria, CoT-LLM) cai em heurística/erro | subir Ollama ou prover chave OpenAI |

## Credenciais reguladas (Camada A — fiscal/fontes restritas)

| ID | 🔴/🟡 | Item | Efeito enquanto ausente | Como prover |
|---|---|---|---|---|
| PEND-05 | 🔴 | **Certificado A1 (.pfx)** + senha (via secret) | Transmissão e-CAC e assinatura PER/DCOMP em `is_stub` | `CERT_A1_PATH`+secret; nunca no repo |
| PEND-06 | 🔴 | **Acesso e-CAC homologação** (Receita Federal) | Transmissão real impossível (protocolo `STUB-…`) | `ECAC_HOMOLOGACAO_URL` + cadastro do cert |
| PEND-07 | 🟡 | **Fontes restritas CRC/CENPROT, CADIN, ONR** (captcha/credencial) | Investigação 360° sempre mock nessas fontes | credencial/worker anti-captcha (Onda 2) |
| PEND-08 | 🟢 | **`VAULT_MASTER_KEY`** | Vault de credenciais fica em modo stub/esqueleto | gerar chave forte como secret |

---

## Decisões de produto/abordagem que podem requerer aval do dono
_(registradas conforme surgem na execução; sigo com a opção recomendada e anoto aqui)_

- _(nenhuma ainda)_
