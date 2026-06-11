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
  regride (baseline atual: **1188 passed / 14 skipped**, master `5579082`).
- **Teste fio-de-ouro.** A partir deste sprint existe um teste de integração
  `tests/integration/test_golden_thread.py` que percorre o pipeline inteiro via API. Ele
  **nunca** é removido ou enfraquecido — cada sprint o **estende** (C.3: mais regras;
  D: retificação; F: PER/DCOMP). É a prova permanente de que as funcionalidades estão
  integradas de ponta a ponta, não só testadas em unidade.

## 2. Registro de débitos técnicos

| ID | Descrição | Origem | Resolução | Status |
|---|---|---|---|---|
| DT-01 | `RuntimeWarning: coroutine 'send_notification' was never awaited` em `src/hitl/hitl_queue.py:322` | Onda 1 | **S-C.2** (higiene) | aberto |
| DT-02 | 5 warnings eslint (unused vars em HitlScreen, TrainingScreen, Invest360Screen, JurisScreen) e CI sem `--max-warnings 0` | Onda 1/PR #83 | **S-C.2** (higiene) | aberto |
| DT-03 | `src/workers/tasks.py`: `process_sped_file` e `analyze_document` são placeholders com mensagens desatualizadas ("parser EFD em S-B.1") | S-0.5 | **S-C.2 Parte A** (vira pipeline real) | aberto |
| DT-04 | Decisões do Bloco C sem ADR (regras determinísticas sem `weighted_voting`; YAML/UF adiado) | S-C.1 | **S-C.2** (higiene — ADR curto) | aberto |
| DT-05 | **Pipeline desconectado**: upload (S-B.1) não dispara parsing; parsers B.2–B.4 e rules engine C.1 não são alcançáveis via API | S-B.1..C.1 | **S-C.2 Parte A** | aberto |
| DT-06 | Regras fiscais hardcoded em Python; carregamento YAML por UF pendente | S-C.1 | **gatilho:** entrada da 1ª regra dependente de UF (provável S-C.3) | registrado |

## 3. SPRINT ATUAL — S-C.2 "Fio de Ouro + Apuração"

**Objetivo:** tornar o pipeline fiscal real de ponta a ponta (Parte A) e construir sobre
ele o mapa de apuração ICMS/PIS/COFINS (Parte B). Ao final, um arquivo SPED enviado via
API resulta em registros canônicos persistidos, achados de regras consultáveis e apuração
calculada — tudo verificável pelo teste fio-de-ouro.

### Parte A — Ligar o pipeline (resolve DT-03 e DT-05)

1. **Task real** em `src/workers/tasks.py::process_sped_file`:
   baixa o arquivo do MinIO (`file_key`) → detecta tipo (`efd_icms` | `efd_contrib` |
   xml, pela extensão/conteúdo já validados no upload) → `registry.get_parser(...)` →
   persiste registros canônicos via Repository (S-B.1) vinculados à `EscrituracaoFiscal`
   → roda `FiscalRulesEngine` (regime vindo dos metadados do upload) → persiste resumo de
   achados → atualiza status da escrituração (`recebido → processando → processado |
   erro`) e `FiscalAudit`.
2. **Disparo no upload**: `POST /api/v1/fiscal/upload` enfileira a task ao final do fluxo
   atual. **Fallback síncrono** quando Celery/broker ausentes (mesmo padrão de degradação
   graciosa do resto do repo — ex.: ledger sem Postgres): executa inline e responde com o
   mesmo contrato.
3. **Consulta de status/resultado**:
   - `GET /api/v1/fiscal/escrituracoes/{id}` → status, contadores (registros por bloco,
     erros/avisos de regra), `correlation_id`.
   - `GET /api/v1/fiscal/escrituracoes/{id}/achados` → lista paginada dos `RuleResult`.
4. **Idempotência e falha**: reprocessar a mesma escrituração não duplica registros
   (upsert por escrituração+linha ou limpeza transacional antes de regravar); exceção na
   task marca `erro` com motivo, nunca deixa `processando` eterno.
5. **Observabilidade**: spans/log estruturado por estágio (download→parse→persist→rules)
   com `correlation_id`; contadores Prometheus (arquivos processados, falhas, duração).

### Parte B — Mapa de apuração (S-C.2 do roadmap)

6. **Engine** `src/fiscal/apuracao.py`, stateless, espelhando o padrão de
   `rules_engine.py`/`reconciliation.py`:
   - **ICMS** (EFD-ICMS/IPI): débitos por saída e créditos por entrada a partir de
     C100/C170 (e D100), consolidação mensal → saldo (devedor a recolher | credor a
     transportar), considerando saldo credor anterior. **Confronto computado × declarado**:
     compara o calculado com o bloco E110 do próprio arquivo e gera divergência
     (`Severidade` reutilizada) quando não bate.
   - **PIS/COFINS** (EFD-Contribuições): consolidação a partir de M200/M210 e M600/M610,
     mesmo confronto computado × declarado.
   - Modelo **minimalista** (roadmap): sem ajustes/benefícios especiais nesta iteração —
     o que não for coberto, listar explicitamente no docstring como fora de escopo.
7. **Persistência**: entidade `ApuracaoFiscal` (migration `0003`): período, tributo,
   totais (débitos, créditos, saldo anterior, saldo final), situação (devedor/credor),
   divergências, FK para escrituração. Repository com o mesmo padrão de cache dos demais.
8. **API**: `POST /api/v1/fiscal/escrituracoes/{id}/apuracao` (calcula e persiste) e
   `GET /api/v1/fiscal/apuracoes?periodo=&tributo=` (consulta). RBAC consistente com as
   rotas fiscais existentes.
9. **Casos-teste oficiais (DoD do roadmap)**: fixtures SPED sintéticas em
   `tests/fixtures/fiscal/` com valores de apuração **calculados à mão e documentados no
   próprio fixture** (comentário com a conta), cobrindo: saldo devedor, saldo credor,
   saldo credor anterior, divergência computado×declarado, arquivo PIS/COFINS. Mínimo 5
   cenários por tributo.

### Higiene do sprint (resolve DT-01, DT-02, DT-04)

10. DT-01: corrigir o `send_notification` não-awaitado em `hitl_queue.py:322`.
11. DT-02: zerar os 5 warnings de eslint e adicionar `--max-warnings 0` ao step de lint
    do frontend no CI.
12. DT-04: ADR curto em `docs/ADRs/` registrando: (a) regras fiscais determinísticas sem
    `weighted_voting` (auditabilidade, CJ-001); (b) YAML/UF adiado até a 1ª regra
    estadual (DT-06).

### Teste fio-de-ouro (novo, obrigatório)

13. `tests/integration/test_golden_thread.py`: via `TestClient`, com fallback síncrono
    (sem Celery/MinIO/Postgres reais — mesmos skips graciosos do repo quando faltar
    infra): upload de fixture EFD-ICMS → escrituração `processado` → registros canônicos
    contados → achados de regra presentes → apuração calculada com saldo esperado →
    divergência E110 detectada no fixture próprio para isso. Espelho mínimo do fluxo para
    EFD-Contribuições.

### DoD do S-C.2 (o coordenador roda exatamente isto)

```bash
black --check src/ tests/
python -m pytest tests/unit/ tests/integration/ -q          # 0 falhas, baseline 1188 + novos
python -m pytest tests/integration/test_golden_thread.py -v # pipeline E2E verde
python -m pytest tests/unit/test_apuracao*.py -q            # casos oficiais conferidos
grep -rn "pipeline SPED em S-B.1\|parser EFD em S-B.1" src/ # 0 ocorrências (DT-03)
cd frontend && npx eslint src --ext .js,.jsx --max-warnings 0  # DT-02
```

- [ ] Upload dispara processamento (async com Celery; inline sem) — evidência: teste
- [ ] Reprocessamento idempotente — evidência: teste
- [ ] Falha de parsing marca `erro` com motivo — evidência: teste
- [ ] Apuração ICMS e PIS/COFINS conferidas contra ≥5 cenários/tributo documentados
- [ ] Confronto computado × declarado (E110/M200/M600) com divergência sinalizada
- [ ] Migration 0003 aplica via `alembic upgrade head` no CI
- [ ] DT-01..DT-05 fechados nesta tabela (status → resolvido) no mesmo PR
- [ ] Estimativa de testes novos: ~55–70 (PR declara o número exato)

## 4. Fila após o S-C.2 (deltas sobre o roadmap — não executar ainda)

- **S-C.3 — Bateria ampla + Edição em lote + RuleLoader YAML.** Entra a 1ª regra
  dependente de UF → implementar o `RuleLoader` YAML (DT-06) alimentando o MESMO
  `FiscalRulesEngine` sem mudar API pública. Edição em lote transacional sobre os
  registros canônicos (não sobre o arquivo). Seed da **regressão tributária 200+**:
  estrutura `tests/regression_fiscal/` parametrizada por fixtures YAML (cenário→esperado),
  começando com ~50 cenários reais derivados das regras existentes.
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
