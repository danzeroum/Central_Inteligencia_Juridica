# 🧭 Fluxos de Usuário

Fluxos reais da SPA (`/app`), organizados pelos dois ambientes da plataforma.
Para o detalhamento de cada tela, veja o [Manual do Estudante](../MANUAL_ESTUDANTE.md).

## Acesso
1. Abrir `http://localhost:8000/app`.
2. Login → **Entrar como Usuário** ou **Entrar como Admin**.
3. Alternar a qualquer momento pelo seletor **Usuário / Admin** no topo.

## Espaço de Trabalho (consulente/advogado)

### Consulta assistida (Assistente)
1. Descrever a dúvida em linguagem natural.
2. Ver **intenção detectada**, tribunais e confiança.
3. Ler a resposta com **aviso de IA** e estado da **fila de revisão humana**.
4. (Opcional) expandir **"Ver payload técnico"** para inspecionar a classificação.

### Consulta de processo
1. Informar o número CNJ → **Consultar**.
2. Tribunal **inferido automaticamente** do número.
3. Ver dados do processo e a **linha do tempo de movimentações**.

### Jurisprudência comparada
1. Informar tema + selecionar tribunais.
2. Ver o entendimento **lado a lado** entre as cortes.

### Histórico (Minhas Consultas)
1. Listar interações recentes com **status** (*Concluída* / *Em revisão humana*).
2. Clicar numa consulta "em revisão humana" leva à fila de aprovações.

## Administração (operador/compliance)

### Aprovação Human-in-the-Loop
1. Receber, em **tempo real** (WebSocket), uma ação sensível proposta por um agente.
2. Ler a ação em **linguagem jurídica** e o **motivo da revisão**.
3. Decidir **Aprovar** (crítica exige confirmar "Revisei") · **Modificar** · **Rejeitar** (com justificativa).
4. A decisão é registrada no **Decision Ledger** (auditoria).

### Auditoria, Autonomia e Monitoramento
1. **Auditoria:** filtrar a trilha imutável e **exportar CSV** (LGPD).
2. **Autonomia (DMN):** ajustar os limiares de "quando revisar" sem tocar no código.
3. **Monitoramento:** acompanhar circuit breakers, fila HITL e canal A2A.
