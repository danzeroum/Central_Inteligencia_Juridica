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
  ocorreu em #107/#108/#111); nesse caso a validação por log **continua obrigatória** logo
  após o merge. Master vermelho → hotfix imediato vira o sprint atual.
- **Zero débito silencioso.** Nada é adiado sem registro: todo deferral entra na seção 2
  com sprint-alvo. Placeholder em código só com marcador `TODO(S-X.Y):` + entrada na
  tabela. Placeholder sem registro = bloqueio de merge.
- **Disciplina de contagem.** O PR declara quantos testes novos traz; a suíte total nunca
  regride. Baseline atual (master `844d8b1`): **árvore completa local sem DB 1426 passed /
  20 skipped** (unit+integração 1276/20 + 111 `regression_fiscal` + 39 `datasus`);
  **CI integração 357 passed / 7 skipped** (run 27393417155).
- **Branch por sprint.** O dev inicia cada sprint com a branch **resetada em
  `origin/master`** (`git fetch origin && git reset --hard origin/master`) — branches
  longevas com histórico próprio do doc geram conflito recorrente (aconteceu em #103 e #105).
- **Prova por log.** Funcionalidade que depende de infra (DB, broker, storage) só conta
  como verificada com o teste **rodando no CI** (PASSED no log do job) — skip gracioso
  local é aceitável, skip silencioso no CI não (lição do DT-09).
- **"PASSED no CI" só com run_id.** O corpo do PR nunca afirma resultado de CI que ainda
  não aconteceu. Números locais medidos **sem** infra dizem isso explicitamente
  ("local sem DB"). Lição do S-C.3 (regressão `DetachedInstanceError` invisível sem
  Postgres); cumprido corretamente pelo PR #111. Antes de pedir aval, rode os E2E com
  Postgres local (`docker run -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:15-alpine`
  + `DATABASE_URL`) ou aguarde o run e cite o run_id.
- **Um sprint por PR, uma trilha por PR.** Trabalho fora do escopo sancionado não pega
  carona em PR de sprint (lição do SAUDE-01: empilhado no PR fiscal, derrubou o gate de
  segurança do sprint inteiro). Iniciativa nova → registrar, pedir sanção do stakeholder,
  trilha própria (seção 6).
- **Teste fio-de-ouro.** `tests/integration/test_golden_thread.py` percorre o pipeline
  inteiro via API. Ele **nunca** é removido ou enfraquecido — cada sprint o **estende**
  (C.3: ciclo detectar→corrigir→reapurar ✓; C.4: apuração com ajuste E111 + regime/UF ✓;
  C.5: ICMS-ST; D: retificação; F: PER/DCOMP). É a prova permanente de que as
  funcionalidades estão integradas de ponta a ponta, não só testadas em unidade.

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
| DT-10 | Workflows `ci-on-pr.yml`/`ci-on-push.yml` com papel não documentado | S-C.2 | S-C.3 (headers) | **resolvido na letra; superado por DT-12** |
| DT-11 | Conexões async morrendo com transação aberta (`unexpected EOF ... open transaction` + `Connection._cancel` no log do Postgres do CI). Dois fenômenos sob o mesmo sintoma: (a) regressão de request — rollback expirava instâncias ORM lidas fora do `with` (4 endpoints; corrigido no S-C.3, commits `ba00dfb..7f29b25`); (b) conexões asyncpg presas a event loops por teste, morrendo no exit do processo | S-C.2.1 (exposto) | S-C.4: `poolclass=NullPool` quando `ENVIRONMENT=test` (`src/db/engine.py`) | **resolvido** — prova por log: run 27393417155 com **zero** `open transaction` e **zero** `Connection._cancel`. Regra de código permanece: nenhum acesso a atributo ORM após `async with get_async_session()` fechar |
| DT-12 | Workflows zumbis `ci-on-pr.yml`/`ci-on-push.yml` em *startup failure* em todo evento (0 jobs) desde antes da Onda 2 — ❌ permanente em master | pré-Onda 2 | S-C.4: removidos (PR #111); `ci.yml` é o gate único | **resolvido** |
| DT-13 | `cd-deploy.yml` falhava em todo push a master (infra/secrets inexistentes) | pré-Onda 2 | Gateado em `workflow_dispatch` (PR #110) | **resolvido** |
| DT-14 | **Convenção COD_AJ_APUR incorreta no E111**: a implementação classifica débito/crédito pelo **3º caractere** com valores `1`/`2`; o leiaute real (tabela 5.1.1 do Guia Prático EFD ICMS/IPI) usa o **4º caractere**: `0`=outros débitos, `1`=estorno de créditos, `2`=outros créditos, `3`=estorno de débitos, `4`=deduções, `5`=débitos especiais. Com códigos reais (ex.: `SP000207`) os ajustes caem em `avisos_ajuste` e **ficam fora do saldo**. Testes verdes porque as fixtures usam a convenção interna (consistente, porém infiel ao leiaute) | **spec do coordenador** (handoff S-C.4); detectado na leitura dirigida pós-merge #111 | **S-C.5 Tarefa 1** — decodificação pelo 4º caractere + fixtures/cenários com códigos reais | **aberto** |

## 3. SPRINT ATUAL — S-C.5 "ICMS-ST + IPI + correção COD_AJ_APUR"

**Objetivo:** completar a apuração para os tributos/registros que ficaram fora do S-C.4
(ICMS-ST e IPI — os `TODO(S-C.5)` de `apuracao.py`) e corrigir a decodificação do E111
(DT-14) **antes** que qualquer arquivo real seja processado com ajustes ignorados no saldo.

### Tarefa 1 — DT-14: decodificação real do COD_AJ_APUR (fazer PRIMEIRO)

1. Em `calcular_icms` (`src/fiscal/apuracao.py`), trocar a natureza do ajuste do 3º para
   o **4º caractere** do `cod_aj_apur`, conforme tabela 5.1.1:
   - `0` (outros débitos) e `1` (estorno de créditos) → `ajustes_debito`
   - `2` (outros créditos) e `3` (estorno de débitos) → `ajustes_credito`
   - `4` (deduções) → abate do saldo devedor **após** a apuração; detalhar em `detalhes`
   - `5` (débitos especiais) → **fora** do saldo; acumular em `detalhes["debitos_especiais"]`
   - qualquer outro valor ou código curto → `AVISO` (comportamento atual preservado)
2. **Fixtures e cenários migram para códigos reais** (ex.: `SP000207`, `SP010102`,
   `RJ020303`). A edição dos cenários E111 existentes é **sancionada por este DT-14**
   (exceção registrada à regra "regressão nunca enfraquece": trocar código fictício por
   real fortalece a suíte). ≥6 casos: débito(0), estorno crédito(1), crédito(2), estorno
   débito(3), dedução(4), débito especial(5).

### Tarefa 2 — ICMS-ST (E300..E316)

3. Apuração ST: E310 é o espelho do E110 para substituição tributária (débitos/créditos
   ST, confronto computado × declarado, mesmo padrão de `DivergenciaApuracao`).
   `ItemApuracao` com `tributo="ICMS-ST"`; quando houver UF de destino (E300), detalhar
   por UF em `detalhes`. **≥5 casos-teste com conta manual** (devedor, credor, divergência
   E310, múltiplas UFs, sem E300 → ausente).
4. Regras de detecção mínimas no YAML: ST negativo, E310 órfão de E300 (ERRO).

### Tarefa 3 — IPI (E520..E530)

5. Apuração IPI a partir do E520 (débitos/créditos/saldo), confronto computado ×
   declarado; E530 ajustes seguem a MESMA disciplina de natureza por caractere da tabela
   correspondente (não repetir o DT-14). **≥4 casos com conta manual.**

### Tarefa 4 — Regressão e fio-de-ouro

6. Cenários novos (ST, IPI, ajustes reais) em `tests/regression_fiscal/scenarios/`:
   **≥140 total** (hoje 111).
7. **Fio-de-ouro estende:** fixture EFD com C100+ST e E300/E310 → upload → apuração via
   API retorna item `ICMS-ST` com saldo da conta manual. Os E2E existentes (ciclo +
   E111+regime) permanecem intactos — atenção: o E2E do E111 muda o código da fixture
   para um real (DT-14), mantendo a mesma conta (100+50=150).

### DoD do S-C.5 (o coordenador roda exatamente isto)

```bash
black --check src/ tests/
python -m pytest tests/unit/ tests/integration/ -q     # ≥ 1276/20 local sem DB, 0 falhas
python -m pytest tests/regression_fiscal/ -q           # ≥140 cenários verdes
grep -rn "TODO(S-C.5)" src/                            # 0 (feito ou re-escopado com registro)
# Com Postgres local: pytest tests/integration/test_golden_thread.py -k E2E -v → TODOS PASSED
# No CI (prova por log, run_id citado no PR):
#   - E2E novo (ICMS-ST) PASSED + E2E E111 com código REAL passed
#   - log do Postgres: zero 'open transaction', zero 'Connection._cancel' (não regredir DT-11)
```

- [ ] DT-14 corrigido: 4º caractere, naturezas 0..5, fixtures com códigos reais
- [ ] ICMS-ST com confronto E310 e ≥5 contas manuais; IPI com ≥4
- [ ] ≥140 cenários de regressão
- [ ] Fio-de-ouro com ST; E2E E111 migrado para código real
- [ ] PR declara nº exato de testes novos; nenhuma afirmação de CI sem run_id

---

## 3-A. Sprints encerrados (histórico)

| Sprint | PR | Encerramento (prova) |
|---|---|---|
| S-0.1..S-0.5, S-A, S-B.1..B.4, S-C.1 | #93–#101 | Validados retroativamente (suítes 821→1188, zero regressão) |
| S-C.2 "Fio de Ouro + Apuração" | #103 | Mergeado com DT-07/08 carregados; encerrado junto com S-C.2.1 |
| S-C.2.1 "E2E real + ADR-016" | #105 | **ENCERRADO** — log run 27362773921: 4 E2E + 7 `postgres_ledger` PASSED (1ª vez no CI), integração 348/7. Expôs e corrigiu bug real de transação e o DT-09 |
| S-C.3 "Regras YAML/UF + Lote + Regressão" | #107 | **ENCERRADO** — 30+6 regras, lote com `dry_run`, 59 cenários, ciclo detectar→corrigir→reapurar. Prova por log reprovou a 1ª tentativa (run 27385154803: 5 E2E failed, `DetachedInstanceError`); corrigida; run final 27387068598: 349/7, 5 E2E PASSED. DT-11 ficou parcial (fechado no S-C.4) |
| S-C.4 "Apuração estendida + regime no upload + saneamento CI" | #111 | **ENCERRADO** — E111/E112/E113 no saldo, cumulativo M100/M500, créditos M400/M405/M800; regime/UF do upload à apuração (fim do hardcode); DT-11 fechado por log (run 27393417155: **zero** `open transaction`/`Connection._cancel`), DT-12 (zumbis removidos), DT-13 (#110). 6/6 E2E PASSED nominais; integração 357/7; local 1426/20; regressão 111. ST/IPI re-escopados (`TODO(S-C.5)`). Mergeado antes do aval; validação pós-merge aprovou **com ressalva DT-14** (convenção COD_AJ_APUR — origem: spec do coordenador) |

## 4. Fila após o S-C.5 (deltas sobre o roadmap — não executar ainda)

- **S-D.1/S-D.2 — Editor + Retificação.** Reusa HITL/progressive_autonomy para aprovação;
  toda edição vira evento no ledger (UF/período/obrigação); geração do arquivo retificado
  a partir dos registros canônicos editados; fio-de-ouro ganha editar→aprovar→regerar.
- **S-E.1/S-E.2 — Analítica.** Dashboards sobre apuração/achados; workbench read-only
  com consultas parametrizadas (RBAC).
- **S-F.1..F.3 — PER/DCOMP capstone.** Vault → gerador → transmissão homologação; o
  fio-de-ouro vira o teste do capstone. A apuração completa (C.4+C.5) é insumo direto.

## 5. Como o coordenador valida cada PR

1. Worktree limpo no head do PR; `black --check`; suíte completa; fio-de-ouro.
2. Auditoria do DoD item a item contra as evidências do corpo do PR.
3. Auditoria da tabela de débitos (seção 2): nenhum `TODO(S-…)` órfão
   (`grep -rn "TODO(S-" src/` deve bater com a tabela).
4. Leitura dirigida do diff (segurança: paths de upload, SQL, RBAC; LGPD: mascaramento;
   **fidelidade a leiaute SPED** — lição DT-14).
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
| **SAUDE-01 "Sentinela Respiratória"** — módulo `src/datasus/` (fetcher FTP DATASUS, descompressão DBC→DBF, leitor SIH-RD com polars), indicador `saude.resp.internacoes_j` (CID J00–J99, agregação k≥5), 39 testes (fixtures locais, sem rede). Governança: `ADR-017-ftp-datasus-plain.md` (risco FTP aceito; `# nosec B402/B321` justificado; revisão se DATASUS oferecer HTTPS) + entrada `internacoes_respiratorias` em `data_sources.yaml` (k=5, exclusão explícita de CPF_AUT/GESTOR_CPF/NASC) | #108 | **ENCERRADO** — run 27386928110 7/7; mergeado (`9711c4f`). Histórico: nasceu não-sancionado dentro do PR fiscal #107 e derrubou o gate bandit do sprint (lição na seção 1) |
| SAUDE-02 (não especificado) | — | **não sancionado** — aguarda demanda do stakeholder (candidatos: espelho HTTPS, agendamento de coleta, exposição do indicador na API/dashboard) |
