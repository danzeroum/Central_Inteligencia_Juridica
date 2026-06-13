# Brief de Design — UI de Conexão Frontend ↔ Backend
### Central de Inteligência Jurídica / Plataforma Modular de Engenharia Tributária

> Para o designer. Objetivo: desenhar (ou redesenhar) **todas** as telas e estados que ligam
> o frontend ao backend, cobrindo cada funcionalidade e cada configuração já existentes na API.
> Este brief é **ancorado nos endpoints reais** (seção 4). Não invente recursos: se algo não
> está no mapa da seção 4, não tem backend — sinalize como "proposta" antes de desenhar.

---

## 0. Como usar este brief

1. Leia personas (§1) e o sistema de design (§2) — são a base de tudo.
2. O **mapa-mestre tela ↔ endpoint ↔ permissão** (§4) é o contrato: cada tela existe para
   consumir endpoints específicos sob um papel específico. Desenhe a partir dele.
3. Para cada tela, entregue **todos os estados** do §2.4 (carregando, vazio, erro, sem-permissão,
   sucesso) — não só o "happy path".
4. Os **padrões transversais** (§6) se repetem em dezenas de telas: desenhe-os uma vez como
   componentes e reuse.
5. Veja o **gap** (§8): a maioria das telas já existe (redesenho/refino); algumas são novas.

---

## 1. Produto, personas e papéis (RBAC)

**Produto:** plataforma que importa arquivos fiscais SPED (EFD-ICMS/IPI, EFD-Contribuições),
detecta inconsistências, apura tributos (ICMS/PIS/COFINS/ST/IPI), permite **retificar** a
escrituração e gera + **transmite PER/DCOMP** ao e-CAC da Receita (homologação). Em volta há
módulos jurídicos (jurisprudência, legislativo, due diligence, consultoria) e administração
(aprovações humanas, auditoria, autonomia, agentes de IA, cofre de credenciais).

**Personas = papéis RBAC** (a UI é *role-gated*; o menu e os botões mudam por papel):

| Papel | Persona | O que faz na UI |
|---|---|---|
| `ADMIN` | Gestor da plataforma | Tudo: configura módulos, autonomia, cofre/certificado, usuários, workbench |
| `OPERATOR` | Contador / Analista fiscal | Núcleo fiscal: upload, apuração, retificação, PER/DCOMP, relatórios |
| `AUDITOR` | Auditor / Perito | Leitura + aprovações (HITL), auditoria (ledger), achados — **não edita** |
| `READONLY` | Cliente / Consulta | Dashboards, consultas, histórico — somente leitura |

Regra de ouro de design: **toda ação sem permissão não aparece como erro** — o controle
fica oculto, ou visível-desabilitado com tooltip "requer perfil X". Telas inteiras fora do
papel não entram no menu.

---

## 2. Sistema de design (fundação)

### 2.1 Extrair e formalizar o existente
Já existem 24 telas e um set de ícones em uso (`spark, process, scale, law, radar, clock,
cog, privacy, doc, compare, ledger, pulse, flow, shield, lock, graduate, robot`). **Primeiro
passo:** auditar essas telas e consolidar um **design system** (não criar do zero um conflitante).

### 2.2 Tokens
- **Cor:** paleta primária + semânticas obrigatórias — `sucesso/verde`, `aviso/âmbar`,
  `erro/vermelho`, `info/azul`, `neutro`. Severidades fiscais usam essas 3 primeiras
  (achados: ERRO/AVISO; situação: devedor/credor/equilibrado).
- **Tipografia:** escala com ênfase em **tabelas densas** (a plataforma é data-heavy) e em
  **valores monetários** (tabulares, alinhados à direita).
- **Espaçamento, raio, sombra, foco** (anel de foco visível p/ a11y).
- **Tema claro e escuro** (o app já tem modo escuro — manter paridade).

### 2.3 Biblioteca de componentes (mínimo)
Cartão de KPI · tabela com ordenação/paginação/filtro · formulário com validação inline ·
**dropzone de upload** (até 500 MB, com barra de progresso) · **stepper/wizard** (fluxos
multi-etapa) · **diff viewer** (original × retificado) · modal/drawer · toast · **badge de
status** (pills: processando/processado/erro; devedor/credor; aguardando_aprovação) ·
gráficos (séries temporais de apuração, distribuição de achados) · tabela de auditoria ·
visualizador de JSON/ficha · breadcrumb · barra de busca · seletor de período (aaaa-mm) e UF.

### 2.4 Estados obrigatórios por tela (entregar TODOS)
1. **Carregando** — skeletons, não spinners vazios.
2. **Vazio / primeiro uso** — com CTA ("Envie sua primeira escrituração").
3. **Erro** — taxonomia da §6.5 (422 validação, 403 sem permissão, 503 banco indisponível,
   500 com `id` de referência).
4. **Sem permissão** — controle oculto ou desabilitado com motivo.
5. **Sucesso/conteúdo** — o estado normal.
6. **Processando assíncrono** — quando há job em background (§6.2).

### 2.5 Transversais
- **i18n pt-BR**; **moeda R$** e **datas dd/mm/aaaa**; números com separador de milhar.
- **A11y WCAG 2.1 AA**: contraste, navegação por teclado, rótulos ARIA, foco visível.
- **Responsivo**: desktop-first (ferramenta de trabalho), mas tabelas e formulários devem
  degradar para tablet. Mobile = consulta/aprovação, não edição pesada.
- **Mascaramento de PII (LGPD)**: CPF/CNPJ e dados pessoais aparecem mascarados por padrão
  (ex.: `***.456.789-**`), com "revelar" auditado só para papéis autorizados.

---

## 3. Shell do aplicativo

- **Login / sessão:** tela de autenticação (JWT via `/auth`); estados de token expirado,
  credencial inválida, e o caso "auth desligada" (ambiente de dev).
- **Top bar:** identidade do usuário + papel, alternância de tema, notificações (badge de
  aprovações pendentes em HITL), busca global.
- **Sidebar / navegação:** grupos por domínio (Jurídico, Fiscal, Operação, Administração),
  **gated por papel**.
- **Grupo "Módulos" DINÂMICO (importante):** o menu é alimentado em tempo real por
  **Server-Sent Events** (`GET /api/v1/slots/stream`). Quando um admin liga/desliga um módulo
  (`PATCH /api/v1/modules/{id}`), o item de menu **aparece/some sem recarregar a página**.
  Desenhe: o estado de transição (item entrando/saindo), o indicador "ao vivo", e o
  comportamento quando o módulo da tela aberta é desligado.

---

## 4. Mapa-mestre — tela ↔ endpoint ↔ permissão (o contrato)

> Esta é a peça central. Cada linha é uma tela (ou aba) que **deve** consumir esses endpoints.
> Prefixo de API: `/api/v1`. Papel = permissão mínima.

### 4.1 Fiscal — núcleo de valor
| Tela | Endpoints | Permissão |
|---|---|---|
| **Upload SPED** | `POST /fiscal/upload` (multipart, regime, uf, até 500 MB) → dispara job | OPERATOR |
| **Escriturações (lista)** | `GET /fiscal/apuracoes`, lista de escrituração; status via `GET /fiscal/escrituracoes/{id}` | OPERATOR/AUDITOR |
| **Escrituração (detalhe)** | `GET /fiscal/escrituracoes/{id}` (status), `/{id}/achados`, `/{id}/registros` | OPERATOR/AUDITOR |
| **Achados (validação)** | `GET /fiscal/escrituracoes/{id}/achados` (ERRO/AVISO, regra, dica) | AUDITOR |
| **Edição em lote** | `POST /fiscal/escrituracoes/{id}/registros/lote` (`dry_run` preview → real; pode exigir HITL) | OPERATOR |
| **Apuração** | `POST /fiscal/escrituracoes/{id}/apuracao` (ICMS/PIS/COFINS/ST/IPI, saldo, divergências) | OPERATOR |
| **Retificação** | `POST /retificacao/comparar`, `/validar-layout`, `/nota-correcao`; `GET /fiscal/escrituracoes/{id}/retificado` (download TXT); `POST /fiscal/escrituracoes/{id}/lote/confirmar` (pós-HITL) | OPERATOR (`retificacao:write`) |
| **Due Diligência** | `GET /fiscal/due-diligence/{cnpj}` | OPERATOR |
| **Consultoria Tributária** | `POST /fiscal/consultoria` (RAG) | OPERATOR |

### 4.2 PER/DCOMP & Transmissão (capstone — ação irreversível)
| Tela | Endpoints | Permissão |
|---|---|---|
| **PER/DCOMP** | `GET /per_dcomp/tipos`, `POST /per_dcomp/gerar`, `/gerar-de-apuracao`, `/validar` | OPERATOR (`per_dcomp:generate/validate`) |
| **Transmissão e-CAC** | `POST /transmissao/enviar`, `GET /transmissao/status/{id}`, `/historico`, `/circuit` (estado do circuit breaker) | OPERATOR (`transmissao:enviar/consultar`) |

### 4.3 Cofre & Certificado (sensível)
| Tela | Endpoints | Permissão |
|---|---|---|
| **Cofre de Credenciais** | `POST /vault/store`, `/rotate`, `GET /vault/metadata`, `DELETE /vault/delete`, `POST /vault/sign` (assina com cert A1) | ADMIN (`vault:read/write/rotate`) |

### 4.4 Analítica, Relatórios, Workbench
| Tela | Endpoints | Permissão |
|---|---|---|
| **Analytics Fiscal** | `GET /analytics/kpis`, `/apuracoes/historico`, `/achados/distribuicao`, `/anomalias`, `/retificacoes` | AUDITOR/OPERATOR |
| **Relatórios** | `GET /reports/tipos`, `/reports/gerar` (JSON ou CSV) | `reports:read` |
| **Workbench SQL** | `GET /workbench/queries`, `POST /workbench/executar`, `/validar`, `/registrar` (admin) | `workbench:execute` / `workbench:admin` |

### 4.5 Jurídico / Usuário
| Tela | Endpoints | Permissão |
|---|---|---|
| **Assistente / Tarefas** | `POST /api/v1/tasks` (+ MCP), `GET` status; `/jobs` para assíncronos | qualquer |
| **Jurisprudência** | `GET /api/v1/jurisprudencia/...` | qualquer |
| **Legislativo** | `GET /api/v1/proposicoes-legislativas`, `POST /api/v1/analises-legislativas` | qualquer |
| **Investigação 360°** | `intelligence` (GraphQL em `/api/v1/intelligence/graphql`) | `intelligence:query` |
| **Minhas consultas (histórico)** | `GET /api/v1/ledger` + `export.csv` | `ledger:read` |
| **Perfil** | `GET/PUT /api/v1/profile` | self |
| **Privacidade (LGPD)** | `/api/v1/lgpd` (consentimento, direitos do titular) | self / `lgpd:*` |

### 4.6 Administração & Configurações
| Tela | Endpoints | Permissão |
|---|---|---|
| **Aprovações (HITL)** | fila + detalhe `/api/v1/hitl`; aplica no fluxo de lote (`/fiscal/.../lote/confirmar`) | `hitl:write` |
| **Monitoramento** | `/api/v1/monitoring` (circuit breakers, profundidade de fila, saúde), `GET /health` | `monitoring:read` |
| **Auditoria (Ledger)** | `GET /api/v1/ledger` + `export.csv` | `ledger:read` |
| **Autonomia (DMN)** | `/api/v1/autonomy` (tabela de decisão, faixas de confiança) | `config:write` |
| **Treinamento** | `/api/v1/training` (sessões, feedback, A/B, métricas) | ADMIN |
| **Agentes de IA** | `GET /api/v1/agents`, `/capabilities`, `/by-capability/{c}`, `/{id}`; `PATCH /{id}/trust`; `POST /{id}/invoke` | `agents:read/manage` |
| **Gestão de Módulos** | `GET /api/v1/modules`, `/{id}`, `PATCH /{id}` (liga/desliga → SSE) | `modules:write` |
| **Usuários & RBAC** *(a criar)* | gestão de usuários e papéis (AP-08) | ADMIN |

---

## 5. Especificação por domínio (resumo do que cada tela faz)

### 5.1 Fiscal — o fio-de-ouro
O fluxo central que o design precisa tornar fluido, ponta a ponta:
**Upload → Processamento (job) → Achados → Edição em lote (dry-run) → Apuração → Retificação
→ PER/DCOMP → Transmissão.** Desenhe-o como uma jornada com **stepper/breadcrumb de progresso**
visível dentro da escrituração, para o usuário sempre saber em que etapa está e o que falta.

- **Upload SPED:** dropzone grande; campos `regime` (lucro_real/presumido/simples) e `uf`;
  validação de tipo/tamanho (≤500 MB); ao enviar, retorna `db_id` e dispara processamento
  assíncrono — leve o usuário ao **estado "processando"** (§6.2), não a um spinner morto.
- **Achados:** lista filtrável por severidade (ERRO/AVISO) e por regra; cada achado mostra
  registro, campo, descrição e **dica de correção**. É a ponte para a edição em lote.
- **Edição em lote:** seleção de registros + campos; **`dry_run` mostra o "antes/depois" e a
  revalidação simulada** antes de aplicar; se exigir aprovação, entra em HITL (§6.3) e a tela
  passa a `aguardando_aprovação`.
- **Apuração:** painel por tributo (ICMS, PIS, COFINS, ICMS-ST, IPI) com débitos, créditos,
  ajustes, saldo e **situação** (devedor/credor/equilibrado); destaque para **divergências**
  computado × declarado (E110/E210/E520/M200/M600).
- **Retificação:** **diff viewer** original × retificado; resultado de `validar-layout`;
  registro de **nota de correção**; **download do TXT retificado**. Confirmação clara: gerar
  retificadora é ato formal.

### 5.2 PER/DCOMP & Transmissão
- **PER/DCOMP:** escolher tipo (`/tipos`), gerar a partir da apuração (`/gerar-de-apuracao`),
  **validar layout** antes de transmitir; mostrar a ficha gerada de forma legível.
- **Transmissão e-CAC:** **a ação mais sensível do sistema — irreversível e federal.** Exigir
  **dupla confirmação** + resumo do que será transmitido (homologação vs produção bem
  rotulado). Acompanhar `status/{id}`; **histórico**; e expor o **estado do circuit breaker**
  (`/circuit`): quando aberto, a UI deve explicar "e-CAC indisponível, transmissão bloqueada
  temporariamente" em vez de deixar o usuário tentar.

### 5.3 Cofre & Certificado
- Nunca exibir o payload da credencial — só **metadados** (tipo, validade, último uso).
- Fluxos de **armazenar**, **rotacionar** (com histórico de timestamps) e **excluir**
  (destrutivo → confirmação forte).
- **Assinatura** (`/sign`) com certificado A1: deixar claro o que está sendo assinado.
- Estado especial: **certificado ausente/expirado** (depende do owner-action AP-05) → banner
  bloqueando PER/DCOMP/transmissão com instrução.

### 5.4 Analítica / Relatórios / Workbench
- **Analytics:** ≥5 KPIs, séries históricas de apuração, distribuição de achados, lista de
  anomalias — tudo com seletor de período/UF/tributo.
- **Relatórios:** catálogo de tipos; gerar com **download em CSV** ou visualização JSON.
- **Workbench SQL:** executar **queries pré-aprovadas parametrizadas** (não SQL livre);
  `validar` mostra por que um SQL foi rejeitado; **registrar** novo template é só admin.

### 5.5 Jurídico / Usuário
Assistente (tarefas, possivelmente assíncronas → §6.2), Jurisprudência (busca), Legislativo
(proposições + análise de IA), Investigação 360° (consulta GraphQL com expansão de QSA, PII
mascarada), Histórico (ledger + export), Perfil, Privacidade/LGPD (consentimento e direitos
do titular).

### 5.6 Administração & Configurações → ver §7.

---

## 6. Padrões transversais (desenhar como componentes reutilizáveis)

1. **Upload de arquivo grande (≤500 MB):** dropzone, validação client-side de tipo/tamanho,
   **barra de progresso de upload**, e transição para o estado de processamento.
2. **Ciclo de job assíncrono:** muitas ações não terminam na hora (processar SPED, transmitir).
   Padrão único: *submeter → tela "em andamento" com status do job (`/jobs/{id}`) → conclusão
   (sucesso/erro com motivo)*. Nunca bloquear a UI; permitir sair e voltar.
3. **HITL (aprovação humana):** quando uma ação exige aprovação, ela entra numa **fila**; o
   solicitante vê `aguardando_aprovação`; o aprovador (AUDITOR/ADMIN) vê a fila + detalhe e
   **aprova/recusa com justificativa**. Badge de pendências no shell.
4. **Tempo real (SSE):** menu de módulos (§3) e, onde fizer sentido, status. Indicar "ao vivo".
5. **Taxonomia de erro (consistente em todas as telas):**
   - `422` → validação: realçar o campo, mensagem específica.
   - `403` → sem permissão: estado §2.4.4.
   - `503` → banco/serviço indisponível: estado de manutenção, com retry.
   - `500` → erro interno: mensagem neutra + **`id` de referência** para suporte (o backend
     já devolve um id; mostre-o).
6. **Downloads:** TXT retificado e CSV de relatórios/ledger — padrão de "gerar → baixar".
7. **Confirmação de ações irreversíveis/externas:** transmissão e-CAC, exclusão de credencial,
   geração de retificadora → modal de confirmação com resumo do impacto.
8. **Mascaramento de PII** (§2.5) em toda exibição de CPF/CNPJ/dados pessoais.

---

## 7. Configurações (todas as superfícies)

O usuário pediu "todas as configurações". Mapa das telas/áreas de configuração:

| Configuração | Onde | Backend |
|---|---|---|
| **Módulos** (ligar/desligar, licenças) | Gestão de Módulos | `PATCH /api/v1/modules/{id}` + SSE |
| **Autonomia** (tabela DMN, faixas de confiança p/ acionar HITL) | Autonomia | `/api/v1/autonomy` |
| **Usuários & papéis (RBAC)** *(tela nova)* | Admin → Usuários | a implementar (AP-08) |
| **Cofre & certificado A1** | Cofre | `/vault/*` |
| **Templates de query** do workbench | Workbench (admin) | `POST /workbench/registrar` |
| **Treinamento / A-B** dos agentes | Treinamento | `/api/v1/training` |
| **Trust score** dos agentes | Agentes | `PATCH /api/v1/agents/{id}/trust` |
| **Perfil** do usuário | Perfil | `/api/v1/profile` |
| **Consentimento/LGPD** | Privacidade | `/api/v1/lgpd` |
| **Prontidão de sistema** (Postgres, MinIO, certificado, e-CAC) *(tela nova, read-only)* | Admin → Sistema | `GET /health`, `/circuit`; reflete os AP-01..06 |

---

## 8. Telas a criar vs. redesenhar (gap analysis)

**Já existem (auditar + refinar para o design system):** as 24 telas em `frontend/src/screens/`
(fiscal: dashboard, escrituração, retificação, PER/DCOMP, transmissão, due diligence,
consultoria, reports/workbench; admin: HITL, HITL detalhe, treinamento, agentes, ledger, DMN,
monitor, vault; usuário: assistente, processos, jurisprudência, legislativo, investigação 360°,
histórico, perfil, privacidade).

**Provavelmente novas (confirmar com o time antes de desenhar):**
- **Upload SPED** como tela/fluxo de primeira-classe (hoje pode estar embutido) com progresso + job.
- **Acompanhamento de jobs assíncronos** (lista/painel de processamentos em andamento).
- **Gestão de Módulos** (a UI admin do toggle; o backend existe, o front só consome via nav).
- **Usuários & RBAC** (AP-08 — não há tela).
- **Prontidão de Sistema** (read-only, reflete owner-actions AP-01..06).

---

## 9. Fluxos prioritários para prototipar (alta fidelidade)

1. **Fio-de-ouro fiscal completo:** Upload → processando → achados → corrigir em lote (dry-run
   → aplicar) → apuração com saldo → retificação (diff → validar → baixar TXT) → PER/DCOMP
   (gerar-de-apuração → validar) → transmissão e-CAC (dupla confirmação → status). É a
   demonstração principal do produto.
2. **Aprovação HITL:** operador dispara edição que exige aprovação → auditor aprova → operador
   confirma.
3. **Módulo ao vivo:** admin desliga um módulo → item some do menu de outro usuário via SSE.

---

## 10. Entregáveis esperados do designer

1. **Design system em Figma:** tokens (cor/tipo/espaço/tema claro+escuro), biblioteca de
   componentes (§2.3) com todos os estados (§2.4).
2. **Telas** de cada item do mapa §4, em todos os estados, com anotações de a11y.
3. **Protótipo navegável** dos 3 fluxos do §9.
4. **Tabela de binding** (entregável-chave para os devs): para cada tela/componente →
   endpoint(s), método, parâmetros, permissão, e estados de erro mapeados. Use o §4 como base
   e detalhe os contratos de request/response com o time de backend.
5. **Convenção de `screen_id`:** o frontend mapeia rota de módulo → tela por um `screen_id`
   (ex.: `assistant`, `due-diligence`, `consultoria`). Toda tela nova precisa de um `screen_id`
   acordado com o dev, para entrar no sistema de slots dinâmicos.
6. **Redlines/specs** de espaçamento e comportamento responsivo.

---

### Apêndice — fonte da verdade técnica
- Contrato vivo da API: **OpenAPI/Swagger** do backend (FastAPI expõe `/docs`). Use-o para os
  esquemas exatos de request/response de cada endpoint do §4.
- Papéis/permissões: `src/api/rbac.py` (ADMIN, OPERATOR, AUDITOR, READONLY).
- Cliente HTTP do front: `frontend/src/api/client.js` (centraliza auth/headers — toda tela
  nova consome por ele).
- Navegação e slots dinâmicos: `frontend/src/App.jsx` + `GET /api/v1/slots/stream` (SSE).
