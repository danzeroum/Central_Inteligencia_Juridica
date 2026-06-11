# Programa Onda 2 — Plataforma Modular de Engenharia Tributária

> **Prompt de hand-off para o desenvolvedor.** Síntese de dois documentos de produto (Plano
> Modular por Plugin + Análise Arquitetural C4, jun/2026) confrontada com o estado **real** do
> código no `master` (commit `dbb2772`). Escopo travado com o stakeholder: **Fundação Modular +
> Onda 2 completa** · **monolito modular + 1 worker SPED extraído** · **transmissão oficial real**
> (homologação) · **PER/DCOMP federal como 1º fluxo ponta-a-ponta**. Onda 3 fica esboçada no fim.

## 0. Como usar este documento

É um prompt de execução para o desenvolvedor (humano ou agente). Cada sprint tem objetivo,
entregas e **Definition of Done verificável**. Regras inegociáveis do repo: `black --check`
bloqueia CI; toda mudança vem com testes; **zero regressão na Onda 1** (822 passed / 16 skipped é
a linha de base); identificadores sempre mascarados (LGPD); nada de segredo/certificado em
repo/env/imagem. Numere os sprints continuando a convenção do repo (Onda 1 foi S1–S10).

## 1. Baseline REAL validada (correções aos documentos de produto)

Os PDFs referenciam v1.1.0/commit antigo e contêm imprecisões. Validado no `master`:

| Afirmação dos documentos | Realidade verificada | Impacto no plano |
|---|---|---|
| "Armazenamento é feito em PostgreSQL" | **Postgres NÃO existe.** Compose só tem redis, chromadb, prometheus, alertmanager, grafana. Persistência hoje = Redis + arquivo (ledger) + ChromaDB + memória | **Base relacional é greenfield e é o tijolo nº 1** |
| `main.py` 912 LOC | **1262 LOC** | God module maior; refactor com golden tests antes |
| "Redis apenas para cache" / "event bus não existe" | `a2a_channel.py` já faz **Redis pub/sub** com fallback memória | Há semente de bus; falta durabilidade (Streams) |
| "Evoluir registry.py para Module Registry" | `registry.py` é **AdapterRegistry in-process** (sem rede/manifest/licença) | Module Registry é construção nova sobre o padrão, não evolução trivial |
| Celery / MinIO / Rules Engine | **Não existem** | Infra assíncrona + storage + engine são novos |
| fiscal_agent / intelligence_agent | **Já existem** (Onda 1) | Quick-win fiscal tem semente |
| 75% do core reaproveitável | **Confirmado plausível**: cache_manager, circuit_breaker, rate_limit, rbac, pii, weighted_voting, observability, ledger, redis_client, input_sanitizer, HITL/progressive_autonomy, registry, alert_rules — todos presentes e 1:1 ou quase | Reuso é real; investimento concentra-se no domínio fiscal novo |

## 2. Veredito da arquitetura modular ("vai atender?")

**Sim — com duas correções de rota que este plano impõe:**

1. **Separar modularidade COMERCIAL de modularidade FÍSICA.** O plano de produto quer cada módulo
   como container Docker independente com auto-registro HTTP, hot-plug e menus via SSE já na
   Onda 1/2. Isso é microserviços-lite caro e arriscado para um time que ainda não dividiu o
   `main.py`. A análise C4 acerta: "monolito modular nas Fases 1-3, containers por módulo só na
   Fase 4+". **Decisão:** obter todo o resultado de negócio (vender módulos avulsos, upsell sem
   migração, menus dinâmicos, licença por módulo) **dentro do monolito**, via license-gating +
   manifest + slots de UI. Os "seams" (fronteiras internas + manifesto) tornam a extração futura
   para container uma mudança de configuração, não um rewrite.
2. **A única extração de container justificada agora é o worker SPED** — por isolamento de
   workload (meta: SPED 500MB em ≤5 min), não por modularidade. Postgres + MinIO + Celery são a
   infra nova de verdade; "containers por módulo" não são.

Com isso o programa preserva o modelo comercial e a opção de evoluir para microserviços, pagando
só a complexidade que gera valor hoje. **Mapa módulo comercial → bloco técnico:** Core=Bloco 0;
Inteligência Jurídica=Onda 1 (pronto); Cadastro e Risco=A.1; Auditoria Tributária=Blocos B+C+D+E;
Obrigações Federais=Bloco F; Obrigações SP/Estaduais/Crédito/BI/RJ=Onda 3.

## 3. Arquitetura alvo (containers reais ao fim da Onda 2)

```
Frontend React+Vite (shell + slots dinâmicos por módulo)         [evolui o existente]
  └─ Backend FastAPI "Core" (app_factory, routes/, middleware/, config; Module Registry;
      auth/RBAC; API gateway interno; license control; agentes via AgentInterface)  [evolui]
       ├─ PostgreSQL 15 (modelo canônico fiscal + apurações + trilha)               [NOVO]
       ├─ Redis 7 (cache + circuit breaker + pub/sub A2A + broker Celery)           [evolui]
       ├─ ChromaDB (RAG jurídico + tributário)                                      [existe]
       ├─ MinIO/S3 (uploads SPED 500MB+, arquivos gerados, backups)                 [NOVO]
       └─ Celery Worker SPED (parse/validate/apura/gera em batch)            [NOVO container]
Observabilidade: Prometheus+Grafana+OTel/Jaeger (evolui) · Vault de certificados (NOVO, Bloco F)
```

Padrões de projeto aplicados: **Strategy** (parsers por layout) · **Factory** (geradores por
tipo/UF) · **Decorator** (camadas de validação fiscal) · **Observer** (eventos de processamento/
transmissão) · **Adapter** (fontes externas SEFAZ/e-CAC) · **Repository** (acesso a dados
fiscais, com decorator de cache).

---

## 4. BLOCO 0 — Fundação Modular & Plataforma (pré-requisito de tudo; de-risk)

### S-0.1 Persistência relacional (greenfield, nº 1 do caminho crítico)
Postgres 15 no compose; SQLAlchemy 2 async + Alembic; `src/db/` (engine, session, base). Modelo
inicial: `tenant`, `module`, `license`, `fiscal_audit` (trilha). Migrar ledger file→Postgres
**mantendo compat** (backend selecionável, como HITL/rate-limit). **DoD:** app sobe com Postgres;
`alembic upgrade head` no CI; health inclui DB; ledger grava em Postgres sem quebrar testes Onda 1.

### S-0.2 Decomposição do god module `main.py` (1262 LOC)
**Golden tests primeiro** (snapshot de rotas + OpenAPI + smoke de subida) como rede de proteção.
Extrair `app_factory.py`, `routes/`, `middleware/`, `config.py`. **DoD:** OpenAPI idêntico antes/
depois; `main.py` ≲ 150 linhas; 0 regressão; imports externos preservados.

### S-0.3 Sistema de módulos (Module Registry + manifest + licença + AgentInterface)
`manifest.json` schema (module_id, version, required_core_version, dependencies,
exposed_endpoints, health_check_path, menu_entries, configuration_schema). `ModuleRegistry`
**in-process** com validação de licença e dependências; `POST /core/registry/register` (interno) e
`GET /core/registry/modules`. `AgentInterface` abstrato (`execute/validate/report`) para agentes
jurídicos e fiscais coexistirem. **DoD:** 2 módulos fake registram; dependência ausente bloqueia;
licença inválida nega; teste do contrato de manifesto.

### S-0.4 Slots dinâmicos no frontend
Shell React renderiza seções/menus a partir dos módulos ativos (endpoint de config + SSE para
atualização sem reload), reusando os design tokens. Licença → visibilidade na UI. **DoD:** ligar/
desligar módulo muda a navegação sem rebuild; menu do Core intacto.

### S-0.5 Infra assíncrona & storage
Celery + Redis broker; MinIO/S3 no compose; padrão de job (`enqueue/status/result`) com tracing/
métricas; client de storage com upload seguro (limites, antivírus opcional). **DoD:** job exemplo
processa em worker separado; status via API; arquivo persistido no MinIO; span no Jaeger.

## 5. BLOCO A — Quick Wins Fiscais (valor imediato, reusa Onda 1)

### S-A.1 Due Diligence Fiscal 360° ampliada (módulo "Cadastro e Risco")
Cruza cadastrais/societários (Onda 1) + situação fiscal + protestos + passivo tributário numa
visão única; empacota como módulo comercial. Reusa `orchestrator`/`risk_engine`, reforça a
dimensão fiscal. **DoD:** relatório 360° jurídico+fiscal por CNPJ; módulo registrável/licenciável.

### S-A.2 Consultoria Tributária assistida
Recomendações por perfil (regime, CNAE, porte) via `fiscal_agent` + **RAG tributário** (ingestão
de legislação/soluções de consulta no ChromaDB existente). **DoD:** parecer preliminar com
citações verificáveis; guardrails CJ-001 (sem inventar norma).

## 6. BLOCO B — Ingestão & Normalização (Pilar 1, caminho crítico)

### S-B.1 Modelo canônico + Repository + upload seguro
Entidades canônicas (escrituração, registro, documento fiscal, período) no Postgres; padrão
Repository (Postgres + decorator de cache). Upload endurecido: anti zip-bomb/xml-bomb, sandbox de
parsing, `input_sanitizer` (reuso 100%). **DoD:** upload → storage → registro persistido;
fuzz/segurança de upload no CI.

### S-B.2 Parser SPED EFD-ICMS/IPI (Strategy; prioridade — maior demanda)
Parser TXT por bloco/registro, multi-versão de layout, normalização canônica, **no worker**.
Dataset de validação anonimizado. **DoD:** ≥95% de acurácia vs. 50 arquivos anonimizados;
relatório de importação com correlation-id.

### S-B.3 Parser EFD-Contribuições + Parser XML (NF-e/CT-e/NFS-e)
EFD-Contribuições (entrada do PER/DCOMP) + XML com validação XSD (Adapter por tipo). **DoD:**
ambos normalizam ao canônico; schemas XSD versionados.

### S-B.4 Parser PDF (DARF/guias) + Cruzamento entre arquivos
PDF por layout (Strategy, OCR opcional) + reconciliação SPED × XML × guias. **DoD:** divergências
(totais, documentos faltantes) sinalizadas em relatório.

## 7. BLOCO C — Motor de Apuração & Regras (Pilar 2)

### S-C.1 Rules Engine declarativo (YAML por UF/obrigação)
Validações CFOP/CST/alíquota/totais via **Decorator**; **reusa `weighted_voting`** para consenso
de validadores (`FiscalValidator`). **DoD:** regras carregadas por UF sem redeploy; 1ª bateria de
inconsistências sobre dados importados.

### S-C.2 Mapa de Apuração ICMS/PIS/COFINS (modelo minimalista primeiro)
Visão cronológica débito/crédito/saldo; apuração mensal consolidada por tributo. **DoD:** apuração
ICMS/PIS/COFINS conferida contra casos-teste oficiais.

### S-C.3 Regras de Inconsistência (bateria ampla) + Edição em Lote
Zerados indevidos, alíquota incorreta, divergências de totais; correção em lote transacional.
**DoD:** início da suíte de **regressão tributária (200+ cenários)** derivada de erros reais.

## 8. BLOCO D — Retificação & Editor (Pilar 3)

### S-D.1 Editor estruturado com validação em tempo real + rollback
Edição de registros com validação streaming; **reusa HITL/progressive_autonomy** para aprovação;
**ledger fiscal** (UF/período/obrigação). **DoD:** editar→validar→aprovar→gerar versão corrigida,
totalmente reversível; trilha no ledger.

### S-D.2 Retificação SPED ponta-a-ponta
Comparação antes/depois, nota de correção, nova versão do arquivo. **DoD:** retificação
EFD-ICMS/IPI validada contra layout oficial.

## 9. BLOCO E — Camada Analítica (Pilar 5)

### S-E.1 Dashboards fiscais + KPIs
Reusa `intelligence_endpoints`/Grafana + telas React. ≥5 gráficos (apuração, auditoria,
anomalias). **DoD:** dashboard de apuração e auditoria provisionado; detecção de anomalia básica.

### S-E.2 Relatórios premium + SQL Workbench seguro
Workbench de consultas **parametrizadas/sandbox** (RBAC, read-only, sem SQL livre destrutivo) +
relatórios exportáveis. **DoD:** relatório premium exportável; workbench bloqueia DDL/DML perigoso.

## 10. BLOCO F — Geração & Transmissão Oficial (capstone Onda 2 — prova federal PER/DCOMP)

### S-F.1 Cofre de credenciais & certificado digital A1/A3
Evolui `credentials.py` → `CredentialProvider` com **vault**; assinatura digital; ambiente de
**homologação**. Segurança: certificado **nunca** em repo/env/imagem (volume/secret cifrado).
**DoD:** assinar payload de teste em homologação; rotação de credencial; RBAC de acesso ao vault.

### S-F.2 Gerador PER/DCOMP (Factory) + validação de layout
Gera ficha PER/DCOMP a partir da apuração/EFD-Contribuições; pré-validação (sintática/semântica) e
pós-validação contra layout oficial. **DoD:** ficha gerada e validada; casos de restituição/
compensação cobertos.

### S-F.3 Transmissão real e-CAC (homologação) + acompanhamento
Cliente de webservice (Adapter) com **circuit breaker** (reuso); **Observer** para status
(webhook/dashboard/ledger). **DoD:** PER/DCOMP transmitido em **homologação** com protocolo;
status rastreado; falha de transmissão não corrompe estado (idempotência).

## 11. Faixas transversais (correm em paralelo aos blocos)

- **Segurança/LGPD:** AES-256 em repouso (column-level para CNPJ/valores), TLS 1.3; **RBAC 5
  papéis fiscais** (admin, auditor, perito, contador, cliente); LGPD (anonimização em datasets de
  teste, log de acesso, right-to-be-forgotten via ledger). Meta: 0 vulnerabilidade OWASP crítica.
- **Observabilidade:** spans por estágio SPED (import→parse→validate→calculate→generate); métricas
  volume MB/h, erro por tipo, profundidade de fila, cache hit; alertas SLA (processamento >5min/
  500MB, fila >100, taxa de erro >5%).
- **CI/CD:** evoluir os workflows existentes — lint (black/ruff + eslint), unit (80% módulos
  fiscais / 60% demais), integração com datasets SPED anonimizados, E2E Playwright, build
  multi-stage por container, smoke pós-deploy. Gate de cobertura sobe progressivamente.
- **Testes:** unit (regras isoladas) → integração (importar→validar→gerar) → E2E (Playwright) →
  **regressão tributária 200+ cenários** (rede anti-regressão fiscal).

## 12. Sequenciamento, caminho crítico e riscos

**Caminho crítico:** S-0.1 (Postgres) → S-0.5 (worker/storage) → S-B.1/B.2 (canônico + parser
SPED) → S-C.2 (apuração) → S-F.2/F.3 (PER/DCOMP + transmissão). Atraso em ETL/parser paralisa
B→F. **Mitigações:** paralelizar parsers (Strategy isola); apuração minimalista ICMS/PIS/COFINS
antes de IPI; editor com log reversível; vault e webservice de F começam por homologação.

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Parser SPED/ETL atrasa | Média | Crítico | 1ª prioridade pós-fundação; paralelizar por layout; MVP ICMS/PIS/COFINS |
| Layout oficial muda | Alta | Médio | Template/parser parametrizável; versão de layout sem redeploy |
| Transmissão real (cert/homolog.) | Média | Alto | Só homologação na Onda 2; idempotência; circuit breaker; Observer de status |
| Inconsistência entre módulos | Média | Alto | Schema versionado; contrato no manifesto; Repository único |
| Volume SPED 500MB | Média | Médio | Worker Celery dedicado; batch; particionar por UF/período; storage MinIO |
| Segurança certificado digital | Baixa | Crítico | Vault; nunca em repo/env/imagem; RBAC; rotação; sandbox de assinatura |

## 13. KPIs de saída da Onda 2 (Definition of Done do programa)

Importação EFD-ICMS/IPI e EFD-Contribuições funcional (≥95% acurácia); mapa de apuração
ICMS/PIS/COFINS; editor com rollback; ≥5 dashboards; **PER/DCOMP gerado, validado e transmitido em
homologação**; cobertura ≥80% nos módulos fiscais; 0 OWASP crítica; **0 regressão na Onda 1**;
p95 da API ≤ ~250ms; ≥3-4 módulos comerciais registráveis/licenciáveis no Core.

## 14. Onda 3 (esboço — reusa 100% o padrão do Bloco F)

CAT42-SP + e-CredAc (SEFAZ-SP/SIPET, template engine + transmissão); obrigações estaduais
parametrizáveis por UF (DRCST-SC, ADRC-PR, DPRST-BA, ACRST-MS); Crédito Tributário (levantamento +
composição documental); PER/DCOMP estendido (PGDAS, PGFN); NCM/classificador; Recuperação Judicial.
Cada nova obrigação = `Factory` + `Decorator` de validação + entrada no vault + Adapter de
webservice — **sem mexer no Core, no orquestrador ou na governança.** Modelo comercial:
pay-per-use para obrigações estaduais sazonais; pacotes verticais (Advocacia, Contador
Tributarista, Empresa) e à la carte por módulo licenciado.

## 15. Verificação ponta-a-ponta do programa

```bash
# Fundação
alembic upgrade head && docker compose up -d postgres redis minio agent-system worker
docker compose exec agent-system curl -s localhost:8000/core/registry/modules -H "Authorization: Bearer $T"
# Ingestão→Apuração (worker)
#  upload EFD-ICMS/IPI → job status → registros canônicos → mapa de apuração ICMS conferido
pytest tests/fiscal -q            # unit + integração fiscal (gate 80%)
pytest tests/regression_fiscal -q # 200+ cenários
# Capstone federal
#  EFD-Contribuições → apuração → PER/DCOMP gerado → validado layout → transmitido (HOMOLOGAÇÃO) → protocolo
pytest tests/ -q                  # regressão total: Onda 1 verde + Onda 2 verde
black --check src/ tests/ && bandit -r src/ --severity-level high
```
