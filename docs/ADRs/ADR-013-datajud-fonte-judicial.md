# ADR-013 — CNJ DataJud como fonte oficial de dados judiciais

## Status
Aceito (2026-06-04)

## Contexto

A Frente F.1 (busca de jurisprudência/jurimetria) exige uma fonte de dados
judiciais reais. O estado anterior:

- `src/agents/agente_jurisprudencia.py` era um worker de fila Redis isolado que
  retornava uma **simulação hardcoded** — não conectado ao fluxo de agentes.
- A integração "real" do ADR-008 (`tribunal_api_adapter.py` / `tribunal_api_client.py`)
  aponta para **APIs proprietárias por tribunal** (`api.tjsp.jus.br`,
  `api5.tjmg.jus.br`), que cobrem apenas TJSP/TJMG, exigem autenticação distinta
  por tribunal e estão "aguardando token". Não há busca de jurisprudência.

## Decisão

Adotar a **API Pública do CNJ DataJud** (`api-publica.datajud.cnj.jus.br`) como
fonte oficial de metadados processuais para busca/jurimetria.

Vantagens sobre as APIs proprietárias por tribunal:
- **Cobertura:** 90+ tribunais com uma **única chave** (vs. 2 tribunais).
- **Oficial e estável:** mantida pelo CNJ; contrato ElasticSearch documentado.
- **Query DSL completa:** `bool`/`range`/`terms` + paginação `search_after`.

### Componentes (aditivos — não alteram o adapter atual)

| Arquivo | Responsabilidade |
|---|---|
| `src/services/datajud_query_builder.py` | Builder fluente do corpo `_search` (assuntos, grau, datas, município IBGE, movimentos, paginação). |
| `src/services/datajud_client.py` | Cliente **assíncrono** (`httpx.AsyncClient`) com fallback gracioso, reaproveitando `CircuitBreaker`. Header `Authorization: APIKey <chave>`. |
| `src/services/datajud_schemas.py` | Schemas Pydantic tolerantes (`extra="allow"`) — `DataJudProcesso`, `DataJudSearchResult`. |
| `src/services/datajud_service.py` | Operações de alto nível + registro de ferramentas MCP (`datajud_buscar_processo`, `datajud_buscar_por_assunto`, `datajud_monitorar_atualizacoes`). |

### Conformidade com o ADR-008
Mantém o padrão tentativa-real → fallback-mock, `source` no resultado
(`real_api` | `simulated`), reúso de `CircuitBreaker`. A chave vem de
`DATAJUD_API_KEY` (env); sem ela, degrada para mock — dev/CI não dependem de rede.

## Limites e arquitetura de duas fontes (LGPD)

A API Pública do DataJud entrega **apenas metadados de capa** — nomes das partes
e textos de decisões são **mascarados** por força da LGPD. Portanto:

> 🚨 DataJud = metadados/jurimetria. O **texto integral** (ementa/acórdão) vem de
> outra fonte (RAG sobre diários oficiais/PJe), nunca do LLM (regra CJ-001).

## Consequências

### Positivas
- Capacidade real de jurimetria por assunto/grau/tribunal, com fallback 100%.
- Async consistente com o restante do sistema; testes determinísticos via `respx`.

### Negativas / dívida assumida
- O `TribunalAPIAdapter` legado (status/processo TJSP/TJMG, **síncrono**) **permanece
  intacto** nesta frente para não desestabilizar seus testes. Migrá-lo para
  delegar ao backend DataJud (e unificar em async) é um **follow-up**.
- A camada de texto integral (RAG diários/PJe) é trabalho posterior.

## Configuração

```bash
DATAJUD_API_KEY=<chave pública do DataJud>   # sem ela → mock
DATAJUD_CB_FAILURE_THRESHOLD=3               # opcional
DATAJUD_CB_TIMEOUT_SECONDS=30                # opcional
```

## Validação
- `tests/integration/test_datajud.py` — builder, sucesso real (mock respx),
  fallback sem chave, fallback em erro HTTP, abertura do circuit breaker,
  serviço e registro de tools MCP (8 testes).
- Suíte completa verde; `black`/`bandit` ok.

## Referências
- DataJud — API Pública: https://datajud-wiki.cnj.jus.br/api-publica/
- ADR-008 (APIs reais / Tool Use + fallback), ADR-005 (paralelização).
