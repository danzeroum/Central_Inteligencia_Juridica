# Arquitetura — Central de Inteligencia Juridica

## Visao Geral

Plataforma multiagente para automacao de consultas juridicas tribunais brasileiros.

## Componentes Principais

### Agentes

| Agente | Responsabilidade |
|---|---|
| **SupervisorAgent** | Orquestra tarefas, identifica tribunais, delega |
| **TribunalAgent** | Operacoes por tribunal (status, processo, movimentacoes) |
| **ArchitectAgent** | Chain-of-Thought para planejamento |

### Infraestrutura

| Componente | Responsabilidade |
|---|---|
| **CacheManager** | Cache com Circuit Breaker (Redis + memoria) |
| **DecisionLedger** | Registro persistente de decisoes |
| **InputSanitizer** | Protecao contra XSS e SQL Injection |
| **VectorMemory** | Memoria vetorial com ChromaDB |

### Consenso e Autonomia

| Componente | Responsabilidade |
|---|---|
| **WeightedConsensusEngine** | Consenso ponderado por expertise |
| **ProgressiveAutonomyManager** | Autonomia progressiva com HITL |

## Diagrama de Componentes

```mermaid
graph TB
    subgraph API["API Layer"]
        FastAPI[FastAPI]
    end

    subgraph Agents["Agent Layer"]
        SUP[SupervisorAgent]
        TRIB[TribunalAgent]
        ARCH[ArchitectAgent]
    end

    subgraph Infra["Infrastructure"]
        CACHE[CacheManager]
        LEDGER[DecisionLedger]
        SANIT[InputSanitizer]
        VECMEM[VectorMemory]
    end

    subgraph Consensus["Consensus & HITL"]
        WCE[WeightedConsensus]
        PAM[ProgressiveAutonomy]
    end

    subgraph External["External Services"]
        REDIS[(Redis)]
        CHROMA[(ChromaDB)]
        PROM[(Prometheus)]
    end

    FastAPI --> SANIT
    FastAPI --> SUP
    SUP --> TRIB
    SUP --> ARCH
    SUP --> WCE
    SUP --> PAM
    SUP --> LEDGER
    TRIB --> CACHE
    TRIB --> VECMEM
    CACHE --> REDIS
    VECMEM --> CHROMA
