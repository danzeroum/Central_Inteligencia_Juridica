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
- **Zero débito silencioso.** Nada é adiado sem registro: todo deferral entra na seção 2
  com sprint-alvo. Placeholder em código só com marcador `TODO(S-X.Y):` + entrada na
  tabela. Placeholder sem registro = bloqueio de merge.
- **Disciplina de contagem.** O PR declara quantos testes novos traz; a suíte total nunca
  regride (baseline atual: **local sem DB 1243 passed / 18 skipped**; **CI integração
  348 passed / 7 skipped** — master `2269f00`).
- **Branch por sprint.** O dev inicia cada sprint com a branch **resetada em
  `origin/master`** (`git fetch origin && git reset --hard origin/master`) — branches
  longevas com histórico próprio do doc geram conflito recorrente (aconteceu em #103 e #105).
- **Prova por log.** Funcionalidade que depende de infra (DB, broker, storage) só conta
  como verificada com o teste **rodando no CI** (PASSED no log do job) — skip gracioso
  local é aceitável, skip silencioso no CI não (lição do DT-09).
- **Teste fio-de-ouro.** A partir deste sprint existe um teste de integração
  `tests/integration/test_golden_thread.py` que percorre o pipeline inteiro via API. Ele
  **nunca** é removido ou enfraquecido — cada sprint o **estende** (C.3: mais regras;
  D: retificação; F: PER/DCOMP). É a prova permanente de que as funcionalidades estão
  integradas de ponta a ponta, não só testadas em unidade.

## 2. Registro de débitos técnicos

| ID | Descrição | Origem | Resolução | Status |
|---|---|---|---|---|
| DT-01 | `RuntimeWarning: coroutine 'send_notification' was never awaited` em `src/hitl/hitl_queue.py:322` | Onda 1 | **S-C.2** (higiene) | **resolvido** (PR S-C.2) |
| DT-02 | 5 warnings eslint (unused vars em HitlScreen, TrainingScreen, Invest360Screen, JurisScreen) e CI sem `--max-warnings 0` | Onda 1/PR #83 | **S-C.2** (higiene) | **resolvido** (PR S-C.2) |
| DT-03 | `src/workers/tasks.py`: `process_sped_file` placeholder com mensagem desatualizada ("parser EFD em S-B.1") | S-0.5 | **S-C.2 Parte A** (vira pipeline real) | **resolvido** (PR S-C.2) |
| DT-04 | Decisões do Bloco C sem ADR (regras determinísticas sem `weighted_voting`; YAML/UF adiado) | S-C.1 | **S-C.2** (higiene — ADR curto) | **resolvido** (PR S-C.2) |
| DT-05 | **Pipeline desconectado**: upload (S-B.1) não dispara parsing; parsers B.2–B.4 e rules engine C.1 não são alcançáveis via API | S-B.1..C.1 | **S-C.2 Parte A** + prova E2E no S-C.2.1 | **resolvido** — confirmado por log do CI (run 27362773921): 4 `TestGoldenThreadE2E` PASSED |
| DT-06 | Regras fiscais hardcoded em Python; carregamento YAML por UF pendente | S-C.1 | **S-C.3** (RuleLoader YAML + uf/SP.yaml + uf/RJ.yaml) | **resolvido** (PR S-C.3) |
| DT-07 | **"Fio-de-ouro" não testa o fio**: `test_golden_thread.py` valida segmentos isolados (chama parser/engine in-process, duplicando `test_apuracao.py`) + smoke `404/503/422`; a cola `upload→persistência→consulta` não tem cobertura de integração. O `202` não prova persistência | S-C.2 (#103) | **S-C.2.1** | **resolvido** (PR S-C.2.1) |
| DT-08 | ADR duplicado: coexistem `ADR-001-performance-target.md` e `ADR-001-regras-fiscais-deterministas.md` | S-C.2 (#103) | **S-C.2.1** (renumerar p/ `ADR-016`) | **resolvido** (PR S-C.2.1) |
| DT-09 | `DATABASE_URL` não passada aos steps de `pytest` em `.github/workflows/ci.yml` → testes de banco skippavam silenciosamente desde S-0.1 (inclui 7 `postgres_ledger` e todos os futuros E2E) | S-C.2.1 (exposto) | **S-C.2.1** (fix no mesmo PR) | **resolvido** (PR S-C.2.1) |
| DT-10 | Workflows `ci-on-pr.yml`/`ci-on-push.yml` duplicados/desatualizados — intenção vs `ci.yml` principal não documentada | S-C.2 | **S-C.3** (documentados com cabeçalho explicando papel de cada workflow) | **resolvido** (PR S-C.3) |
| DT-11 | Sessões async não fecham limpo no caminho inline: log do Postgres no CI com 6× `unexpected EOF on client connection with an open transaction` + 2 warnings `coroutine 'Connection._cancel' was never awaited` (run 27362773921) | S-C.2.1 (exposto) | **S-C.3** — rollback explícito em `get_async_session()` quando `session.in_transaction()` | **resolvido** (PR S-C.3) |

## 3. SPRINT ATUAL — S-C.3 "Regras declarativas por UF + Edição em lote + Regressão tributária"

**Objetivo:** ampliar a malha de detecção com regras carregadas de **YAML por UF** (fecha
DT-06), permitir **corrigir em lote** o que foi detectado, e plantar a **suíte de regressão
tributária**. O fio-de-ouro ganha o ciclo completo: **detectar → corrigir → reapurar**.

### Tarefa 1 — RuleLoader YAML por UF (fecha DT-06)

1. `config/fiscal/rules/base.yaml` + `config/fiscal/rules/uf/SP.yaml` e `uf/RJ.yaml`.
   Schema declarativo **sem eval** (mini-DSL segura): `id`, `tipo_registro`, `campo`,
   `severidade`, `descricao`, `dica`, `regimes`, `uf` (opcional) e `check` com operadores
   enumerados (`negative`, `missing`, `gt_field`, `lt`, `gt`, `eq`, `ne`, `not_in`,
   `pct_divergence` …). YAML inválido → **falha explícita na carga** (nunca silêncio).
2. As **15 regras atuais migram** para `base.yaml`; `_build_rules()` passa a delegar ao
   loader. **Golden test de equivalência**: mesmos `id`s, mesmo comportamento — os testes
   existentes de `test_fiscal_rules_engine.py` continuam passando sem alteração.
3. API pública preservada e estendida: `get_rules_engine(regime, uf=None)` — sem `uf`,
   só regras base (compat total com S-C.2).
4. **Primeiras regras UF-dependentes (≥3):** alíquota interna fora da tabela da UF
   (ex.: SP 18%, RJ 20/22%) em C100/C170 → `AVISO` (interestadual: aceitar 4/7/12 quando
   CFOP 6xxx; documentar limitações no YAML). Tabela de alíquotas vive no YAML da UF —
   ajuste de alíquota = editar YAML, **sem redeploy** (DoD original do roadmap).

### Tarefa 2 — Bateria ampla de inconsistências (≥15 regras novas; total ≥30)

Zerados indevidos (CST tributada com `vl_icms=0`), coerência CFOP×`ind_oper` (CFOP 1xxx/2xxx
em saída e 5xxx/6xxx em entrada), `dt_doc` fora do período 0000, duplicidade de documento
(num+série+participante), contadores do bloco 9 vs contados, consistência base×alíquota do
M210/M610 (espelho PIS/COFINS). Cada regra com ≥2 testes (viola / não-viola).

### Tarefa 3 — Edição em lote transacional

5. `POST /api/v1/fiscal/escrituracoes/{id}/registros/lote` — body
   `{operacoes: [{registro_id, campos: {...}}], dry_run: bool}`.
   - `dry_run=true`: preview com diff + **revalidação simulada** (achados antes/depois),
     nada persiste.
   - `dry_run=false`: **transação única** (tudo-ou-nada), `FiscalAudit` + ledger (reuso),
     revalidação automática pós-commit, resposta com achados antes/depois.
   - Bloqueia se escrituração em `processando`; RBAC igual às rotas fiscais; identificadores
     mascarados na resposta (LGPD).
6. Edição é sobre os **registros canônicos** (não sobre o arquivo); regeneração de arquivo
   retificado fica no S-D.2 (não antecipar).

### Tarefa 4 — Seed da regressão tributária (meta 200+ até fim do Bloco E)

7. `tests/regression_fiscal/` com runner parametrizado lendo
   `tests/regression_fiscal/scenarios/*.yaml` — cada cenário: nome, registros inline,
   `regime`/`uf`, esperado (`regra_ids` violadas e/ou apuração esperada). **≥50 cenários**
   nesta entrega (30 regras × viola/ok + apurações). Roda na suíte normal, rápido, sem DB.

### Higiene do sprint (fecha DT-10 e DT-11; re-escopa TODOs)

8. **DT-10:** remover `ci-on-pr.yml` e `ci-on-push.yml` (gate único = `ci.yml`) ou
   documentar no próprio YAML por que ficam; conferir required checks da branch protection
   antes de remover.
9. **DT-11:** fechar sessões/transações do caminho inline — critério: log do Postgres no
   CI **sem** `unexpected EOF ... open transaction` e sem warnings `Connection._cancel`.
10. Os marcadores `TODO(S-C.3)` em `apuracao.py` (E111/ICMS-ST/IPI/M100/M500/créditos)
    **não** entram neste sprint: re-marcar como `TODO(S-C.4)` (apuração estendida — ver
    fila) para manter a tabela coerente com o código.

### Fio-de-ouro estende (obrigatório): ciclo detectar→corrigir→reapurar

11. Novo E2E em `TestGoldenThreadE2E`: upload de fixture **com erro detectável** → achados
    com `ERRO` → `POST /registros/lote` corrigindo (dry_run e depois real) → revalidação
    mostra 0 erros → `POST /apuracao` sem divergência E110. Tudo via HTTP, com DB (mesmo
    guard do S-C.2.1).

### DoD do S-C.3 (o coordenador roda exatamente isto)

```bash
black --check src/ tests/
python -m pytest tests/unit/ tests/integration/ -q     # baseline local 1243/18 + novos, 0 falhas
python -m pytest tests/regression_fiscal/ -q           # ≥50 cenários verdes
grep -rn "TODO(S-C.3)" src/                            # 0 ocorrências (re-escopados p/ S-C.4)
ls .github/workflows/                                  # DT-10 decidido (removidos ou documentados)
# No CI (prova por log): E2E do ciclo completo PASSED; log do Postgres sem 'open transaction'
```

- [ ] 15 regras migradas p/ YAML com golden test de equivalência; YAML inválido falha startup
- [ ] ≥3 regras UF (SP+RJ) — alíquota editável sem redeploy
- [ ] ≥30 regras totais, cada uma com par viola/não-viola
- [ ] Lote: dry_run + transacional + audit/ledger + revalidação; bloqueio em `processando`
- [ ] E2E ciclo detectar→corrigir→reapurar PASSED no CI (prova por log)
- [ ] ≥50 cenários de regressão; DT-06/10/11 fechados na tabela; CI 6/6 verde
- [ ] Estimativa de testes novos: ~80–110 (PR declara o número exato)

---

## 3-A. Sprints encerrados (histórico)

| Sprint | PR | Encerramento (prova) |
|---|---|---|
| S-0.1..S-0.5, S-A, S-B.1..B.4, S-C.1 | #93–#101 | Validados retroativamente (suítes 821→1188, zero regressão) |
| S-C.2 "Fio de Ouro + Apuração" | #103 | Mergeado com DT-07/08 carregados; encerrado junto com S-C.2.1 |
| S-C.2.1 "E2E real + ADR-016" | #105 | **ENCERRADO** — log run 27362773921: 4 `TestGoldenThreadE2E` PASSED, 7 `postgres_ledger` PASSED (1ª vez no CI), integração 348/7. Expôs e corrigiu bug real de transação (`session.begin()` único) e o DT-09 |

## 4. Fila após o S-C.3 (deltas sobre o roadmap — não executar ainda)

- **S-C.4 — Apuração estendida.** Os `TODO(S-C.4)` de `apuracao.py`: ajustes E111/E112/E113,
  ICMS-ST (E300+), IPI (E520+), regime cumulativo PIS/COFINS (M100/M500), créditos
  (M400/M405/M800). Mesmo padrão: casos-teste com conta manual + confronto declarado.
- **S-D.1/S-D.2 — Editor + Retificação.** Reusa HITL/progressive_autonomy existentes para
  aprovação; toda edição vira evento no ledger (UF/período/obrigação); geração do arquivo
  retificado a partir dos registros canônicos editados; fio-de-ouro ganha etapa
  editar→aprovar→regerar.
- **S-E.1/S-E.2 — Analítica.** Dashboards sobre as entidades de apuração/achados (que o
  S-C.2 cria); workbench só com consultas parametrizadas (RBAC, read-only).
- **S-F.1..F.3 — PER/DCOMP capstone.** Conforme roadmap (vault → gerador → transmissão
  homologação); o fio-de-ouro se torna o teste do capstone completo.

## 5. Como o coordenador valida cada PR

1. Worktree limpo no head do PR; `black --check`; suíte completa; fio-de-ouro.
2. Auditoria do DoD item a item contra as evidências do corpo do PR.
3. Auditoria da tabela de débitos (seção 2): nenhum `TODO(S-…)` órfão
   (`grep -rn "TODO(S-" src/` deve bater com a tabela).
4. Leitura dirigida do diff (segurança: paths de upload, SQL, RBAC; LGPD: mascaramento).
5. Parecer no PR: aprovação ou itens bloqueantes. Merge só após parecer.
