# 🚀 Training System - Guia de Início Rápido

Este guia mostra como começar a usar o Sistema de Treinamento Contínuo em **menos de 5 minutos**.

## ⚡ Quick Start (5 minutos)

### 1. Setup Inicial

```bash
# Clone e navegue até o diretório do projeto
git clone https://github.com/sua-org/central-inteligencia-juridica.git
cd central-inteligencia-juridica

# Configure ambiente virtual
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Inicie o Sistema

```bash
uvicorn src.api.main:app --reload
```

### 3. Abra o Training Dashboard

```
http://localhost:8000/training-dashboard
```

### 4. Envie Feedback de Teste

```bash
curl -X POST http://localhost:8000/api/v1/training/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "TJSP",
    "task_result": {"success": true, "latency": 0.52},
    "user_rating": 0.88
  }'
```

### 5. Force um Ciclo de Treinamento

```bash
curl -X POST http://localhost:8000/api/v1/training/train \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "TJSP", "force": true}'
```

### 6. Consulte Estatísticas Atualizadas

```bash
curl http://localhost:8000/api/v1/training/stats?agent_type=TJSP | jq
```

## 🧪 Rodando Testes de Integração

```bash
pytest tests/integration/test_training_system.py -v
```


## 🚀 Setup Inicial do Agente (< 10 minutos)

### 1. Clone e Estruture

```bash
git clone <repo> && cd <projeto>
./scripts/create-v6.1-structure.sh
```

### 2. Configure o Ambiente

```bash
cp .env.template .env
# Adicione suas API keys (OPENAI_API_KEY, etc.)
```

### 3. Inicie Dependências Essenciais

```bash
docker-compose up -d redis
```

### 4. Bootstrap do Agente Base

```bash
./scripts/agent-lifecycle/bootstrap-agent.sh
```

### 5. Valide a Instalação

```bash
python -c "from src.core.safe_agent_base import SafeAgentBase; print('✅ Agent base OK')"
```

## 🎯 Primeiro Agente Funcional

```python
from src.core.safe_agent_base import SafeAgentBase
from src.protocols.mcp_server import MCPServer

# Criar agente com guardrails obrigatórios
agent = SafeAgentBase()
agent.add_capability("memory")
agent.add_capability("planning")

# Expor via MCP
mcp = MCPServer(agent)
print(mcp.publish_agent_card())

# Executar primeira tarefa
result = agent.execute(
    task="Analise o projeto e sugira próximos passos",
    context="Projeto de agente jurídico com TJSP/TJMG"
)
print(result.to_dict())
```

## ✅ Verificação Rápida

```bash
# Teste padrões básicos
pytest tests/emergent/test_emergent_behavior.py -v

# Valide comportamento
./scripts/agent-lifecycle/validate-behavior.sh

# Monitore decisões em tempo real
tail -f .buildtoflip/ledger/agent-decisions/*.json
```

## 🔥 Troubleshooting Agêntico

### Problema: Agente em Loop Infinito

**Sintomas:**

- Mesma decisão repetida mais de cinco vezes.
- Consumo de tokens crescendo exponencialmente.
- Timeout em tasks simples.

**Diagnóstico:**

```bash
# Analise padrões no ledger
jq '.[] | select(.reasoning_log | length > 10)' .buildtoflip/ledger/agent-decisions/*.json

# Verifique dependências circulares
grep -r "depends_on" src/agents/
```

**Solução:**

```python
from src.chains.resilient_chain import ResilientPromptChain

chain = ResilientPromptChain(
    steps=[...],
    max_retries=3,  # Limite de repetições
)
```

### Problema: Confidence Sempre Baixo (<0.5)

**Causas comuns:** RAG sem documentos relevantes, prompt engineering inadequado ou modelo subdimensionado.

```python
# 1. Enriqueça contexto via RAG
from src.tools.rag_tool import RAGTool

rag = RAGTool("http://localhost:8000")
context = rag.retrieve(task, k=10)  # Aumente k

# 2. Use prompts avançados
from config.prompts.advanced_agent_prompts import AGENT_PROMPTS

prompt = AGENT_PROMPTS["architect_with_cot"]  # Chain-of-Thought

# 3. Considere modelo mais capaz
# Exemplo: gpt-3.5-turbo → gpt-4 ou gemini-pro
```

### Problema: Sandbox Violations

```python
# Verifique patterns proibidos
from src.safety.security_config import SecurityConfig

# Adicione exceção controlada (somente se necessário)
# NUNCA desabilite guardrails globalmente!
SecurityConfig.ALLOWED_DOMAINS.add("trusted-api.example.com")
```

### Problema: Memória Crescendo Infinitamente

```python
from src.memory.intelligent_forgetting import IntelligentForgetting

# Ative esquecimento inteligente
memory = IntelligentForgetting(memory_store)
removed = memory.adaptive_forget()  # Remove memórias com relevance < 0.1
print(f"Removidos {removed} registros obsoletos")
```

### Problema: Consenso Entre Agentes Nunca Alcançado

```python
from src.consensus.weighted_voting import WeightedConsensusEngine

# Ajuste pesos de especialização
engine = WeightedConsensusEngine()
engine.agent_weights["architect"]["architecture"] = 0.95  # Aumente peso do expert

# Reduza threshold temporariamente
if consensus["consensus_strength"] >= 0.55:  # Era 0.7
    proceed_with_caution(consensus)
```

## 🏆 Checklist de Certificação v6.1

Para obter certificação oficial BuildToFlip v6.1, garanta que cada item esteja ✅:

### 🔴 Crítico (Bloqueia Certificação)

- Guardrails ativos: os quatro guardrails obrigatórios no `SafeAgentBase`.
- Sandbox funcional: zero execuções de ferramentas fora do sandbox.
- Ledger completo: todas as decisões registradas em `.buildtoflip/ledger/agent-decisions/`.
- Testes emergentes: suíte `tests/emergent/` com >80% de cobertura comportamental.
- Observabilidade: `src/utils/observability.py` gerando traces válidos.
- MCP compliance: agentes expondo cards válidos via MCP.

### 🟡 Importante (Recomendado)

- RAG integrado com recall >75%.
- Multi-agent: pelo menos dois agentes colaborando via protocolos.
- Estratégia de fallback (`fallback-strategy.md`) implementada.
- Learning loop ativo em `scripts/agent-lifecycle/learning-loop.sh`.
- Mecanismo de consenso ponderado funcionando.
- Prompts versionados em `.buildtoflip/prompts/registry.json`.

### 🟢 Desejável (Diferencial)

- Framework de A/B testing ativo.
- Adaptive planning com replanning automático.
- Progressive autonomy elevando níveis de confiança.
- Cost optimization configurado para uso eficiente de recursos.
- Técnicas avançadas de raciocínio (CoT, ToT ou ReAct) habilitadas.

### 📋 Comando de Certificação

```bash
# Execute validação completa
./scripts/validate-agents-v6.1.sh

# Se tudo passar, gere certificado
python - <<'CERT'
from datetime import datetime
import json

cert = {
    "project": "Central de Inteligência Jurídica",
    "version": "1.0.0-v6.1",
    "certification_date": datetime.now().isoformat(),
    "patterns_implemented": [
        "prompt_chaining", "routing", "tool_use",
        "memory_management", "multi_agent_collaboration",
        "guardrails", "reasoning_techniques"
    ],
    "quality_gates": {"all_passed": True},
    "certified_by": "BuildToFlip Squad v6.1",
    "confidence": 0.98
}

print(json.dumps(cert, indent=2))
CERT
```

## 🌱 Roadmap de Evolução do Agente

### Fase 1: Foundation (Semanas 1-2)

- ✅ `SafeAgentBase` com quatro guardrails.
- ✅ Ledger de decisões funcionando.
- ✅ Primeiro padrão (Prompt Chaining ou Routing).
- ✅ Testes emergentes básicos.
- **Próximo passo:** `scripts/agent-lifecycle/evolve-capabilities.sh memory_management`.

### Fase 2: Capabilities (Semanas 3-4)

- ✅ Memory + RAG integrados.
- ✅ Tool use com sandbox.
- ✅ Reasoning techniques (CoT ou ReAct).
- ✅ Fallback strategy implementado.
- **Próximo passo:** `scripts/agent-lifecycle/evolve-capabilities.sh multi_agent`.

### Fase 3: Collaboration (Semanas 5-6)

- ✅ Dois ou mais agentes especializados.
- ✅ Mecanismo de consenso funcionando.
- ✅ Protocolo MCP implementado.
- ✅ Comunicação agente-a-agente ativa.
- **Próximo passo:** `scripts/agent-lifecycle/learning-loop.sh`.

### Fase 4: Intelligence (Semanas 7-8)

- ✅ A/B testing entre configurações.
- ✅ Learning router ajustando rotas.
- ✅ Progressive autonomy aumentando trust.
- ✅ Adaptive planning com replanning.
- **Próximo passo:** certificação v6.1 completa.

| Fase | Goal Achievement | Confidence Avg | HITL Rate | Cost/Task |
|------|------------------|----------------|-----------|-----------|
| 1    | >70%             | >0.6           | <50%      | <$0.50    |
| 2    | >80%             | >0.7           | <30%      | <$0.30    |
| 3    | >90%             | >0.8           | <15%      | <$0.20    |
| 4    | >95%             | >0.85          | <10%      | <$0.15    |

## 🔌 Integração com Ecossistema

### LangSmith (Observabilidade Avançada)

```python
import os
from langchain.callbacks.manager import tracing_v2_enabled

os.environ["LANGCHAIN_API_KEY"] = "sua-chave"
os.environ["LANGCHAIN_PROJECT"] = "buildtoflip-v61"

with tracing_v2_enabled(project_name="central-juridica"):
    result = agent.execute(task)
    # Traces automaticamente no dashboard LangSmith
```

### Weights & Biases (Métricas de ML)

```python
import wandb
from src.evaluation.continuous_eval import ContinuousEvaluator

wandb.init(project="buildtoflip-agents", name="juridico-mvp")

evaluator = ContinuousEvaluator(metrics_config={})
trajectory = agent.execute(task)
scores = evaluator.evaluate_trajectory(trajectory)

wandb.log({
    "task_completion": scores["task_completion"],
    "efficiency": scores["efficiency"],
    "safety": scores["safety"],
})
```

### Vector DB (ChromaDB, Pinecone, Weaviate)

```python
# ChromaDB (local)
from src.tools.rag_tool import RAGTool
rag = RAGTool("http://localhost:8000")

# Pinecone (cloud)
import pinecone
pinecone.init(api_key="sua-chave", environment="us-west1-gcp")
index = pinecone.Index("buildtoflip-memories")

# Weaviate (híbrido)
import weaviate
client = weaviate.Client("http://localhost:8080")
```

### Message Queues (Kafka, RabbitMQ)

```python
from kafka import KafkaProducer, KafkaConsumer

producer = KafkaProducer(bootstrap_servers="localhost:9092")

# Agente publica decisão
producer.send("agent-decisions", value=decision.encode("utf-8"))

# Outro agente consome
consumer = KafkaConsumer("agent-decisions", bootstrap_servers="localhost:9092")
for message in consumer:
    process_peer_decision(message.value)
```

## 🎯 Casos de Uso Avançados

### Caso 1: Agente Legal Research Assistant

```python
legal_agent = SafeAgentBase()
legal_agent.add_capability("tool_use")
legal_agent.add_capability("memory")
legal_agent.add_capability("planning")

from src.agents.tribunal_api_client import TribunalAPIClient

for tribunal in ["TJSP", "TJMG", "STF"]:
    client = TribunalAPIClient(tribunal)
    legal_agent.register_tool(f"query_{tribunal}", client.query_real_process)

result = legal_agent.execute(
    task="Encontre jurisprudência sobre LGPD em São Paulo dos últimos 6 meses"
)
```

### Caso 2: Multi-Agent Contract Analyzer

```python
from src.orchestration.unified_orchestrator import UnifiedOrchestrator

orchestrator = UnifiedOrchestrator()

# Adicionar agentes especializados
orchestrator.agents["legal"] = LegalAgent()
orchestrator.agents["financial"] = FinancialAgent()
orchestrator.agents["risk"] = RiskAgent()

analysis = await orchestrator.execute_complex_task({
    "description": "Analisar contrato de prestação de serviços anexo",
    "document": contract_pdf,
    "priority": "high",
})

print(analysis["consensus"])  # decision_maker, consensus_strength
```

### Caso 3: Self-Improving Customer Support Agent

```python
from src.evaluation.ab_testing import AgentABTestingFramework
from src.routing.learning_router import LearningRouter

ab_framework = AgentABTestingFramework()
router = LearningRouter()

test_cases = load_support_tickets()
result = await ab_framework.run_ab_test(
    agent_a=SupportAgent(prompt="v1"),
    agent_b=SupportAgent(prompt="v2_cot"),
    test_cases=test_cases,
    metrics=["resolution_time", "customer_satisfaction"],
)

if result["winner"] == "B":
    router.update_route_performance(
        request={"type": "support"},
        route="v2_cot",
        success=True,
        latency=result["scores"]["B"],
    )
```

## 📘 FAQ Estratégico

### Quando usar AI Agent vs. Traditional App?

Use AI Agent quando:

- ✅ Tarefas exigem raciocínio complexo.
- ✅ Ambiente é dinâmico ou imprevisível.
- ✅ É necessária adaptação contínua.
- ✅ Há múltiplas ferramentas/APIs a orquestrar.
- ✅ Decisões precisam de explicabilidade.

Prefira abordagens tradicionais quando:

- ❌ Fluxo é totalmente determinístico.
- ❌ Performance é crítica (<50 ms).
- ❌ Não há tolerância a custos de LLM.
- ❌ Regulamentação proíbe IA autônoma.

### Como balancear autonomia vs. controle?

```python
from src.hitl.progressive_autonomy import ProgressiveAutonomyManager

autonomy = ProgressiveAutonomyManager()

autonomy.agent_trust_scores["legal_agent"] = 0.5  # Nível inicial conservador

for task in tasks:
    result = await autonomy.execute_with_autonomy("legal_agent", task)
    # Trust score aumenta +0.02 a cada sucesso e diminui -0.1 a cada falha

# Eventualmente atinge nível 3 (full autonomy)
```

### Como debugar comportamento emergente inesperado?

```python
from src.utils.observability import AgentObserver

observer = AgentObserver()
span = observer.start_span("investigate_behavior")
observer.log_reasoning("Por que agente tomou decisão X?")
trajectory = observer.export_trajectory()
```

```bash
jq '.[] | select(.agent=="problematic_agent")' \
  .buildtoflip/ledger/agent-decisions/*.json | less

pytest tests/emergent/test_emergent_behavior.py::test_specific_scenario -v
```

### Como migrar de v6.0 para v6.1?

```bash
# 1. Backup do projeto
tar -czf backup-v6.0.tar.gz .

# 2. Atualize estrutura
./scripts/create-v6.1-structure.sh

# 3. Migre agentes para SafeAgentBase
python - <<'PY'
# Antes (v6.0)
# agent = CustomAgent()

# Depois (v6.1)
from src.core.safe_agent_base import SafeAgentBase
agent = SafeAgentBase()
agent.add_capability("memory")
agent.add_capability("planning")
PY

# 4. Configure prompts versionados
cp .buildtoflip/prompts/v1.0/* .buildtoflip/prompts/v1.1/

# 5. Rode testes emergentes
pytest tests/emergent/ -v

# 6. Valide comportamento
./scripts/agent-lifecycle/validate-behavior.sh
```

## 📚 Glossário Agêntico

| Termo | Definição | Exemplo no Projeto |
|-------|-----------|--------------------|
| Agent Card | Metadados MCP descrevendo capacidades | `MCPServer.publish_agent_card()` |
| Chain-of-Thought (CoT) | Raciocínio exposto passo a passo | `ArchitectAgent.reason_with_cot()` |
| Consensus Strength | Métrica de acordo entre agentes (0-1) | `WeightedConsensusEngine.reach_consensus()` |
| Emergent Behavior | Comportamento não programado da composição | `tests/emergent/` |
| Guardrail | Validação de segurança obrigatória | 4 em `SafeAgentBase` |
| HITL | Human-in-the-Loop, escalação para humano | `ProgressiveAutonomyManager` |
| Ledger | Registro imutável de decisões | `.buildtoflip/ledger/agent-decisions/` |
| MCP | Model Context Protocol para discovery | `MCPServer`, `MCPToolRegistry` |
| Orchestration Matrix | Mapa de handoffs entre padrões | `orchestration-matrix.md` |
| Progressive Autonomy | Confiança crescente baseada em histórico | Trust score 0.0-1.0 |
| RAG | Retrieval Augmented Generation | `RAGTool` com ChromaDB |
| ReAct | Reasoning + Acting em loop | `DeveloperAgent.react_loop()` |
| Replanning | Ajuste dinâmico do plano após falha | `AdaptivePlanner.replan_from_point()` |
| Sandbox | Ambiente isolado para execução de tools | `SecureToolSandbox` com Docker |
| Span | Segmento rastreável de operação | `AgentObserver.start_span()` |
| Trajectory | Sequência de decisões/ações | `AgentObserver.export_trajectory()` |
| Tool Use | Capacidade de invocar ferramentas externas | `MCPToolRegistry.execute()` |
| Vector DB | Base vetorial para memória semântica | ChromaDB/Pinecone/Weaviate |

## ⚡ Quick Wins (Valor Imediato)

### Quick Win 1: Expor Lógica Existente como Tool (15 min)

```python
from src.tools.mcp_registry import MCPToolRegistry

registry = MCPToolRegistry()

@registry.register_tool("analyze_contract")
def analyze_contract(contract_text: str) -> dict:
    return {"score": 0.85, "risks": ["clause_3"]}

agent.execute("Analise o contrato X")
```

### Quick Win 2: Adicionar Memória a Agente Stateless (10 min)

```python
from src.memory.agent_memory import AgentMemorySystem

memory = AgentMemorySystem()

memory.remember_decision("legal_agent", {
    "case_id": "2024-001",
    "decision": "approve",
    "confidence": 0.92,
})

context = memory.recall_similar("casos aprovados recentes", k=3)
```

### Quick Win 3: Habilitar Observabilidade (5 min)

```python
from src.utils.observability import AgentObserver

observer = AgentObserver()
span = observer.start_span("legal_analysis", {"case_id": "2024-001"})

result = agent.execute(task)
observer.log_reasoning("Escolhi aprovar porque...")

span.close()

print(observer.export_trajectory())
```

### Quick Win 4: Rate Limiting (5 min)

```python
from src.safety.security_config import SecurityConfig

SecurityConfig.MAX_CONCURRENT_TOOLS = 3  # Era 5
agent.resource_limit = {"max_tokens": 4000, "max_cost": 0.10}
```

### Quick Win 5: Cache (10 min)

```python
from src.utils.cache_manager import get_cache_manager

cache = get_cache_manager()

cached = cache.get_cached("TJSP", "status_check", {})
if cached:
    return cached

cache.set_cache("TJSP", "status_check", {}, result, ttl=3600)
```

## 🛠️ Comandos Essenciais de 1 Linha

```bash
# SETUP
./scripts/create-v6.1-structure.sh && ./scripts/agent-lifecycle/bootstrap-agent.sh

# DESENVOLVIMENTO
pytest tests/emergent/ -v && ./scripts/agent-lifecycle/validate-behavior.sh

# EVOLUÇÃO
./scripts/agent-lifecycle/evolve-capabilities.sh [PATTERN] && pytest tests/emergent/

# MONITORAMENTO
tail -f .buildtoflip/ledger/agent-decisions/*.json | jq -C '.'

# DEBUGGING
jq '.[] | select(.confidence < 0.5)' .buildtoflip/ledger/agent-decisions/*.json

# ROLLBACK
./scripts/agent-lifecycle/rollback-version.sh [VERSION_TAG]

# CERTIFICAÇÃO
./scripts/validate-agents-v6.1.sh && echo "✅ Certificação OK"

# DEPLOY
docker-compose up -d && ./scripts/demo-v6.sh
```

## 📚 Próximos Passos

1. Leia a [documentação completa](training-system.md).
2. Configure alertas no Prometheus/Grafana.
3. Automatize o script [`scripts/setup-training-system.sh`](../scripts/setup-training-system.sh).
4. Registre decisões estratégicas no `docs/decision-ledger.jsonl`.

---

Você agora tem:

- ✅ Framework completo de orquestração agêntica.
- ✅ 17 componentes de referência.
- ✅ Padrões das cinco famílias principais.
- ✅ Troubleshooting de problemas comuns.
- ✅ Roadmap de evolução incremental.
- ✅ Certificação oficial BuildToFlip v6.1.

**Próximos passos sugeridos:**

- Se está iniciando: execute o “Setup Inicial do Agente” (10 min).
- Se está evoluindo: consulte o “Roadmap de Evolução” para a próxima fase.
- Se está debugando: acesse diretamente “Troubleshooting Agêntico”.
- Se está certificando: rode o checklist completo de certificação.

> Filosofia Crisp Pragmatist: valor primeiro, segurança inegociável, observabilidade desde o dia 1, evolução incremental e HITL quando houver incerteza.

