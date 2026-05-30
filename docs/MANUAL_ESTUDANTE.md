# Manual do Estudante de Direito — Central de Inteligência Jurídica

> Um guia prático para explorar a plataforma. A Central é um sistema de
> **agentes jurídicos de IA** que consultam tribunais, classificam a sua dúvida
> e roteiam para o agente especializado — sempre com **supervisão humana** nas
> ações sensíveis. Este manual cobre **tudo o que a ferramenta faz hoje**.

---

## 1. Antes de começar: o que é (e o que não é)

- **É** um assistente que ajuda a **pesquisar** status de processos, movimentações,
  jurisprudência comparada entre tribunais e o cenário legislativo.
- **Não** substitui aconselhamento jurídico. Toda resposta é **gerada por IA** e,
  quando puder virar uma **ação processual** (ex.: peticionar), entra numa **fila
  de revisão humana** antes de qualquer execução. Guarde essa ideia — ela aparece
  na interface e é o coração da ferramenta.

A plataforma tem **dois ambientes**, alternáveis no topo da tela:

| Ambiente | Para quê | Quem usa |
|---|---|---|
| **Espaço de Trabalho** | Pesquisar e consultar (seu dia a dia) | Advogado / consulente |
| **Administração** | Governar a IA: aprovar ações, auditar, monitorar | Operador / compliance |

Como estudante, você usará bastante o **Espaço de Trabalho** — mas vale explorar a
**Administração** para entender *como a responsabilidade humana sobre a IA é
controlada* (tema cada vez mais cobrado, inclusive pela LGPD).

---

## 2. Acessando a ferramenta

1. Suba o backend e a interface (ver `README.md`):
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && npm run build && cd ..
   uvicorn src.api.main:app --reload --port 8000
   ```
2. Abra **`http://localhost:8000/app`**.
3. Na tela de login, clique em **“Entrar como Usuário”** (o e-mail já vem
   preenchido para demonstração) ou **“Entrar como Admin”**.
4. Use o seletor **Usuário / Admin** no canto superior direito para alternar a
   qualquer momento.

---

## 3. Espaço de Trabalho (seu dia a dia)

### 3.1 Assistente 🟦 *(chat)*
O ponto de entrada. Descreva sua dúvida em **linguagem natural** e o sistema:
- **classifica a intenção** (ex.: “comparação de jurisprudência”) e mostra a
  **confiança** e os **tribunais** detectados;
- exibe o **roteamento** (Supervisor → agentes especializados);
- traz um **aviso de IA** e informa **quantas solicitações estão na fila de
  revisão humana** naquele momento.

Sugestões prontas para experimentar (clicáveis na tela inicial):
- *“O TJSP está disponível para consultas agora?”* → checagem de status
- *“Últimas movimentações do processo 1234567‑89.2024.8.26.1234”*
- *“Comparar jurisprudência sobre LGPD no STF e no TJSP”*
- *“Decisões recentes do STJ sobre dano moral em relações de consumo”*

> 💡 **Dica de estudo:** clique em **“Ver payload técnico”** em cada resposta para
> ver como a IA estruturou a consulta — ótimo para entender *como* a máquina
> interpretou seu pedido.

### 3.2 Processos
Digite um **número único CNJ** e clique em **Consultar**. O tribunal é **inferido
automaticamente** do próprio número (ex.: `.8.26.` → TJSP, `.8.13.` → TJMG). A tela
mostra os dados do processo e a **linha do tempo de movimentações**.

### 3.3 Jurisprudência
Pesquise um **tema** e selecione **quais tribunais comparar** (STF, STJ, TJSP,
TJMG, TJRS, TJRJ, TST). A ferramenta consulta os agentes de cada tribunal e
apresenta o entendimento **lado a lado** — útil para identificar **convergências
e divergências** entre cortes.

### 3.4 Legislativo
Pesquise um **tema** (ex.: “inteligência artificial”) e a ferramenta consulta a
**Câmara dos Deputados** trazendo as **proposições** relacionadas, mais uma
**análise de cenário assistida por IA** sobre tendências e impactos.

### 3.5 Minhas Consultas *(histórico)*
Lista suas interações recentes com **status**: *Concluída* ou
**“Em revisão humana”**. Consultas que geraram uma ação sensível aparecem
destacadas — clicar nelas leva você à fila de aprovações, mostrando na prática o
fluxo *Human‑in‑the‑Loop*.

---

## 4. Administração (entendendo a governança da IA)

Mesmo que você não vá operar essa área, ela é um **laboratório didático** sobre
**responsabilização de IA**.

### 4.1 Aprovações · Human‑in‑the‑Loop ⭐
A tela mais importante para entender o conceito. Quando um agente propõe uma ação
sensível (ex.: **protocolar petição**), ela **não é executada sozinha** — fica
aqui aguardando um humano decidir **Aprovar · Modificar · Rejeitar**:
- a ação aparece em **linguagem jurídica** (não em JSON), com o **motivo da
  revisão** (ex.: “ação crítica” ou “consenso abaixo do limiar”);
- ações **críticas** exigem marcar *“Revisei o conteúdo”* antes de aprovar
  (fricção proporcional ao risco);
- **Modificar** abre um editor para ajustar os parâmetros antes de aprovar;
- **Rejeitar** exige **justificativa**, que vai para a trilha de auditoria;
- a fila é **em tempo real** (WebSocket) e acessível por teclado (`A`/`R`/`M`).

### 4.2 Auditoria · *Decision Ledger*
Trilha **imutável**: quem decidiu o quê, quando e sob qual regra. Pode **filtrar
por agente** e **exportar em CSV**. É a base de **conformidade com a LGPD** e de
prestação de contas — exatamente o tipo de registro que um advogado pediria.

### 4.3 Autonomia · Regras (DMN)
Mostra **quando um humano precisa decidir**, em forma de **tabela de decisão**
editável (sem mexer no código). Você vê e ajusta os **limiares**: ação crítica
sempre revisa; consenso abaixo de 0,60 revisa; agente “restrito” revisa. Excelente
para entender que a regra de governança é **explícita e auditável**.

### 4.4 Agentes
Catálogo dos **agentes especializados** (Supervisor, TJSP, STF, TJMG…), cada um
com seu **nível de confiança (trust score)** e **nível de autonomia** (Pleno /
Supervisionado / Restrito) e suas **capacidades**. Dá para **invocar um agente
diretamente** com uma tarefa de teste.

### 4.5 Treinamento
Mostra como os agentes **melhoram com o feedback** das decisões humanas:
estatísticas, histórico de sessões e o botão **“Treinar agora”** (assíncrono, com
barra de progresso).

### 4.6 Monitoramento
Saúde do sistema: **circuit breakers** (resiliência das APIs dos tribunais),
**profundidade da fila HITL** e **canal de comunicação entre agentes (A2A)**.

---

## 5. Roteiro sugerido (15 minutos)

1. **Assistente** → clique na sugestão de *comparar jurisprudência LGPD* e observe
   a intenção detectada + roteamento.
2. **Jurisprudência** → compare STF × TJSP no mesmo tema.
3. **Processos** → consulte o número de exemplo e leia a linha do tempo.
4. **Legislativo** → pesquise “inteligência artificial” e leia a análise de IA.
5. **Minhas Consultas** → veja o histórico e o status “em revisão humana”.
6. Troque para **Admin → Aprovações** e veja como uma ação sensível espera decisão
   humana; depois abra **Auditoria** para ver o registro da decisão.

---

## 6. Três lições que a ferramenta ensina

1. **IA jurídica é assistiva, não decisória.** Toda ação sensível passa por um
   humano responsável.
2. **Rastreabilidade importa.** Cada decisão fica registrada (quem, o quê, quando,
   por qual regra) — alinhado à LGPD.
3. **A regra de autonomia é transparente.** “Quando revisar” é uma tabela
   auditável, não uma caixa-preta.

> ⚠️ **Aviso:** plataforma educacional/demonstrativa. As respostas de IA podem
> conter imprecisões e **não substituem** a análise de um profissional habilitado.
