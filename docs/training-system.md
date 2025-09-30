# 🎓 Sistema de Treinamento Contínuo - BuildToFlip v6.1

## Visão Geral

O **Sistema de Treinamento Contínuo** é uma capacidade avançada do BuildToFlip v6.1 que permite aos agentes jurídicos aprenderem e melhorarem continuamente através de feedback real dos usuários e métricas de performance.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                   Training Manager                       │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Feedback     │  │   Training   │  │    A/B       │ │
│  │   Queue       │  │   Sessions   │  │   Testing    │ │
│  └───────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼───────┐  ┌──────▼──────┐  ┌──────▼──────┐
│  Continuous   │  │   Learning  │  │   Metrics   │
│  Evaluator    │  │   Router    │  │  Collector  │
└───────────────┘  └─────────────┘  └─────────────┘
```

## 📦 Componentes Principais

### 1. Training Manager (`src/training/training_manager.py`)

**Responsabilidade:** Orquestrador central do sistema de aprendizado.

**Funcionalidades:**
- Gerenciar sessões de treinamento
- Processar feedback dos usuários
- Calcular melhorias de performance
- Atualizar pesos de roteamento
- Coordenar testes A/B

**Exemplo de Uso:**
```python
from src.training.training_manager import TrainingManager

manager = TrainingManager()

# Submeter feedback
await manager.process_feedback(
    agent_type="TJSP",
    task_result={"success": True, "latency": 0.45},
    user_rating=0.9
)

# Treinar agente
result = await manager.train_agent("TJSP")
print(result["improvements"])
```

### 2. Training API (`src/api/training_endpoints.py`)

**Responsabilidade:** Expor funcionalidades de treinamento via REST API.

**Endpoints:**

#### POST `/api/v1/training/feedback`
Submete feedback para um agente.

```bash
curl -X POST http://localhost:8000/api/v1/training/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "TJSP",
    "task_result": {"success": true, "latency": 0.5},
    "user_rating": 0.85
  }'
```

#### POST `/api/v1/training/train`
Inicia ciclo de treinamento para um agente.

```bash
curl -X POST http://localhost:8000/api/v1/training/train \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "TJSP", "force": false}'
```

#### GET `/api/v1/training/stats`
Obtém estatísticas de treinamento.

```bash
curl http://localhost:8000/api/v1/training/stats?agent_type=TJSP
```

#### GET `/api/v1/training/history`
Obtém histórico de sessões de treinamento.

```bash
curl http://localhost:8000/api/v1/training/history?limit=20
```

#### POST `/api/v1/training/ab-test`
Executa teste A/B entre duas variantes de agente.

```bash
curl -X POST http://localhost:8000/api/v1/training/ab-test \
  -H "Content-Type: application/json" \
  -d '{
    "agent_a_type": "TJSP_v1",
    "agent_b_type": "TJSP_v2",
    "test_cases": [{"task": "status check"}]
  }'
```

### 3. Training Dashboard (`src/api/static/training-dashboard.html`)

**Responsabilidade:** Interface visual para monitoramento de treinamento.

**Funcionalidades:**
- Visualização de estatísticas globais
- Seleção e análise por agente
- Histórico de sessões de treinamento
- Trigger manual de treinamento
- Auto-refresh a cada 30 segundos

**Acesso:**
```
http://localhost:8000/training-dashboard
```

**Componentes Visuais:**
- **Estatísticas Globais:** Total de sessões, feedback recebido, sessões ativas
- **Lista de Agentes:** Agentes com histórico de treinamento
- **Performance do Agente:** Métricas e melhorias percentuais
- **Histórico:** Sessões passadas com status e resultados

### 4. Learning Metrics (`src/training/learning_metrics.py`)

**Responsabilidade:** Coletar e analisar métricas específicas de aprendizado.

**Funcionalidades:**
- Armazenamento em janelas deslizantes
- Cálculo de estatísticas (média, desvio padrão, percentis)
- Detecção de tendências (improving/declining/stable)
- Detecção de anomalias
- Comparação entre agentes
- Cálculo de taxa de aprendizado

**Exemplo de Uso:**
```python
from src.training.learning_metrics import get_metrics_collector

collector = get_metrics_collector()

# Registrar métrica
collector.record("TJSP", "accuracy", 0.85)

# Obter resumo
summary = collector.get_metric_summary("TJSP", "accuracy")
print(summary["statistics"])  # mean, std, p50, p95, p99
print(summary["trend"])        # improving/declining/stable

# Detectar anomalias
anomalies = collector.detect_anomalies("TJSP", "accuracy")

# Comparar agentes
comparison = collector.compare_agents("TJSP", "TJMG", "accuracy")
print(comparison["comparison"]["better_performer"])
```

### 5. Integration Tests (`tests/integration/test_training_system.py`)

**Responsabilidade:** Validar comportamento do sistema de treinamento.

**Testes Cobertos:**
- Inicialização do Training Manager
- Submissão de feedback
- Ciclo completo de treinamento
- Validação de requisitos mínimos
- Recuperação de estatísticas
- Testes A/B
- Gravação e análise de métricas
- Detecção de tendências e anomalias
- Treinamento multi-agente
- Rastreamento de histórico

**Executar Testes:**
```bash
pytest tests/integration/test_training_system.py -v
```

## 🔄 Fluxo de Treinamento

### 1. Coleta de Feedback
```
Usuario → Tarefa Processada → Feedback → Fila de Feedback
```

### 2. Acúmulo até Threshold
```
Fila atingiu 10 feedbacks → Auto-trigger Training (opcional)
```

### 3. Sessão de Treinamento
```
Inicio Sessão
    ↓
Avaliar Performance (com feedback)
    ↓
Calcular Melhorias vs Baseline
    ↓
Atualizar Pesos de Roteamento
    ↓
Atualizar Estado do Agente
    ↓
Gravar no Ledger
    ↓
Fim Sessão (completed/failed)
```

### 4. Aplicação de Aprendizado
```
Novos requests → Router usa pesos atualizados → Melhoria gradual
```

## 📊 Métricas Rastreadas

### Métricas de Performance
- **Success Rate:** Taxa de sucesso das tarefas
- **Latency:** Tempo de resposta (P50, P95, P99)
- **Accuracy:** Precisão das respostas
- **User Satisfaction:** Rating médio dos usuários

### Métricas de Treinamento
- **Total Sessions:** Sessões de treino concluídas
- **Total Feedback:** Volume de feedback acumulado
- **Improvements:** Melhorias percentuais por métrica
- **Learning Rate:** Taxa de melhoria por hora
- **Trend:** Direção da evolução (improving/declining/stable)

## 🎯 Casos de Uso

### Caso 1: Melhorar Agente com Baixa Satisfação

```python
# 1. Identificar problema no dashboard
# → TJMG mostra user_satisfaction em declínio

# 2. Coletar feedback específico
for _ in range(20):
    await manager.process_feedback(
        agent_type="TJMG",
        task_result=result,
        user_rating=rating,
        corrections={"suggested": "melhorar precisão"}
    )

# 3. Treinar com força
result = await manager.train_agent("TJMG")

# 4. Monitorar melhoria
summary = collector.get_metric_summary("TJMG", "user_satisfaction")
print(summary["trend"])  # Esperado: "improving"
```

### Caso 2: Teste A/B de Nova Versão

```python
# Criar teste entre versão atual e nova
result = await manager.run_ab_test(
    agent_a_type="TJSP_current",
    agent_b_type="TJSP_new",
    test_cases=[
        {"task": "status check"},
        {"task": "process query"},
        {"task": "complex analysis"}
    ]
)

if result["winner"] == "B" and result["statistical_significance"] > 0.8:
    print("Nova versão aprovada para produção!")
```

### Caso 3: Detecção de Degradação

```python
# Sistema detecta automaticamente via anomalias
anomalies = collector.detect_anomalies("TJSP", "latency", threshold_std=2.0)

if anomalies:
    print(f"ALERTA: {len(anomalies)} anomalias detectadas!")
    # Trigger automatic rollback ou notificação
```

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# .env
TRAINING_MIN_FEEDBACK=10           # Mínimo de feedback para treinar
TRAINING_INTERVAL_HOURS=24         # Intervalo entre treinamentos
TRAINING_METRICS_WINDOW=100        # Tamanho da janela de métricas
TRAINING_AUTO_TRIGGER=true         # Auto-trigger ao atingir threshold
```

### Customização do Training Manager

```python
manager = TrainingManager()

# Ajustar parâmetros
manager.min_feedback_for_training = 20
manager.training_interval_hours = 12
manager.auto_trigger_enabled = True  # habilita treino automático ao atingir threshold

# Adicionar callbacks customizados
manager.on_training_complete = lambda result: notify_team(result)
```

## 📈 Monitoramento via Prometheus

O sistema expõe métricas Prometheus em `/metrics`:

```
# Métricas disponíveis
training_sessions_total{agent="TJSP",status="completed"}
training_feedback_total{agent="TJSP"}
training_improvement_percent{agent="TJSP",metric="accuracy"}
training_duration_seconds{agent="TJSP"}
```

**Exemplo de Query:**
```promql
# Taxa de melhoria média nos últimos 7 dias
avg_over_time(training_improvement_percent{metric="accuracy"}[7d])
```

## 🚨 Troubleshooting

### Problema: Treinamento não é triggered automaticamente

**Causa:** Feedback insuficiente ou intervalo mínimo não atingido.

**Solução:**
```python
# Verificar estado
stats = manager.get_training_stats("TJSP")
print(stats["pending_feedback"])  # Deve ser >= 10
print(stats["last_training"])      # Deve ser há >24h

# Forçar treinamento
await manager.train_agent("TJSP", force=True)
```

### Problema: Métricas não aparecem no dashboard

**Causa:** Métricas não sendo registradas ou threshold não atingido.

**Solução:**
```python
# Verificar métricas registradas
collector = get_metrics_collector()
export = collector.export_metrics("TJSP")
print(export["metrics"].keys())

# Registrar manualmente se necessário
collector.record("TJSP", "accuracy", 0.85)
```

### Problema: A/B test retorna "insufficient_data"

**Causa:** Pouco feedback para comparação estatística.

**Solução:**
```python
# Usar test_cases mais numerosos
test_cases = [{"task": f"test_{i}"} for i in range(50)]
result = await manager.run_ab_test(a, b, test_cases)
```

## 🎓 Melhores Práticas

### 1. Feedback de Qualidade
- Sempre incluir `user_rating` quando disponível
- Fornecer `corrections` específicas quando possível
- Marcar tarefas críticas para priorização

### 2. Monitoramento Ativo
- Verificar dashboard diariamente
- Configurar alertas para anomalias
- Revisar tendências semanalmente

### 3. Treinamento Gradual
- Não forçar treinamentos muito frequentes
- Aguardar acúmulo de feedback diversificado
- Validar melhorias antes de deploy

### 4. Testes A/B Rigorosos
- Usar amostras significativas (>50 casos)
- Verificar significância estatística (>0.8)
- Documentar resultados no ledger

## 🔐 Segurança

### Proteções Implementadas
- Rate limiting nos endpoints de training
- Validação de input em todos os endpoints
- Autenticação JWT (se habilitado)
- Auditoria completa via ledger

### Recomendações
- Restringir acesso ao dashboard em produção
- Usar HTTPS para endpoints de training
- Implementar RBAC para operações críticas
- Monitorar tentativas de manipulação de feedback

## 📚 Referências

- [ADR-007: Memória e Aprendizagem](ADRs/ADR-007-vector-memory.md)
- [BuildToFlip v6.1 Reality Check](buildtoflip-v6.1-reality-check.md)
- [Orchestration Matrix](orchestration-matrix.md)
- [Fallback Strategy](fallback-strategy.md)

---

**Nota:** Este sistema segue os princípios "Crisp Pragmatist" do BuildToFlip: **disciplina mínima, valor máximo, vendabilidade sempre**. O treinamento é **incremental, auditável e reversível**.
