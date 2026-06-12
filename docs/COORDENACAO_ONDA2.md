# Coordenação Onda 2 — Protocolo, Débitos e Sprint Atual

> Documento operacional da coordenação técnica. O plano-mestre é `docs/ROADMAP_ONDA2.md`;
> este arquivo diz **o que executar agora**, **como cada entrega é verificada** e **onde
> estão os débitos técnicos**. Atualizado pelo coordenador a cada sprint. **Dev: leia a
> seção 3 e execute. Em dúvida entre este doc e o roadmap, este doc prevalece** (ele
> incorpora decisões tomadas depois do roadmap).

## 1. Protocolo de trabalho

- **Papéis.** Dev implementa; coordenador especifica, valida ponta-a-ponta e aprova merge.
- **1 PR por sprint**, título `Bloco X (S-X.Y): <resumo>`. O corpo do PR lista cada item do
  DoD com a **evidência** (nome do teste, endpoint, caminho da fixture). Sem evidência, o
  item conta como não entregue.
- **Validação antes do merge.** O coordenador roda em worktree limpo: `black --check`,
  suíte completa (`pytest tests/unit tests/integration`), os testes E2E do sprint e a
  auditoria do registro de débitos. Só então o PR é mergeado.
- **Validação pós-merge.** O stakeholder pode mergear antes do aval (prerrogativa dele —
  ocorreu nos PRs #107/#108); nesse caso a validação por log **continua obrigatória** logo
  após o merge. Master vermelho → hotfix imediato vira o sprint atual.
- **Zero débito silencioso.** Nada é adiado sem registro: todo deferral entra na seção 2
  com sprint-alvo. Placeholder em código só com marcador `TODO(S-X.Y):` + entrada na
  tabela. Placeholder sem registro = bloqueio de merge.
- **Disciplina de contagem.** O PR declara quantos testes novos traz; a suíte total nunca
  regride (baseline atual: **local sem DB 1341 passed / 19 skipped** — inclui 59
  `regression_fiscal` e 39 `datasus`; **CI integração 349 passed / 7 skipped** — run
  27387068598, master `b61281f`).
- **Branch por sprint.** O dev inicia cada sprint com a branch **resetada em
  `origin/master`** (`git fetch origin && git reset --hard origin/master`) — branches
  longevas com histórico próprio do doc geram conflito recorrente (aconteceu em #103 e #105).
- **Prova por log.** Funcionalidade que depende de infra (DB, broker, storage) só conta
  como verificada com o teste **rodando no CI** (PASSED no log do job) — skip gracioso
  local é aceitável, skip silencioso no CI não (lição do DT-09).
- **"PASSED no CI" só com run_id.** O corpo do PR nunca afirma resultado de CI que ainda
  não aconteceu. Números locais medidos **sem** infra dizem isso explicitamente
  ("local sem DB"). Lição do S-C.3: o PR declarou o ciclo E2E "PASSED no CI"
  antecipadamente; o primeiro run real reprovou os 5 E2E (regressão DetachedInstanceError
  que só aparece com Postgres). Antes de pedir aval, rode os E2E com Postgres local
  (`docker run -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:15-alpine` + `DATABASE_URL`)
  ou aguarde o run e cite o run_id.
- **Um sprint por PR, uma trilha por PR.** Trabalho fora do escopo sancionado não pega
  carona em PR de sprint (lição do SAUDE-01: empilhado no PR fiscal, derrubou o gate de
  segurança do sprint inteiro). Iniciativa nova → registrar, pedir sanção do stakeholder,
  trilha própria (seção 6).
- **Teste fio-de-ouro.** `tests/integration/test_golden_thread.py` percorre o pipeline
  inteiro via API. Ele **nunca** é removido ou enfraquecido — cada sprint o **estende**
  (C.3: ciclo detectar→corrigir→reapurar ✓; C.4: apuração com ajustes; D: retificação;
  F: PER/DCOMP). É a prova permanente de que as funcionalidades estão integradas de ponta
  a ponta, não só testadas em unidade.

## 2. Registro de débitos técnicos

| ID | Descrição | Origem | Resolução | Status |
|---|---|---|---|---|
| DT-01 | `RuntimeWarning` coroutine em `hitl_queue.py` | Onda 1 | S-C.2 | **resolvido** (PR S-C.2) |
| DT-02 | 5 warnings eslint + CI sem `--max-warnings 0` | Onda 1/#83 | S-C.2 | **resolvido** (PR S-C.2) |
| DT-03 | `process_sped_file` placeholder | S-0.5 | S-C.2 Parte A | **resolvido** (PR S-C.2) |
| DT-04 | Decisões do Bloco C sem ADR | S-C.1 | S-C.2 | **resolvido** (PR S-C.2) |
| DT-05 | Pipeline desconectado (upload não dispara parsing) | S-B.1..C.1 | S-C.2 + prova S-C.2.1 | **resolvido** — log run 27362773921 |
| DT-06 | Regras fiscais hardcoded; YAML por UF pendente | S-C.1 | S-C.3 (RuleLoader + SP/RJ) | **resolvido** (PR #107) |
| DT-07 | "Fio-de-ouro" não testava o fio | S-C.2 (#103) | S-C.2.1 | **resolvido** (PR S-C.2.1) |
| DT-08 | ADR-001 duplicado | S-C.2 (#103) | S-C.2.1 (→ADR-016) | **resolvido** (PR S-C.2.1) |
| DT-09 | `DATABASE_URL` ausente nos steps de pytest do `ci.yml` → skip silencioso | S-C.2.1 (exposto) | S-C.2.1 | **resolvido** (PR S-C.2.1) |
| DT-10 | Workflows `ci-on-pr.yml`/`ci-on-push.yml` com papel não documentado | S-C.2 | S-C.3 (headers) | **resolvido na letra, superado por DT-12** — a opção fraca (documentar) foi escolhida, mas os arquivos nunca executaram; os headers descrevem comportamento que não existe |
| DT-11 | Conexões async morrem com transação aberta: log do Postgres no CI com `unexpected EOF ... open transaction` + warnings `Connection._cancel was never awaited` | S-C.2.1 (exposto) | S-C.3 → **reaberto p/ S-C.4** | **parcial** — ver nota DT-11 abaixo |
| DT-12 | **Workflows zumbis**: `ci-on-pr.yml` e `ci-on-push.yml` sofrem *startup failure* em todo evento (run criado com 0 jobs e o *path* como nome — ex.: run 27388419543); nenhum job deles aparece nos check_runs de **nenhum** PR (#103–#108) nem push desde antes da Onda 2. Ruído ❌ permanente no histórico de master que mascara falha real. Causa exata do não-carregamento não diagnosticada (YAML aparenta válido); irrelevante se a resolução for remoção | pré-Onda 2 (diagnosticado no encerramento do S-C.3) | **S-C.4 higiene: remover ambos** — `ci.yml` já é o gate completo (full suite + Postgres + Docker + frontend, push e PR). Antes de remover, conferir required checks da branch protection | **aberto** |
| DT-13 | `cd-deploy.yml` falha em todo push a master (infra/secrets de staging inexistentes) — segundo ❌ permanente | pré-Onda 2 (diagnosticado idem) | **S-C.4 higiene**: condicionar a `workflow_dispatch` (ou checagem de secret) até existir infra de deploy (Bloco F/G) | **aberto** |

**Nota DT-11 (reaberto com novo escopo).** O S-C.3 teve dois fenômenos distintos sob o
mesmo sintoma:

1. **Regressão introduzida e corrigida no próprio PR**: o `rollback()` no `finally` de
   `get_async_session()` expira instâncias ORM; 4 endpoints liam atributos **após** o
   bloco (`get_escrituracao_status`, `get_escrituracao_achados`, `listar_apuracoes`,
   `listar_registros`) → `DetachedInstanceError` em 5 E2E (run 27385154803). Corrigido
   materializando a resposta **dentro** do `with` (commits `ba00dfb`/`bc1eaec`/`7f29b25`);
   run final 27387068598: 5 E2E PASSED. **Regra de código:** nenhum acesso a atributo ORM
   depois que `async with get_async_session()` fecha.
2. **O fenômeno original persiste**: mesmo no run verde, o log do Postgres tem **7×**
   `unexpected EOF ... open transaction`, todos no **exit do processo de teste**
   (00:52:31, após o sumário do pytest), junto de `coroutine 'Connection._cancel' was
   never awaited`. Diagnóstico provável: conexões asyncpg presas a event loops de teste já
   fechados (pytest-asyncio cria loop por teste; engine global compartilha pool) — morrem
   no exit sem rollback/close gracioso. **Não** é o caminho de request de produção (loop
   único + rollback do item 1). Resolução S-C.4: higiene de teardown — `await
   engine.dispose()` em fixture de sessão de teste, ou `poolclass=NullPool` quando
   `ENVIRONMENT=test`. Critério inalterado: log do Postgres no CI **sem** `open
   transaction` e **zero** warnings `Connection._cancel`.

## 3. SPRINT ATUAL — S-C.4 "Apuração estendida + regime no upload + saneamento CI"

**Objetivo:** a apuração deixa de cobrir só o caso básico e passa a tratar **ajustes e
regimes** — pré-requisito direto do PER/DCOMP (Bloco F). O upload passa a carregar
metadados fiscais reais (regime/UF) em vez de hardcode. A casa de CI fica limpa: master
sem ❌ permanente.

### Tarefa 1 — Apuração estendida (fecha os `TODO(S-C.4)` de `apuracao.py`)

1. **Ajustes ICMS (E111/E112/E113):** débitos/estornos/créditos adicionais entram no
   saldo (`saldo = débitos − créditos + ajustes_débito − ajustes_crédito − saldo_ant`);
   E112/E113 como detalhamento vinculado. ≥5 casos-teste com conta manual (ajuste a
   débito, a crédito, múltiplos, código inválido → AVISO, E111 órfão de E110 → ERRO).
2. **Regime cumulativo PIS/COFINS (M100/M500 → bases; M200/M600 já confrontados):**
   detectar regime pelo bloco presente; cumulativo usa alíquotas 0,65%/3% — a alíquota
   vem do YAML de regras (sem hardcode novo). ≥4 casos-teste por tributo.
3. **Créditos PIS/COFINS (M400/M405, M800):** crédito básico abate o apurado; saldo
   credor persiste como `situacao=credor`. ≥4 casos-teste.
4. **ICMS-ST (E300..E316) e IPI (E520..E530):** **somente se couber no sprint**; caso
   contrário re-marcar `TODO(S-C.5)` + linha na fila (zero débito silencioso). Não
   sacrificar a qualidade dos itens 1–3 por estes.
5. **Regressão tributária:** cada cenário novo de apuração vira YAML em
   `tests/regression_fiscal/scenarios/` — meta intermediária **≥100 cenários** (hoje 59).

### Tarefa 2 — Regime/UF reais no upload (mata o hardcode de `upload.py:206`)

6. `POST /upload` (rota fiscal) aceita metadados opcionais `regime`
   (`lucro_real|lucro_presumido|simples`) e `uf` (sigla); persistidos em
   `EscrituracaoFiscal.details`; defaults atuais preservados com `AVISO` "regime assumido".
7. Pipeline e revalidação do lote usam o regime/UF persistidos (hoje
   `details.get("regime", "lucro_real")` — passa a ser fonte única). Regras UF (SP/RJ do
   S-C.3) **disparam via API** quando `uf` informada — teste de integração prova.

### Tarefa 3 — Higiene CI (fecha DT-11 reaberto, DT-12, DT-13)

8. **DT-11:** teardown de teste com `engine.dispose()` (fixture autouse de sessão) ou
   `NullPool` sob `ENVIRONMENT=test`. Critério (prova por log): Postgres do CI **sem**
   `open transaction`, **zero** `Connection._cancel`.
9. **DT-12:** remover `.github/workflows/ci-on-pr.yml` e `ci-on-push.yml`; antes,
   conferir em Settings → Branches se algum required check os referencia (se sim, avisar
   o stakeholder para ajustar a proteção — dev não tem esse acesso).
10. **DT-13:** `cd-deploy.yml` → trigger `workflow_dispatch` (com comentário de cabeçalho
    explicando: reativar em push quando houver infra), eliminando o ❌ de deploy em cada
    merge.

### Fio-de-ouro estende (obrigatório)

11. Fixture EFD ICMS **com E111 de ajuste a débito** → upload (com `regime`/`uf` via
    metadados) → apuração via API soma o ajuste no saldo (conta manual no teste) →
    listagem reflete. Ciclo do S-C.3 (detectar→corrigir→reapurar) permanece intacto.

### DoD do S-C.4 (o coordenador roda exatamente isto)

```bash
black --check src/ tests/
python -m pytest tests/unit/ tests/integration/ -q     # ≥ baseline 1341/19 local sem DB, 0 falhas
python -m pytest tests/regression_fiscal/ -q           # ≥100 cenários verdes
grep -rn "TODO(S-C.4)" src/                            # 0 ocorrências (feito ou re-escopado S-C.5)
ls .github/workflows/                                  # sem ci-on-pr.yml / ci-on-push.yml
# No CI (prova por log, com run_id citado no PR):
#   - E2E novo (ajuste E111 + regime via upload) PASSED
#   - log do Postgres sem 'open transaction'; zero 'Connection._cancel'
#   - push a master SEM nenhum run ❌ (zumbis removidos, CD gated)
```

- [ ] E111/E112/E113 no saldo ICMS com ≥5 casos de conta manual
- [ ] Cumulativo M100/M500 + créditos M400/M405/M800 com casos por tributo
- [ ] ICMS-ST/IPI entregues **ou** re-escopados com registro (S-C.5)
- [ ] `regime`/`uf` do upload à apuração (fim do hardcode); regra UF dispara via API
- [ ] ≥100 cenários de regressão
- [ ] DT-11 fechado por log; DT-12/DT-13: master push 100% verde
- [ ] PR declara nº exato de testes novos; nenhuma afirmação de CI sem run_id

---

## 3-A. Sprints encerrados (histórico)

| Sprint | PR | Encerramento (prova) |
|---|---|---|
| S-0.1..S-0.5, S-A, S-B.1..B.4, S-C.1 | #93–#101 | Validados retroativamente (suítes 821→1188, zero regressão) |
| S-C.2 "Fio de Ouro + Apuração" | #103 | Mergeado com DT-07/08 carregados; encerrado junto com S-C.2.1 |
| S-C.2.1 "E2E real + ADR-016" | #105 | **ENCERRADO** — log run 27362773921: 4 `TestGoldenThreadE2E` PASSED, 7 `postgres_ledger` PASSED (1ª vez no CI), integração 348/7. Expôs e corrigiu bug real de transação e o DT-09 |
| S-C.3 "Regras YAML/UF + Lote + Regressão" | #107 | **ENCERRADO** — 30 regras base + 3 SP + 3 RJ (equivalência: `test_fiscal_rules_engine.py` inalterado e verde); lote transacional com `dry_run`; 59 cenários de regressão; ciclo detectar→corrigir→reapurar no fio-de-ouro. A prova por log **reprovou a 1ª tentativa** (run 27385154803: 5 E2E failed por `DetachedInstanceError` — regressão do rollback DT-11 que o "verde local sem DB" não pegava); corrigida nos 4 endpoints; run final 27387068598: **349/7, 5 E2E PASSED nominalmente**. Mergeado pelo stakeholder antes do aval final; validação pós-merge confirmou. DT-11 segue **parcial** (EOFs no exit de teste — seção 2) |

## 4. Fila após o S-C.4 (deltas sobre o roadmap — não executar ainda)

- **S-C.5 (condicional)** — só se ICMS-ST/IPI forem re-escopados no S-C.4.
- **S-D.1/S-D.2 — Editor + Retificação.** Reusa HITL/progressive_autonomy para aprovação;
  toda edição vira evento no ledger (UF/período/obrigação); geração do arquivo retificado
  a partir dos registros canônicos editados; fio-de-ouro ganha editar→aprovar→regerar.
- **S-E.1/S-E.2 — Analítica.** Dashboards sobre apuração/achados; workbench read-only
  com consultas parametrizadas (RBAC).
- **S-F.1..F.3 — PER/DCOMP capstone.** Vault → gerador → transmissão homologação; o
  fio-de-ouro vira o teste do capstone. A apuração estendida do S-C.4 é insumo direto.

## 5. Como o coordenador valida cada PR

1. Worktree limpo no head do PR; `black --check`; suíte completa; fio-de-ouro.
2. Auditoria do DoD item a item contra as evidências do corpo do PR.
3. Auditoria da tabela de débitos (seção 2): nenhum `TODO(S-…)` órfão
   (`grep -rn "TODO(S-" src/` deve bater com a tabela).
4. Leitura dirigida do diff (segurança: paths de upload, SQL, RBAC; LGPD: mascaramento).
5. **Prova por log**: run_id do CI conferido (testes nominais + log de containers de infra).
6. Parecer no PR: aprovação ou itens bloqueantes. Merge só após parecer (ou validação
   pós-merge imediata, se o stakeholder mergear antes).

## 6. Trilha paralela — SAÚDE (sancionada pelo stakeholder em 2026-06-11)

Trilha independente do caminho fiscal (Onda 2). **Regras:** PR próprio por entrega (nunca
pegar carona em PR de sprint fiscal); governança LGPD obrigatória para cada fonte nova
(entrada em `config/governance/data_sources.yaml` + ADR da fonte); mesma disciplina de
DoD/prova por log.

| Entrega | PR | Estado |
|---|---|---|
| **SAUDE-01 "Sentinela Respiratória"** — módulo `src/datasus/` (fetcher FTP DATASUS, descompressão DBC→DBF, leitor SIH-RD com polars), indicador `saude.resp.internacoes_j` (CID J00–J99, agregação k≥5), 39 testes (fixtures locais, sem rede). Governança: `ADR-017-ftp-datasus-plain.md` (risco FTP aceito: fonte pública oficial sem TLS, leitura anônima, sem credenciais; `# nosec B402/B321` justificado na linha; condição de revisão se DATASUS oferecer HTTPS) + entrada `internacoes_respiratorias` em `data_sources.yaml` (k=5, colunas do produto, exclusão explícita de CPF_AUT/GESTOR_CPF/NASC) | #108 | **ENCERRADO** — run final 27386928110 7/7 verde; mergeado (`9711c4f`). Histórico: nasceu não-sancionado dentro do PR fiscal #107 e derrubou o gate bandit do sprint (lição na seção 1) |
| SAUDE-02 (não especificado) | — | **não sancionado** — aguarda demanda do stakeholder (candidatos: espelho HTTPS, agendamento de coleta, exposição do indicador na API/dashboard) |
