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
```

## 🧪 Testes

```bash
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
