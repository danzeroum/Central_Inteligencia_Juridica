# Camada BPM/DMN — Decisões de Negócio Externalizadas

> Frente F4 do [Plano Mestre](PLANO_MESTRE_MELHORIAS.md). Separa **regras de
> negócio** (que mudam com leis/súmulas) do **código**, codificando-as como dados
> e mapeando-as à infraestrutura já existente. Não recria nada que já funciona —
> documenta e externaliza.

## DMN-02 — Roteamento de Fonte de Dados (regra CJ-001)

**Regra arquitetural não-negociável:**

> 🚨 O LLM **analisa**. A API real **fornece os dados**. Nunca o contrário.

- **Fonte da verdade (dados):** [`config/governance/data_sources.yaml`](../config/governance/data_sources.yaml)
- **Engine (aplicação):** [`src/governance/data_source_policy.py`](../src/governance/data_source_policy.py)
- **Guardrail:** `SafetyProtocol.enforce_data_source(data_type, source)` levanta
  `DataSourceViolation` (hard block) se o LLM for fonte de um dado **crítico**.

| Tipo de dado | Fonte autorizada | Papel do LLM | Crítico | Cache TTL |
|---|---|---|---|---|
| `legislacao` | Planalto / LexML | análise | ✅ | 7d |
| `jurisprudencia` | CNJ DataJud (ADR-013) | sumarização | ✅ | 24h |
| `indice_economico` | BCB / IBGE | — | ✅ | 1h |
| `honorarios` | Tabela OAB | — | ✅ | 30d |
| `prazo_processual` | CPC/CLT (base local) | — | ✅ | ∞ |
| `dado_mercado_financeiro` | Alpha Vantage / Finnhub | nunca | ✅ | 5min |
| `interpretacao` | LLM | exclusivo | ❌ | n/a |

Adicionar/alterar uma política = editar o YAML (zero mudança de código).

## DMN-03 — Tolerância a Falhas (já implementada)

A DMN-03 (o que fazer quando uma fonte falha) **não é nova** — é realizada pela
infraestrutura existente. Esta seção apenas a mapeia:

| Elemento da DMN-03 | Realização concreta no código |
|---|---|
| Estados CLOSED → OPEN → HALF-OPEN | [`src/tools/circuit_breaker.py`](../src/tools/circuit_breaker.py) (`CircuitBreaker`) |
| Retry com backoff exponencial | `tenacity` em `src/tools/tribunal_api_adapter.py` |
| Fallback gracioso + `source` (real_api/simulated) | ADR-008; `DataJudClient` (ADR-013) |
| Abertura → usar cache/mock + disclaimer | `_mock_result` / `_get_mock_*` dos adapters |

Parâmetros do circuit breaker são configuráveis por ambiente
(`*_CB_FAILURE_THRESHOLD`, `*_CB_TIMEOUT_SECONDS`, `DATAJUD_CB_*`).

## DMN-01 — Seleção de Template de Peça (futuro)

Depende das skills de geração de peças (Frente F.2). Será externalizada no mesmo
padrão (YAML + engine) quando aquela frente for implementada.

## Process Mining (XES) — follow-up

Os logs estruturados com `correlation_id` (`src/utils/logging_config.py`) e o
`DecisionLedger` já existem. Emitir eventos compatíveis com **XES** sobre o ledger
(para mineração com ProM/Celonis) é um passo posterior, de baixo esforço.

## Referências

- [Plano Mestre — §5 Frente D](PLANO_MESTRE_MELHORIAS.md)
- ADR-008 (APIs reais / fallback), ADR-013 (DataJud)
