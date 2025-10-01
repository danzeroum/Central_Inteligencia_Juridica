<<<<<<< HEAD
# 🤖 Sistema de Colaboração Multi-Agente

Sistema especializado em consultas jurídicas com arquitetura multi-agente, onde um supervisor orquestra tarefas para agentes especializados por tribunal.

## 🏗️ Arquitetura

```
src/
├── agents/
│   ├── __init__.py
│   ├── supervisor_agent.py    # Agente orquestrador
│   └── tribunal_agent.py      # Agentes especializados
├── utils/
│   ├── __init__.py
│   ├── input_sanitizer.py     # Sanitização de entradas
│   └── ledger.py              # Ledger de decisões
tests/
├── __init__.py
├── test_supervisor_agent.py
└── test_tribunal_agent.py
examples/
└── demo_multi_agent.py        # Demonstração do sistema
```

## ⚡ Quick Start

```python
from src.agents.supervisor_agent import SupervisorAgent

# Criar supervisor
supervisor = SupervisorAgent()

# Processar tarefa
resultado = supervisor.process_task("Verificar status do tribunal TJSP")
print(resultado)
=======
# Central Inteligência Jurídica

Plataforma de agentes jurídicos com foco em automação, coordenação e aprendizado contínuo.

## 🚀 Novidades: Sistema de Treinamento Contínuo

O BuildToFlip v6.1 trouxe um pipeline completo de aprendizado contínuo para os agentes:

- Coleta estruturada de feedback via REST API (`/api/v1/training/feedback`)
- Orquestração de sessões com o `TrainingManager`
- Métricas avançadas com o `LearningMetricsCollector`
- Dashboard interativo em `/training-dashboard`
- Testes A/B para comparar variantes de agentes

> Documentação completa em [`docs/training-system.md`](docs/training-system.md) e guia rápido em [`docs/training-quickstart.md`](docs/training-quickstart.md).

## ⚙️ Setup Rápido

```bash
./scripts/setup-training-system.sh
```

O script instala dependências, valida o pipeline e executa os testes de integração.

Para subir o servidor manualmente:

```bash
uvicorn src.api.main:app --reload
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
```

## 🧪 Testes

```bash
<<<<<<< HEAD
# Executar testes unitários
python -m pytest tests/ -v

# Executar demonstração
python examples/demo_multi_agent.py
```

## 🔧 Funcionalidades

### SupervisorAgent
- ✅ Identificação automática de tribunal
- ✅ Delegação para agentes especializados
- ✅ Registro no ledger de decisões
- ✅ Histórico de tarefas
- ✅ Estatísticas de uso

### TribunalAgent
- ✅ Consulta de status do tribunal
- ✅ Simulação de consulta processual
- ✅ Movimentações processuais
- ✅ Configurações específicas por tribunal
- ✅ Capacidades especializadas

### Segurança
- ✅ Sanitização de entradas
- ✅ Validação contra injection
- ✅ Logging seguro

## 🏛️ Tribunais Suportados

- TJSP - Tribunal de Justiça de São Paulo
- TJMG - Tribunal de Justiça de Minas Gerais  
- TJRS - Tribunal de Justiça do Rio Grande do Sul
- TJRJ - Tribunal de Justiça do Rio de Janeiro
- STF - Supremo Tribunal Federal

## 📊 Ledger de Decisões

Sistema de registro que captura todas as decisões dos agentes para auditoria e análise:

```python
from src.utils.ledger import DecisionLedger

ledger = DecisionLedger()
entries = ledger.get_entries(agent_type="SupervisorAgent")
```

## 🚀 Exemplos de Uso

```python
# Consulta de status
supervisor.process_task("Status do TJSP")

# Consulta processual  
supervisor.process_task("Processo 1234567-89.2024.8.26.1234 TJMG")

# Múltiplas consultas
supervisor.process_task("Status TJRS e consulta processo STF")
```

## 🔮 Próximos Passos

- [ ] Integração com APIs reais dos tribunais
- [ ] Cache de consultas
- [ ] Dashboard de monitoramento
- [ ] Autenticação e autorização
- [ ] Rate limiting por tribunal
=======
pytest tests/integration/test_training_system.py -v
```

## 📊 Monitoramento

- Dashboard web: `http://localhost:8000/training-dashboard`
- Métricas Prometheus: `http://localhost:8000/metrics`

## 📚 Recursos

- [`examples/demo_training_system.py`](examples/demo_training_system.py): script de demonstração end-to-end
- [`scripts/setup-training-system.sh`](scripts/setup-training-system.sh): automação de setup
- [`docs/training-system.md`](docs/training-system.md): referência detalhada
- [`docs/training-quickstart.md`](docs/training-quickstart.md): onboarding em 5 minutos
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
