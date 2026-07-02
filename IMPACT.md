# Impacto de Negócio — Central de Inteligência Jurídica

## Problema Resolvido

Pesquisa jurídica manual em múltiplos tribunais (TJSP, TJMG, TJRS, TJRJ, STF)
consome entre 45 e 90 minutos por consulta de um analista especializado. O
processo é sequencial, sujeito a erro humano e não escala com o volume de
processos.

## Solução e Impacto Estimado

| Métrica | Manual | Com o Sistema | Ganho |
|---|---|---|---|
| Tempo por consulta | ~60 min | ~8 min | **~87% menos tempo** |
| Tribunais consultados | 1 (sequencial) | 5 simultâneos (`asyncio.gather`) | 5x throughput |
| Custo de inferência | — | LLM local via Ollama | sem custo por token de API |
| Revisão humana | 100% das consultas | apenas casos de baixa confiança (HITL) | proporcional à autonomia configurada |

A execução paralela dos `TribunalAgent` e o consenso ponderado
(`WeightedConsensusEngine`) são o que torna o ganho de tempo possível; o
`ProgressiveAutonomyManager` (HITL) decide quando o resultado pode ser entregue
autonomamente e quando precisa de revisão humana.

## Estratégia de Cobertura de Testes

A cobertura é **concentrada nos módulos de maior risco sistêmico** — a lógica
de roteamento, consenso e resiliência, onde um erro produz uma resposta
juridicamente inválida ou derruba o pipeline. Os números abaixo foram **medidos
com `pytest-cov`** sobre a suíte de cada módulo (`pytest tests/unit/<módulo>
--cov=<módulo>`):

| Módulo | Coverage | Por que é crítico |
|---|---|---|
| `routing/learning_router` | **100%** | Base de todo o roteamento adaptativo de consultas |
| `routing/tribunal_identifier` | **95%** | Identifica os tribunais a consultar — erro aqui compromete todo o resto |
| `consensus/weighted_voting` | **94%** | Consenso entre agentes — erro gera decisão final errada |
| `tools/circuit_breaker` | **89%** | Resiliência a falhas de API externa de tribunal |
| `utils/input_sanitizer` | **82%** | Segurança (XSS/SQLi) — crítico em qualquer produção |
| `utils/cache_manager` | **73%** | Performance e fallback (Redis + memória) |
| `agents/architect_agent` | **66%** | Raciocínio Chain-of-Thought para planejamento estratégico |

O pipeline de CI (`.github/workflows/ci.yml`) impõe um piso de cobertura de
**50%** nos testes unitários (`--cov-fail-under=50`) como gate bloqueante, além
de rodar a suíte de integração (`pytest tests/integration/`). Módulos de
infraestrutura (workers, storage, integrações externas) têm cobertura de teste
menor de forma deliberada: suas falhas são detectadas por observabilidade
(Prometheus/Grafana) antes de impactarem o usuário final. O próximo passo do
roadmap é ampliar os testes E2E dos endpoints FastAPI com `TestClient` para
elevar o piso de cobertura acima de 50%.

## Capacidade como Enabler

O sistema não substitui o advogado — amplifica sua capacidade:

- Um analista consegue processar significativamente mais consultas com a mesma
  qualidade, porque a parte mecânica (buscar e cruzar jurisprudência entre
  tribunais) é paralelizada e consolidada automaticamente.
- O `ProgressiveAutonomyManager` (HITL) mantém o humano no loop para decisões de
  alta complexidade ou baixa confiança, ajustando o nível de autonomia por
  configuração.
- Times de outras áreas (compliance, contratos, fiscal) podem consumir a API
  REST sem conhecimento jurídico especializado profundo.
