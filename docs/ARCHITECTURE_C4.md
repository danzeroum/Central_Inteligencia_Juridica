# Arquitetura (C4 + 4+1) — Central de Inteligência Jurídica

Documentação arquitetural nos quatro níveis do modelo **C4** (Contexto,
Contêiner, Componente, Código) mais diagramas de **sequência** dos cenários-chave
(visão 4+1). Os diagramas usam Mermaid (renderizam no GitHub).

> Visão de alto nível e tabela de componentes: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## Nível 1 — Contexto

Quem usa o sistema e com quais sistemas externos ele conversa.

```mermaid
graph TB
    Adv["👤 Advogado / Consulente<br/>(pesquisa jurídica)"]
    Op["👤 Operador HITL / Compliance<br/>(aprova ações, audita)"]
    CIJ["⚖️ Central de Inteligência Jurídica<br/>(plataforma multiagente + HITL)"]
    Trib["🏛️ APIs de Tribunais<br/>(TJSP, TJMG, STF…)"]
    Camara["🏛️ API Câmara dos Deputados"]
    LLM["🤖 LLM (OpenAI/Ollama)<br/>classificação de intenção"]

    Adv -->|consulta em linguagem natural| CIJ
    Op -->|Aprovar/Modificar/Rejeitar| CIJ
    CIJ -->|processos/jurisprudência| Trib
    CIJ -->|projetos de lei| Camara
    CIJ -->|classifica intenção| LLM
```

---

## Nível 2 — Contêineres

Unidades executáveis/implantáveis e seus armazenamentos.

```mermaid
graph TB
    subgraph Browser["Navegador"]
        SPA["SPA React+Vite<br/>(/app)"]
    end
    subgraph Server["FastAPI (uvicorn)"]
        API["API REST + WebSocket<br/>/api/v1/*"]
        Static["StaticFiles<br/>serve a SPA"]
    end
    subgraph Core["Núcleo de Agentes (in-process)"]
        ORCH["Supervisor / UnifiedOrchestrator"]
        HITL["HITLQueue + ProgressiveAutonomy"]
    end
    subgraph Data["Estado / Dados"]
        REDIS[("Redis<br/>cache + A2A")]
        CHROMA[("ChromaDB<br/>VectorMemory")]
        LEDGER[("Decision Ledger<br/>JSON em logs/")]
        PROM[("Prometheus")]
    end

    SPA -->|fetch /api/v1, WS| API
    Static --> SPA
    API --> ORCH
    API --> HITL
    ORCH --> REDIS
    ORCH --> CHROMA
    HITL --> LEDGER
    API --> PROM
```

> **Nota:** Redis e ChromaDB são opcionais — há fallback in-memory (A2A/cache) e o
> VectorMemory degrada graciosamente sem ChromaDB.

---

## Nível 3 — Componentes (API + núcleo de processamento)

```mermaid
graph LR
    EP["Endpoints<br/>(tasks, hitl, ledger,<br/>autonomy, monitoring,<br/>agents, training, a2a)"]
    SUP["SupervisorAgent"]
    IC["IntentClassifier<br/>(LLM + fallback)"]
    TID["TribunalIdentifier<br/>(YAML)"]
    TA["TribunalAgent(s)"]
    WCE["WeightedConsensusEngine"]
    PAM["ProgressiveAutonomyManager"]
    Q["HITLQueue (WS)"]
    LG["DecisionLedger"]
    CB["CircuitBreaker + CacheManager"]
    REG["AgentRegistry (MCP)"]
    A2A["A2AChannel"]

    EP --> SUP
    EP --> Q
    EP --> REG
    SUP --> IC --> TID
    SUP --> TA
    SUP --> WCE
    SUP --> PAM
    PAM -->|ação sensível| Q
    Q -->|decisão| LG
    TA --> CB
    SUP <--> A2A
    TA <--> A2A
```

---

## Nível 4 — Código (subsistema de decisão HITL)

```mermaid
classDiagram
    class ProgressiveAutonomyManager {
        +execute_with_autonomy(agent, action)
        -_requires_human_review(agent, action, consensus) bool
        -_get_autonomy_level(agent) str
        +update_config(...)
        +update_trust_score(agent, delta) float
    }
    class HITLQueue {
        +add_request(agent, action, context) HITLRequest
        +wait_for_decision(request_id)
        +record_decision(request_id, approved, modifications, feedback) bool
        +get_pending_requests()
    }
    class HITLRequest {
        request_id, agent, action, context
        status, decision, decided_by, decided_at
    }
    class DecisionLedger {
        +log_decision(agent_type, decision_type, metadata)
        +get_entries(agent_type, decision_type, limit)
    }
    ProgressiveAutonomyManager --> HITLQueue : solicita aprovação
    HITLQueue --> HITLRequest : gerencia
    HITLQueue --> DecisionLedger : registra decisão
```

---

## 4+1 — Cenário A: consulta com revisão humana (HITL)

```mermaid
sequenceDiagram
    participant U as Advogado (SPA)
    participant API as FastAPI
    participant SUP as Supervisor
    participant PAM as Autonomy
    participant Q as HITLQueue
    participant Op as Operador (SPA)
    participant L as Ledger

    U->>API: POST /api/v1/tasks
    API->>SUP: process_task()
    SUP->>PAM: execute_with_autonomy(ação)
    PAM->>PAM: _requires_human_review? (crítica/consenso/autonomia)
    PAM->>Q: add_request()
    Q-->>Op: WebSocket "new_request"
    Op->>API: POST /api/v1/hitl/decisions (aprovar)
    API->>Q: record_decision()
    Q->>L: log_decision() (auditoria)
    Q-->>PAM: decisão liberada
    PAM-->>U: ação executada
```

## 4+1 — Cenário B: jurisprudência multi-tribunal (consenso)

```mermaid
sequenceDiagram
    participant U as Usuário
    participant SUP as Supervisor
    participant IC as IntentClassifier
    participant T1 as Agente STF
    participant T2 as Agente TJSP
    participant WCE as Consenso

    U->>SUP: "comparar jurisprudência LGPD STF e TJSP"
    SUP->>IC: classify() -> operacao=comparison, tribunais=[STF,TJSP]
    par Consultas paralelas (asyncio.gather)
        SUP->>T1: execute_task()
        SUP->>T2: execute_task()
    end
    T1-->>SUP: proposta + confiança
    T2-->>SUP: proposta + confiança
    SUP->>WCE: reach_consensus(propostas)
    WCE-->>SUP: decisão + consensus_strength + dissidências
    SUP-->>U: resultado comparado
```

---

## Referências de código

| Elemento | Arquivo |
|---|---|
| Endpoints | `src/api/main.py`, `src/api/{hitl,training,ledger,autonomy,monitoring}_endpoints.py` |
| Supervisor / Tribunal | `src/agents/{supervisor,tribunal}_agent.py` |
| Intenção / Roteamento | `src/routing/{intent_classifier,tribunal_identifier,learning_router}.py` |
| Consenso | `src/consensus/weighted_voting.py` |
| HITL / Autonomia | `src/hitl/{hitl_queue,progressive_autonomy}.py` |
| Auditoria | `src/utils/ledger.py` |
| Resiliência | `src/tools/circuit_breaker.py`, `src/utils/cache_manager.py` |
| MCP / A2A | `src/protocols/{agent_card,a2a_channel}.py` |
| Frontend | `frontend/` (build em `src/api/static/spa`) |
