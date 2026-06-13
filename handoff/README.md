# Handoff — Fluxo Fiscal (fio-de-ouro) + Plano de Telas

**Central de Inteligência Jurídica · Plataforma Modular de Engenharia Tributária**

Este pacote tem dois entregáveis complementares:

1. **`Plano de Telas — Central Juridica.html`** — o **contrato de design de todo o produto**: as 30 telas, ligadas a endpoints reais e papéis RBAC, com os estados obrigatórios. É o mapa do que existe e do que falta construir.
2. **`Fluxo Fiscal — Central Juridica.html`** — o **protótipo navegável de alta fidelidade do Fluxo 1** (o "fio-de-ouro" fiscal), de Upload SPED até Transmissão e-CAC. É a referência pixel-accurate a recriar primeiro.

> **Leia este README inteiro.** Ele é autossuficiente: um dev que não participou do design consegue implementar a partir daqui.

---

## 1. Sobre os arquivos de design

Os arquivos `.html` / `.jsx` / `.css` deste pacote são **referências de design feitas em HTML** — protótipos que mostram o visual e o comportamento pretendidos, **não código de produção para copiar diretamente**.

Sua tarefa é **recriar estes designs no codebase existente** (`frontend/` — React 18 + Vite + CSS puro com design tokens, **sem Tailwind/MUI**), usando os componentes primitivos e padrões já estabelecidos no repositório. A stack, os tokens e os nomes de classe CSS do protótipo foram criados para serem diretamente compatíveis — use-os como especificação fiel.

Os protótipos usam React via Babel no browser e dados fictícios (`fiscal-data.js`). No produto, troque os dados mock por chamadas reais através de **`frontend/src/api/client.js`** (cliente HTTP que centraliza auth/headers).

## 2. Fidelidade

**Alta fidelidade (hifi).** Cores finais, tipografia, espaçamentos e interações estão prontos. Recrie a UI fielmente usando as libs e padrões do codebase.

## 3. Stack e pré-requisitos

| Item | Valor |
|---|---|
| Framework | React 18 + Vite |
| Estilo | CSS puro com variáveis CSS (design tokens) — **sem Tailwind, sem MUI** |
| Fontes | IBM Plex Sans (UI) · IBM Plex Mono (números/IDs/valores monetários) · Newsreader (títulos) |
| Ícones | SVG inline monoline 24px, stroke 1.7 — ver `app/primitives.jsx` |
| Acessibilidade | WCAG 2.1 AA — `:focus-visible` navy 2px, `prefers-reduced-motion`, `aria-label`, foco visível |
| Idioma | pt-BR · moeda R$ · datas dd/mm/aaaa · números com separador de milhar |
| API | prefixo `/api/v1` · contrato vivo em OpenAPI/Swagger (`/docs`) |
| RBAC | `src/api/rbac.py` — ADMIN · OPERATOR · AUDITOR · READONLY |

---

## 4. Design tokens (já existem em `frontend/src/styles.css` = `app/base.css`)

**Não criar variáveis novas.** Os componentes usam exclusivamente estas:

```css
/* Marca / primária */
--navy:#2C5AA0; --navy-2:#234a87;        /* hover btn-primary */
--navy-tint:#eaf0f9;                      /* item ativo, glyphs, badges navy */
--navy-tint-2:#f3f7fc;                    /* hover de linha, fundo de tabela */
/* Texto */
--ink:#1b2330; --ink-2:#515b6b; --faint:#677387;
/* Superfícies */
--bg:#f5f7fa; --surface:#ffffff; --line:#e6eaf0; --line-2:#eef1f5; --mut-bg:#eef1f5;
/* Semáforo (severidade fiscal e situação) */
--ok:#1f8a4c;  --ok-bg:#e9f6ee;           /* credor / sucesso */
--warn:#8a6d0b; --warn-bg:#fbf3df;        /* AVISO / atenção */
--crit:#c0392b; --crit-bg:#fae9e7;        /* ERRO / devedor / irreversível */
/* Forma */
--radius:10px; --radius-sm:7px;
--shadow:0 1px 2px rgba(20,30,50,.06), 0 4px 16px rgba(20,30,50,.05);
/* Tipografia */
--sans:'IBM Plex Sans'; --mono:'IBM Plex Mono'; --serif:'Newsreader';
```

**Mapeamento semântico fiscal:**
- Severidade de achado: `ERRO` → `crit` · `AVISO` → `warn`
- Situação de apuração: `devedor` → `crit` · `credor` → `ok` · `equilibrado` → `mut`
- Valores monetários: sempre `IBM Plex Mono`, **alinhados à direita**, `font-variant-numeric: tabular-nums`, formatados com `toLocaleString('pt-BR', {minimumFractionDigits:2})`.

**Modo escuro:** manter paridade (o app já tem). **Colorblind-safe:** quando `data-cb="1"` no `<html>`, sobrescrever ok/warn/crit (ver `ext.css`).

---

## 5. O contrato — todas as telas (ver `Plano de Telas`)

O Plano de Telas documenta **30 telas em 6 domínios**, cada uma com endpoints, papel mínimo e estados-chave. Resumo do que o dev precisa entregar:

| Domínio | Telas | Status |
|---|---|---|
| **Fiscal** (núcleo) | Upload SPED · Escriturações (lista) · Escrituração (detalhe) · Achados · Edição em lote · Apuração · Retificação · Due Diligência · Consultoria | 1 nova · 8 redesenho |
| **PER/DCOMP & Transmissão** | PER/DCOMP · Transmissão e-CAC | redesenho (capstone irreversível) |
| **Cofre** | Cofre de Credenciais (cert A1) | redesenho (sensível) |
| **Analítica** | Analytics Fiscal · Relatórios · Workbench SQL | redesenho |
| **Jurídico/Usuário** | Assistente · Jurisprudência · Legislativo · Investigação 360° · Minhas consultas · Perfil · Privacidade (LGPD) | 360° entregue · 1 nova · resto redesenho |
| **Admin/Config** | HITL · Monitoramento · Ledger · Autonomia (DMN) · Treinamento · Agentes · **Gestão de Módulos (nova)** · **Usuários & RBAC (nova, AP-08)** · **Prontidão de Sistema (nova)** | 6 redesenho · 3 novas |

**Regra de ouro do RBAC:** ação sem permissão **nunca** vira erro — o controle fica **oculto** ou **visível-desabilitado** com tooltip "requer perfil X". Telas inteiras fora do papel não entram no menu.

**Convenção `screen_id`:** cada tela tem um `screen_id` (ex.: `fiscal-upload`, `retificacao`, `transmissao`) que entra no sistema de slots dinâmicos (`frontend/src/App.jsx` + `GET /api/v1/slots/stream`). Os ids estão em cada cartão do Plano de Telas. Toda tela nova precisa de um `screen_id` acordado.

---

## 6. Fluxo 1 — fio-de-ouro fiscal (implementar primeiro)

Uma **jornada de 8 etapas dentro de uma escrituração**, com stepper de progresso visível. Cada etapa é uma tela (ou aba) com seus endpoints, estados e interações.

### Shell comum a todas as etapas
- **Sidebar** (`.sidebar`): grupo "Fiscal" com as 8 etapas; etapas não alcançadas ficam **travadas** (ícone `lock`, `opacity:.45`); concluídas mostram check verde.
- **Topbar** (`.topbar`): breadcrumb `Fiscal / Escrituração / <etapa>`; badge de ambiente (homologação/produção); botões de reiniciar e notificações.
- **Stepper** (`.fstepper`): 8 passos clicáveis (só para etapas já alcançadas). Estados de passo: `done` (navy preenchido + check), `now` (anel navy + halo), idle/`locked`. Conectores navy entre passos concluídos.
- **Barra da escrituração** (`.esc-bar`, a partir da etapa 2): empresa, **CNPJ mascarado**, UF, período, regime, `db_id`, badge "PII mascarada".

### Estado (state machine)
```
step: 0..7         // etapa atual
maxStep: 0..7      // etapa máxima alcançada (controla travas e navegação)
go(i)  → setStep(i); maxStep = max(maxStep, i); scroll topo
next() → go(step+1)
```
Persistir `step`/`maxStep` (no protótipo: `localStorage`; no produto: rota/URL ou estado do servidor por escrituração).

---

### Etapa 1 — Upload SPED · `screen_id: fiscal-upload` · OPERATOR · **tela nova**
- **Propósito:** importar o arquivo EFD (≤500 MB) e disparar o processamento assíncrono.
- **Layout:** título serif 22px → subtítulo → `.dropzone` (borda tracejada, 40px padding, hover navy) que vira `.file-chip` ao selecionar → `.field-row` (grid 3 col: regime / UF / período) → `.step-foot` com botão primário "Enviar escrituração".
- **Componentes:** dropzone com drag-over (`.drag`), validação client-side de tipo (.txt) e tamanho (≤500 MB), `<select>` regime (`lucro_real`/`presumido`/`simples`) e UF, input período (aaaa-mm).
- **Endpoint:** `POST /fiscal/upload` (multipart: arquivo, regime, uf) → retorna `db_id` e dispara job.
- **Estados obrigatórios:** vazio (dropzone), erro 422 (tipo/tamanho — realçar), **processando** (transição para etapa 2). Botão desabilitado até arquivo+regime+uf.
- **Interação:** "Enviar" → POST → navega para etapa 2 (processando). **Não** mostrar spinner morto.

### Etapa 2 — Processando (job assíncrono) · `screen_id: fiscal-escrituracao`
- **Propósito:** acompanhar o job sem travar a UI.
- **Layout:** `.job-card` com cabeçalho (spinner `.job-spin` → vira check ok ao concluir), `.job-bar`/`.job-fill` (barra de progresso), `%` em mono, e `.job-log` (linhas que aparecem em sequência, cada uma com dot ok + texto + tempo em mono).
- **Endpoints:** poll `GET /fiscal/escrituracoes/{id}` (status) — padrão de job assíncrono `/jobs/{id}`.
- **Estados:** processando (barra animada + log incremental) → concluído (check verde + botão "Ver achados (n)"). **Permitir sair e voltar** — o job continua no servidor.
- **Interação:** ao concluir, botão primário → etapa 3.

### Etapa 3 — Achados · `screen_id: fiscal-achados` · AUDITOR (leitura) / OPERATOR
- **Propósito:** revisar inconsistências detectadas.
- **Layout:** filtro `.seg` (Todos / Erros / Avisos com contagens) → lista de `.ach-card` (borda esquerda 4px: `crit` para ERRO, `warn` para AVISO). Cada card: badge de severidade + badge da regra + registro/linha/campo em mono à direita + descrição + `.ach-dica` (fundo navy-tint, ícone spark).
- **Endpoint:** `GET /fiscal/escrituracoes/{id}/achados` (severidade ERRO/AVISO, regra, descrição, dica).
- **Estados:** vazio ("nenhum achado"), carregando (skeleton), sucesso. Filtro por severidade e por regra.
- **Interação:** CTA "Corrigir em lote" → etapa 4 (ponte para a edição).

### Etapa 4 — Edição em lote (dry-run → HITL) · `screen_id: fiscal-edicao-lote` · OPERATOR
- **Propósito:** corrigir registros em massa com pré-visualização e revalidação.
- **Layout:** tabela `.t2` dos registros selecionados (registro·linha, item, **CST antes→depois** com `.cst-from` tachado + `.cst-to` verde, valor à direita em mono) + linha de total.
- **Fases (state local `phase`):**
  - `edit` → botão "Pré-visualizar (dry-run)".
  - `preview` → `.dryrun-banner` (antes/depois + revalidação simulada: achado some, saldo recalculado) + botão "Aplicar correção".
  - Se a ação exige aprovação (faixa de autonomia / Tweak `exigirHITL`): `aguardando` → `.hitl-gate.pending` com linha do tempo (`Solicitado → Em revisão → Aplicado`), badge `aguardando_aprovação`, protocolo HITL. Botão "Aprovar" simula o auditor (no produto: outro papel, fila HITL).
- **Endpoints:** `POST /fiscal/escrituracoes/{id}/registros/lote` (dry_run → real); aprovação via `/api/v1/hitl`; aplicação final `POST /fiscal/escrituracoes/{id}/lote/confirmar`.
- **Estados:** preview dry-run, aguardando_aprovação, erro 422, sucesso.

### Etapa 5 — Apuração · `screen_id: fiscal-apuracao` · OPERATOR
- **Propósito:** ver débitos/créditos/saldo por tributo e divergências.
- **Layout:** `.apur-grid` com um `.apur-card` por tributo (ICMS, PIS, COFINS, ICMS-ST, IPI). Cabeçalho: nome + registro (E110/M200/M600/E210/E520) + **saldo grande em mono** (cor por situação) + badge devedor/credor/equilibrado. Corpo: 3 células (Débitos/Créditos/Ajustes). Se `computado ≠ declarado` → `.apur-diverg` (fundo crit, valores em mono).
- **Endpoint:** `POST /fiscal/escrituracoes/{id}/apuracao` (ICMS/PIS/COFINS/ST/IPI, saldo, situação, divergências E110/E210/E520/M200/M600).
- **Estados:** divergências realçadas, processando, sucesso.
- **Interação:** "Gerar retificação" → etapa 6.

### Etapa 6 — Retificação · `screen_id: retificacao` · OPERATOR (`retificacao:write`)
- **Propósito:** comparar original × retificado, validar e gerar a retificadora (ato formal).
- **Layout:** `.diff-view` agrupado por registro; cada grupo: linha `.del` (vermelho, sinal −) e `.add` (verde, sinal +) em mono.
- **Fases:** validar layout → `.validate-ok` (banner verde) → botão **danger** "Gerar retificadora" → `<Modal>` de confirmação (irreversível) → card de download do TXT.
- **Endpoints:** `POST /retificacao/comparar`, `/validar-layout`, `/nota-correcao`; `GET /fiscal/escrituracoes/{id}/retificado` (download TXT).
- **Estados:** confirmação irreversível (modal), gerar→baixar, erro de layout, sucesso.

### Etapa 7 — PER/DCOMP · `screen_id: per-dcomp` · OPERATOR (`per_dcomp:generate/validate`)
- **Propósito:** aproveitar crédito apurado, gerar e validar a ficha.
- **Layout:** `.type-grid` de opções (radio custom `.type-opt`) → botão "Gerar de apuração" → `.ficha` legível (cabeçalho + `.kv` com número/período/origem/crédito/Selic/débito/situação + `.ficha-total` destacado). Badge "layout válido".
- **Endpoints:** `GET /per_dcomp/tipos`; `POST /per_dcomp/gerar`, `/gerar-de-apuracao`, `/validar`.
- **Estados:** ficha legível, erro de validação, sucesso → transmissão.

### Etapa 8 — Transmissão e-CAC · `screen_id: transmissao` · OPERATOR (`transmissao:enviar/consultar`)
- **Propósito:** transmitir à Receita — **ação irreversível e federal**.
- **Layout:** `.amb-banner` (homologação navy / produção crit) → `.transmit-summary` (resumo do que será enviado, CNPJ mascarado) → `.circuit` (estado do circuit breaker) → botão de transmitir.
- **Confirmação dupla:** botão → `<Modal>` com resumo + **checkbox obrigatório** "ciente de que é irreversível" → "Transmitir agora". Em produção, botões em vermelho (`btn-danger`).
- **Circuit breaker:** se `GET /transmissao/circuit` = aberto → `.circuit.open` ("e-CAC indisponível, transmissão bloqueada temporariamente") e **botão desabilitado** — não deixar o usuário tentar.
- **Endpoints:** `POST /transmissao/enviar`; `GET /transmissao/status/{id}`, `/historico`, `/circuit`.
- **Estados:** dupla confirmação, circuit aberto (bloqueio), processando (status), sucesso (protocolo + recibo copiáveis via `<CopyLine>`, rodapé de auditoria com ledger).

---

## 7. Estados obrigatórios — entregar TODOS por tela

1. **Carregando** — skeletons (`.skeleton`), nunca spinner morto.
2. **Vazio / 1º uso** — com CTA ("Envie sua primeira escrituração").
3. **Erro** — taxonomia (§8).
4. **Sem permissão** — controle oculto ou desabilitado com motivo.
5. **Sucesso / conteúdo** — estado normal.
6. **Processando (async)** — job em background; poll + sair/voltar.

## 8. Taxonomia de erro (consistente em todas as telas)

| Código | Significado | UI |
|---|---|---|
| **422** | Validação | Realçar o campo + mensagem específica inline. |
| **403** | Sem permissão | Estado "sem permissão" — controle oculto/desabilitado com motivo. |
| **503** | Banco/serviço indisponível | Estado de manutenção + botão retry. |
| **500** | Erro interno | Mensagem neutra + **id de referência** (o backend devolve — exibi-lo). |

## 9. Padrões transversais (componentes reutilizáveis — desenhar uma vez)

- **Upload grande (≤500 MB):** dropzone + validação client-side + progresso + transição a processamento.
- **Ciclo de job assíncrono:** submeter → "em andamento" (`/jobs/{id}`) → conclusão. Nunca travar a UI.
- **HITL:** fila + detalhe; solicitante vê `aguardando_aprovação`; aprovador (AUDITOR/ADMIN) decide com justificativa; badge de pendências no shell.
- **Tempo real (SSE):** menu de módulos (`GET /api/v1/slots/stream`) e status; indicador "ao vivo".
- **Downloads:** TXT retificado, CSV de relatórios/ledger — padrão "gerar → baixar".
- **Confirmação de irreversíveis:** transmissão e-CAC, exclusão de credencial, retificadora → modal com resumo do impacto.
- **Mascaramento de PII (LGPD):** CPF/CNPJ e dados pessoais mascarados por padrão (`12.***.***/0001-90`); "revelar" auditado só para papéis autorizados. **Nunca** o valor completo no DOM, tooltips ou logs.

## 10. Mascaramento de PII — checklist crítico

- [ ] CNPJ/CPF mascarados em 100% dos lugares (DOM, tooltips, console).
- [ ] "Revelar" (quando existir) é auditado e gated por papel.
- [ ] Identificadores em mono, formato consistente.

---

## 11. Componentes primitivos disponíveis (`app/primitives.jsx`)

| Componente | Uso |
|---|---|
| `<Icon name>` | Ícones SVG monoline (set completo no arquivo: `attach`, `doc`, `alert`, `edit`, `scale`, `compare`, `send`, `lock`, `check`, `refresh`, etc.) |
| `<Badge kind icon dot>` | Pills de status (`mut`/`navy`/`ok`/`warn`/`crit`) |
| `<Stat>` | Cartão de KPI |
| `<Spark points>` | Mini-gráfico de linha |
| `<Modal title actions onClose>` | Modal acessível (focus trap + Esc) — usado nas confirmações |
| `<Drawer title sub footer onClose>` | Painel lateral direito |
| `<CopyLine value label>` | Botão de copiar protocolo/identificador |

`app/tweaks-panel.jsx` é o painel de Tweaks do protótipo (densidade, colorblind, exigir HITL, ambiente e-CAC, circuit breaker). **No produto, estes tweaks viram: configurações reais** (autonomia/HITL em `/api/v1/autonomy`), seleção de ambiente, e estado real do circuit breaker. Não precisa portar o painel.

---

## 12. Responsividade

Desktop-first (ferramenta de trabalho). Tabelas e formulários degradam para tablet. Mobile = consulta/aprovação, não edição pesada.

| Breakpoint | Comportamento |
|---|---|
| ≤768px | Sidebar oculta; `.fiscal-screen` padding reduzido; `.apur-body` em coluna única; stepper rola horizontalmente. |

## 13. Ordem sugerida de construção

1. **Design system + shell + estados base** (fundação).
2. **Fio-de-ouro fiscal (8 etapas) + HITL** (este pacote — Fluxos 1 e 2).
3. **PER/DCOMP + Transmissão + Cofre/cert A1**.
4. **Analytics · Relatórios · Workbench · Ledger**.
5. **Admin: Gestão de Módulos (SSE) · Usuários/RBAC · Prontidão de Sistema** (telas novas).
6. **Jurídico/Usuário: refino + LGPD placeholder** (360° já entregue na Fase 1).

## 14. Critério de aceite

> Um contador encontra, entende e confia no que vê — e nunca transmite algo irreversível sem dupla confirmação.

- [ ] Stepper reflete a etapa atual e o que falta; etapas futuras travadas.
- [ ] Cada etapa entrega os 6 estados obrigatórios (§7).
- [ ] Erros seguem a taxonomia (§8), inclusive id de referência no 500.
- [ ] Upload mostra progresso real de job; permite sair e voltar.
- [ ] Edição em lote tem dry-run antes/depois e, quando exigido, gate HITL com `aguardando_aprovação`.
- [ ] Apuração destaca divergências computado × declarado.
- [ ] Retificação exige confirmação (ato formal) antes de gerar.
- [ ] Transmissão e-CAC: dupla confirmação + checkbox; rotula homologação vs produção; bloqueia com circuit breaker aberto.
- [ ] PII mascarada em 100% dos lugares (§10).
- [ ] `prefers-reduced-motion` desliga animações; foco visível navy; `aria-label` em ícones-botão.

---

## 15. Arquivos deste pacote

| Arquivo | Descrição |
|---|---|
| `Plano de Telas — Central Juridica.html` | **Contrato** de todas as 30 telas (tela ↔ endpoint ↔ permissão ↔ estados). Autossuficiente — abrir no browser. |
| `Fluxo Fiscal — Central Juridica.html` | **Protótipo** do fio-de-ouro (8 etapas). Abrir no browser e navegar pelo stepper / sidebar. |
| `app/base.css` | Design system (tokens + componentes primitivos) — idêntico a `frontend/src/styles.css`. |
| `app/ext.css` | Extensões já existentes (Fase 1). |
| `app/fiscal-ext.css` | Classes do fluxo fiscal (stepper, dropzone, job, apuração, diff, ficha, transmissão). |
| `app/primitives.jsx` | Ícones, Badge, Stat, Spark, Modal, Drawer, CopyLine. |
| `app/tweaks-panel.jsx` | Painel de Tweaks (só protótipo). |
| `app/fiscal-data.js` | Dados fictícios da escrituração (trocar por API real). |
| `app/fiscal-steps-a.jsx` | Etapas 1–4 (Upload, Processando, Achados, Lote). |
| `app/fiscal-steps-b.jsx` | Etapas 5–8 (Apuração, Retificação, PER/DCOMP, Transmissão). |
| `app/fiscal-flow.jsx` | Shell + stepper + máquina de estados + Tweaks. |

## 16. Fonte da verdade técnica

- **API:** OpenAPI/Swagger do backend (`/docs`) — esquemas exatos de request/response.
- **Papéis/permissões:** `src/api/rbac.py`.
- **Cliente HTTP:** `frontend/src/api/client.js` (toda tela consome por ele).
- **Navegação e slots dinâmicos:** `frontend/src/App.jsx` + `GET /api/v1/slots/stream` (SSE).

---

## 17. Mapa do codebase — arquivos a editar

Os scaffolds já existem em `frontend/src/screens/fiscal/`. O dev **edita** estes arquivos (não cria do zero):

| screen_id | Arquivo no codebase | Situação |
|---|---|---|
| `fiscal-upload` (Etapa 1) | `EscrituracaoScreen.jsx` | Scaffold — implementar dropzone + form |
| `fiscal-escrituracao` (Etapa 2) | `EscrituracaoScreen.jsx` | Scaffold — implementar job poll + log |
| `fiscal-achados` (Etapa 3) | `EscrituracaoScreen.jsx` | Scaffold — implementar filtros + cards |
| `fiscal-edicao-lote` (Etapa 4) | `EscrituracaoScreen.jsx` | Scaffold — implementar dry-run + HITL gate |
| `fiscal-apuracao` (Etapa 5) | `EscrituracaoScreen.jsx` | Scaffold — implementar apur-grid + divergências |
| `retificacao` (Etapa 6) | `RetificacaoScreen.jsx` | Scaffold — implementar diff-view + modal confirm |
| `per-dcomp` (Etapa 7) | `PERDCOMPScreen.jsx` | Scaffold — implementar type-grid + ficha |
| `transmissao` (Etapa 8) | `TransmissaoScreen.jsx` | Scaffold — implementar dupla confirm + circuit |
| `fiscal-dashboard` | `FiscalDashboardScreen.jsx` | Scaffold — KPIs + distribuição + anomalias |
| `due-diligence` | `DueDiligenceScreen.jsx` | Scaffold — fiscal 360° por CNPJ |
| `consultoria-fiscal` | `ConsultoriaScreen.jsx` | Scaffold — RAG fiscal |
| `reports-workbench` | `ReportsWorkbenchScreen.jsx` | Scaffold — analytics + workbench SQL |

**Componentes transversais já prontos no codebase:**
- `frontend/src/components/primitives.jsx` — `Icon`, `Badge`, `Stat`, `Spark`, `Modal`, `Drawer`, `CopyLine`
- `frontend/src/styles.css` — todos os tokens (idêntico a `handoff/app/base.css`)
- `frontend/src/api/client.js` — cliente HTTP (`api.get`, `api.post`, `api.put`, `api.del` + endpoints tipados)
- `frontend/src/components/toast.jsx` — notificações toast
- `frontend/src/api/hitlSocket.js` — WebSocket para fila HITL em tempo real

**Executar o protótipo localmente:**
```bash
# Abrir os HTMLs diretamente no browser (sem servidor):
open handoff/Fluxo\ Fiscal\ -\ Central\ Juridica.html
open handoff/Plano\ de\ Telas\ -\ Central\ Juridica.html

# Rodar o frontend real em dev:
cd frontend && npm install && npm run dev
# App em http://localhost:5173 · API proxy para http://localhost:8000
```
