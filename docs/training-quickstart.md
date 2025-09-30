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

## 📚 Próximos Passos

1. Leia a [documentação completa](training-system.md)
2. Configure alertas no Prometheus/Grafana
3. Automatize o script [`scripts/setup-training-system.sh`](../scripts/setup-training-system.sh)
4. Registre decisões estratégicas no `docs/decision-ledger.jsonl`
