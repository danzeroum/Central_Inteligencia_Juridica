# ADR-010: Resolução do Paradoxo do Orquestrador

## Status
Substituída na prática (ver nota de conformidade — 2026-05)

> ⚠️ **Nota de conformidade (sync com o código — D01).** A decisão original abaixo
> (mover `UnifiedOrchestrator` e componentes avançados para um diretório
> `experimental/`) **não foi implementada** e o rumo do projeto foi o oposto:
> - **Não existe** diretório `experimental/` no repositório.
> - O **`UnifiedOrchestrator` está EM PRODUÇÃO** em
>   `src/orchestration/unified_orchestrator.py` — é instanciado pela API
>   (`src/api/main.py`) e atende o endpoint `/api/v1/tasks/advanced`.
> - `AdaptivePlanner`, `WeightedConsensusEngine` e `LearningRouter` permanecem
>   sob `src/` (não isolados).
>
> Ou seja: em vez de isolar o orquestrador avançado, ele foi promovido e
> integrado. O texto abaixo é mantido como registro histórico.

## Contexto

Durante análise crítica pós-certificação do MVP, identificou-se a coexistência de dois mecanismos de orquestração com responsabilidades sobrepostas:

1. **SupervisorAgent** (`src/agents/supervisor_agent.py`)
   - Arquitetura simples e pragmática (supervisor-delegate pattern)
   - Utilizado em 100% dos testes de integração
   - Validado pelo MVP certificado
   - 198 linhas, foco claro

2. **UnifiedOrchestrator** (`src/orchestration/unified_orchestrator.py`)
   - Arquitetura complexa com 8 subsistemas integrados
   - Utilizado apenas em 1 teste isolado (`test_unified_orchestration.py`)
   - Não integrado ao fluxo principal da aplicação
   - 163 linhas, escopo ambicioso

**Problema identificado:** Ambiguidade arquitetural cria:
- **Débito técnico oculto** - código não utilizado aumenta complexidade
- **Confusão para novos desenvolvedores** - qual orquestrador usar?
- **Risco de manutenção** - duas implementações para evoluir

## Decisão

**Mover `UnifiedOrchestrator` e componentes avançados para diretório `experimental/`** e documentar caminho de evolução futuro.

### Estrutura proposta:

```
src/
├── agents/
│   ├── supervisor_agent.py          # PRODUCTION (ativo)
│   └── tribunal_agent.py
├── orchestration/                    # MOVIDO PARA:
└── experimental/                     # ← NOVO
    ├── README.md                     # Roadmap de integração
    ├── orchestration/
    │   └── unified_orchestrator.py
    ├── planning/
    │   ├── adaptive_planner.py
    │   └── hierarchical_planner.py
    ├── consensus/
    │   └── weighted_voting.py
    ├── routing/
    │   └── learning_router.py
    └── tests/
        └── test_experimental_features.py
```

### Justificativa:

1. **Princípio Crisp Pragmatist:** "Disciplina mínima, valor máximo"
   - `SupervisorAgent` entrega 100% do valor do MVP
   - `UnifiedOrchestrator` adiciona complexidade sem valor imediato

2. **Caminho de evolução claro:**
   - Fase atual: MVP em produção com `SupervisorAgent`
   - Próxima fase: A/B testing de features do `UnifiedOrchestrator`
   - Fase futura: Migração gradual quando valor for comprovado

3. **Redução de risco:**
   - Código experimental isolado não polui arquitetura de produção
   - Testes experimentais não afetam CI/CD principal
   - Refatorações futuras têm escopo definido

## Alternativas Consideradas

### Opção A: Integrar UnifiedOrchestrator imediatamente
**Rejeitada:** Requer reescrever todos os testes, aumenta P95 latency, over-engineering para MVP.

### Opção B: Deletar UnifiedOrchestrator
**Rejeitada:** Perda de código de qualidade que representa roadmap futuro.

### Opção C: Manter status quo
**Rejeitada:** Perpetua débito arquitetural identificado.

## Consequências

### Positivas
- ✅ Arquitetura de produção clara e sem ambiguidade
- ✅ Código experimental preservado para evolução futura
- ✅ Redução de complexidade cognitiva para novos desenvolvedores
- ✅ CI/CD mais rápido (menos testes na suite principal)

### Negativas
- ⚠️ Features avançadas (adaptive planning, consensus, learning) não disponíveis imediatamente
- ⚠️ Requer documentação clara do roadmap experimental

### Mitigações
- 📝 Criar `experimental/README.md` com cronograma de integração
- 🧪 Manter testes experimentais em CI separado (opcional)
- 📊 Definir métricas de sucesso para promover features experimentais

## Roadmap de Integração

### Fase 1 (Q1 2026): Foundation
- [ ] Resolver issues P0 do MVP (multi-tribunal, circuit breaker)
- [ ] Coletar métricas de produção do `SupervisorAgent`

### Fase 2 (Q2 2026): A/B Testing
- [ ] Feature flag para `AdaptivePlanner` em casos de falha
- [ ] Comparar performance vs planejamento estático
- [ ] Métrica de sucesso: redução de 20% em replanning

### Fase 3 (Q3 2026): Consensus Gradual
- [ ] Integrar `WeightedConsensusEngine` para decisões críticas
- [ ] Testar em shadow mode (log decisões sem afetar produção)
- [ ] Métrica de sucesso: 90% de acordo com decisões manuais

### Fase 4 (Q4 2026): Learning Loop
- [ ] Ativar `LearningRouter` para otimização de roteamento
- [ ] Coletar feedback de precisão de identificação de tribunal
- [ ] Métrica de sucesso: aumento de 15% em accuracy

## Validação

- [x] Arquiteto aprovou estrutura experimental
- [x] Dev team concordou com isolamento de código
- [x] Ops validou que não impacta deployment atual

## Referências

- Análise crítica pós-certificação (2025-09-30)
- Princípio Crisp Pragmatist
- Martin Fowler - "Feature Toggles" (featuretoggle.org)
