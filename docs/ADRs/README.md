# Architecture Decision Records (ADRs)

Registros de decisões arquiteturais da Central de Inteligência Jurídica.
Cada ADR é um documento imutável que captura o **contexto**, a **decisão** e as
**consequências** de uma escolha relevante. Use o [`ADR-Template.md`](ADR-Template.md)
para novos registros.

## Índice canônico

| # | Título | Status |
|---|--------|--------|
| [001](ADR-001-performance-target.md) | Meta de performance (P95) | Aceito |
| [002](ADR-002-database-choice.md) | Escolha de persistência | Aceito |
| [003](ADR-003-api-design-standards.md) | Padrões de design da API (`/api/v1`) | Aceito |
| [004](ADR-004-api-design.md) | Design da API (detalhe) | Aceito |
| [005](ADR-005-parallelization.md) | Execução paralela multi-tribunal (`asyncio.gather`) | Aceito |
| [007](ADR-007-vector-memory.md) | Memória vetorial (ChromaDB) | Aceito |
| [008](ADR-008-real-apis.md) | Integração com APIs reais de tribunais | Aceito |
| [010](ADR-010-orquestrador.md) | Orquestrador unificado + Circuit Breaker | Aceito |
| [011](ADR-011-sandbox-decision.md) | Decisão de sandbox de execução | Aceito |
| [012](ADR-012-numpy-constraint.md) | Restrição NumPy < 2.0 (compat. ChromaDB) | Aceito |

> **Nota sobre numeração:** os números **006** e **009** não possuem ADR emitido —
> antigos rascunhos genéricos ("Raciocínio" e "Resiliência") foram removidos por
> serem boilerplate de metodologia, não decisões específicas do projeto. O tema de
> raciocínio (Chain-of-Thought / `ArchitectAgent`) está descrito em
> [`../ARCHITECTURE_C4.md`](../ARCHITECTURE_C4.md); resiliência (Circuit Breaker)
> está coberta na ADR-010. Gaps em numeração de ADR são normais e preservam o
> histórico.
