# Roadmap de Execução v1 — Plano Unificado de Implementação

> **Log vivo** da execução autônoma do plano unificado (minha análise + análise do
> analista "Super Z"). Atualizado a cada PR. Detalhes da análise/validação em
> [`PLANO_IMPLEMENTACAO_UNIFICADO.md`](PLANO_IMPLEMENTACAO_UNIFICADO.md).
> Pendências do dono em [`pendencia_v1.md`](pendencia_v1.md).

Status: ⬜ a fazer · 🟦 em andamento · ✅ merged · ⏸️ bloqueado (ver pendência) · 🔵 roadmap futuro

## Protocolo
Branch `claude/<onda>-<slug>` ← `master` → implementar+testar → pré-validar local
(`black`, `bandit` high, `pytest unit cov≥50`, `eslint`, `npm build`) → push → PR →
CI verde (corrigir até) → auto-review → **merge**. Cobertura unitária do CI: **≥50%**.

---

## Sequência de PRs

| PR | Onda | Escopo | Status | PR# | Notas |
|---|---|---|---|---|---|
| PR0 | — | Scaffolding: `roadmap_v1`, `pendencia_v1`, cópia do plano | ✅ | #133 | merged |
| PR1 | 1 | Higiene: botões Demo (guard DEV), botão morto Invest360 (wire→Processos), default `INTEGRATIONS_*=real` (só fontes implementadas), ortografia README, clarificação `handoff/` | ✅ | #134 | merged |
| PR2 | 2 | **CoT-LLM plugável** no ArchitectAgent (narrativa via LLM + fallback determinístico; roteamento sempre determinístico) | 🟦 | — | **C2** |
| PR3 | 2 | Consenso semântico + recalibrar `consensus_strength`/gate HITL | ⬜ | — | C1 |
| PR-S | 1 | Streaming SSE `/api/v1/tasks/stream` + timeline/agentes no AssistantScreen | ⬜ | — | reordenado p/ depois (god-method) |
| PR4 | 3 | Migrations ledger/hitl/training/a2a + training real + embeddings reais + A2A pub/sub | ⬜ | — | C3, I2, I3, I4 |
| PR5 | 4 | e-CAC real atrás do stub + CRC/CADIN/ONR + Vault wiring + handlers Celery | ⬜ | — | credenciais→pendência |
| PR6 | 5 | Diferenciais UX: "Contradição encontrada", Modo Explorador, badges, mapa (MVP) | ⬜ | — | XL |
| — | T | Transversal segurança/LGPD tecido nos PRs | ⬜ | — | rate-limit, redact_pii, etc. |

---

## Histórico de execução

### PR0 — Scaffolding (✅ merged em #133)
- Criados `docs/roadmap_v1.md`, `docs/pendencia_v1.md`, `docs/PLANO_IMPLEMENTACAO_UNIFICADO.md`.
- Objetivo: persistir o plano (o arquivo de `/root/.claude/plans` é efêmero) e validar o loop PR→CI→merge. CI 6/6 verde.

### PR1 — Onda 1 higiene (✅ merged em #134)
- **Botões Demo** (`App.jsx`): agora atrás de `import.meta.env.DEV` — removidos do build de produção.
- **Botão morto Invest360** (`Invest360Screen.jsx`): "Abrir na consulta processual" agora navega para a tela
  Processos com o nº CNJ pré-preenchido e consulta automática (via `store.consultaProcesso` + `go('process')`).
- **docker-compose**: fontes implementadas (DataJud/DJEN/Receita/TSE) passam a `=real` por padrão (degradam p/
  mock sem credencial); CRC/CADIN/ONR seguem `=mock` (real levanta `NotImplementedError`).
- **README**: correções de acentuação (título, intro, headers, "Raciocínio").
- **handoff/README.md**: nota esclarecendo que é _design handoff_, não runtime (decisão: clarificar em vez de
  renomear o diretório, que tocaria ADR-002/.gitignore — registrado abaixo).

---

### PR2 — C2: CoT por LLM plugável (🟦 em andamento)
- `ArchitectAgent` ganha modo opcional de Chain-of-Thought por LLM: a **narrativa** (`chain_of_thought`)
  pode vir de um LLM (`llm_fn` injetável ou Ollama local lazy; flag `ARCHITECT_COT_LLM=1`), enquanto a
  **identificação de tribunais e a confiança permanecem determinísticas** (roteamento reprodutível).
- Degrada graciosamente: sem LLM, resposta vazia, string "Erro:…" ou exceção → mantém a heurística.
- **Aditivo e retrocompatível** (default = heurística), então os testes existentes seguem verdes.
- Novos testes: `tests/unit/test_architect_cot_llm.py` (6 casos). Local: 14 passed, black/bandit ok.
- Endereça o achado C2 (validado): o "CoT" era 100% heurística por keyword — agora há caminho real de LLM.

## Decisões de execução (desvios do plano, justificados)
- **`handoff/`→`design-handoff/` NÃO renomeado:** o diretório é referenciado em `docs/ADRs/ADR-002`
  e `.gitignore` (docs históricos). Em vez de reescrever registros históricos por ganho cosmético, adicionei
  nota de esclarecimento no `handoff/README.md` (atinge o objetivo do analista: remover a confusão). Rename
  pleno fica como item opcional de baixo valor.
- **`INTEGRATIONS_*=real` seletivo:** flip apenas das 4 fontes com adapter real; as 3 sem implementação
  (CRC/CADIN/ONR) seguiriam para FAILED (não mock) em modo real — mantidas em `mock`.

## Novos gaps descobertos durante a execução
_(inseridos aqui na posição adequada conforme surgem)_

- _(nenhum ainda)_
