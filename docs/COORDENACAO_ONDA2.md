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
  regride. Baseline atual (branch `51a3b7c`, S-C.6 mergeado): **árvore completa local sem DB 1490 passed /
  21 skipped** (unit+integração 1299/21 + 152 `regression_fiscal` + 39 `datasus`);
  **CI integração 358 passed / 7 skipped** (run 27410841899).
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
  C.5: ICMS-ST ✓; C.6: ST via E200/E210 reais ✓; D: retificação; F: PER/DCOMP). É a prova
  permanente de que as
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
| DT-14 | **Convenção COD_AJ_APUR incorreta no E111**: a implementação classifica débito/crédito pelo **3º caractere** com valores `1`/`2`; o leiaute real (tabela 5.1.1 do Guia Prático EFD ICMS/IPI) usa o **4º caractere**: `0`=outros débitos, `1`=estorno de créditos, `2`=outros créditos, `3`=estorno de débitos, `4`=deduções, `5`=débitos especiais. Com códigos reais (ex.: `SP000207`) os ajustes caem em `avisos_ajuste` e **ficam fora do saldo**. Testes verdes porque as fixtures usam a convenção interna (consistente, porém infiel ao leiaute) | **spec do coordenador** (handoff S-C.4); detectado na leitura dirigida pós-merge #111 | S-C.5 Tarefa 1 — `_decode_aj_apur` pelo 4º caractere + fixtures/cenários com códigos reais | **resolvido** (PR #113) — 6 naturezas testadas; prova: run 27395640351, E2E E111 com `SP000207` PASSED |
| DT-15 | **Fidelidade de leiaute do Bloco E (além do E111)** — 5 itens da leitura dirigida do #113: (1) confronto ST apontado para **E300/E310**, mas no leiaute real ST é **E200/E210** (E300/E310 = DIFAL EC 87/15); (2) `_E310_CAMPOS` é espelho inventado do E110, não o leiaute real; (3) `_E520_CAMPOS` diverge do E520 real (`VL_SD_ANT_IPI, VL_DEB_IPI, VL_CRED_IPI, VL_OD_IPI, VL_OC_IPI, VL_SC_IPI, VL_SD_IPI`) — inclui `vl_icms_ressarc` inexistente e omite OD/OC/SC/SD, desalinhando posições em arquivo real; (4) `_E530_CAMPOS` sem `IND_AJ` (flag real débito/crédito do ajuste IPI) — 4º caractere **não se aplica** ao E530; (5) deduções (natureza 4) dentro da fórmula do saldo podem inverter para credor artificialmente. Tudo verde com fixtures internas; infiel a arquivos reais | itens 1–2: TODO original do S-C.2 + **spec do coordenador**; 3–5: implementação S-C.5; detectados na leitura dirigida pós-merge #113 | **S-C.6** (sprint curto, antes do Bloco D) | **resolvido** (branch `51a3b7c`, run 27410841899) — E200/E210 reais, E520/E530 fiéis ao leiaute, deduções só sobre devedor, regressão 142→152 |

## 3. PRÓXIMO SPRINT — aguardando especificação do coordenador

S-C.6 encerrado. Próximo passo natural é **S-D.1 — Editor + Retificação** (ver seção 4),
mas só inicia após sanção explícita do coordenador. Regras de DoD do S-C.6 em diante:
handler novo/alterado conferido contra o Guia Prático EFD ICMS/IPI, versão citada no header.

---

## 3-A. Sprints encerrados (histórico)

| Sprint | PR | Encerramento (prova) |
|---|---|---|
| S-0.1..S-0.5, S-A, S-B.1..B.4, S-C.1 | #93–#101 | Validados retroativamente (suítes 821→1188, zero regressão) |
| S-C.2 "Fio de Ouro + Apuração" | #103 | Mergeado com DT-07/08 carregados; encerrado junto com S-C.2.1 |
| S-C.2.1 "E2E real + ADR-016" | #105 | **ENCERRADO** — log run 27362773921: 4 E2E + 7 `postgres_ledger` PASSED (1ª vez no CI), integração 348/7. Expôs e corrigiu bug real de transação e o DT-09 |
| S-C.3 "Regras YAML/UF + Lote + Regressão" | #107 | **ENCERRADO** — 30+6 regras, lote com `dry_run`, 59 cenários, ciclo detectar→corrigir→reapurar. Prova por log reprovou a 1ª tentativa (run 27385154803: 5 E2E failed, `DetachedInstanceError`); corrigida; run final 27387068598: 349/7, 5 E2E PASSED. DT-11 ficou parcial (fechado no S-C.4) |
| S-C.4 "Apuração estendida + regime no upload + saneamento CI" | #111 | **ENCERRADO** — E111/E112/E113 no saldo, cumulativo M100/M500, créditos M400/M405/M800; regime/UF do upload à apuração (fim do hardcode); DT-11 fechado por log (run 27393417155: **zero** `open transaction`/`Connection._cancel`), DT-12 (zumbis removidos), DT-13 (#110). 6/6 E2E PASSED nominais; integração 357/7; local 1426/20; regressão 111. ST/IPI re-escopados (`TODO(S-C.5)`). Mergeado antes do aval; validação pós-merge aprovou **com ressalva DT-14** (convenção COD_AJ_APUR — origem: spec do coordenador) |
| S-C.5 "ICMS-ST + IPI + correção COD_AJ_APUR" | #113 | **ENCERRADO** — DT-14 fechado (`_decode_aj_apur` 4º caractere, naturezas 0..5, fixtures com códigos reais; E2E E111 com `SP000207` mantendo 100+50=150); `calcular_icms_st` + `calcular_ipi` com confronto e contas manuais; regras ST/IPI no YAML; regressão 111→142. Prova: run 27395640351 — 7/7 E2E PASSED (inclui `test_e2e_apuracao_icms_st`), integração 358/7, DT-11 limpo. Local: 1299/21, 142 regressão, black 343. Mergeado antes do aval; validação pós-merge aprovou **com DT-15** (fidelidade de leiaute Bloco E — ST real é E200/E210, não E300/E310; ver seção 2) |
| S-C.6 "Fidelidade de leiaute do Bloco E" | branch `51a3b7c` | **ENCERRADO** — DT-15 fechado: handlers E200/E210 reais (leiaute Guia Prático v3.1.5, citado no header); E300/E310 removidos; `calcular_icms_st` confronta via E210 (`vl_retencao_st + vl_out_deb_st + vl_aj_debitos_st`); E520 com 7 campos reais (sem `vl_icms_ressarc`); E530 com `ind_aj` explícito (sem `_decode_aj_apur`); deduções abatem só saldo devedor (excedente → AVISO). Regressão 142→152 (+10 cenários). Prova: run 27410841899 — 6/6 jobs success (Python 3.11+3.12, lint, security, frontend, docker), integração 358/7, fio-de-ouro `test_e2e_apuracao_icms_st` PASSED (saldo 200−100=100 devedor). Local: 1299/21, 152 regressão, black ✓ |

## 4. Fila após o S-C.6 (deltas sobre o roadmap — não executar ainda)

- **S-D.1/S-D.2 — Editor + Retificação** (inicia só após o S-C.6: opera sobre arquivos reais). Reusa HITL/progressive_autonomy para aprovação;
  toda edição vira evento no ledger (UF/período/obrigação); geração do arquivo retificado
  a partir dos registros canônicos editados; fio-de-ouro ganha editar→aprovar→regerar.
- **S-E.1/S-E.2 — Analítica.** Dashboards sobre apuração/achados; workbench read-only
  com consultas parametrizadas (RBAC).
- **DIFAL EC 87/15 (E300/E310)** — candidato sem sprint; só com demanda do stakeholder.
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
