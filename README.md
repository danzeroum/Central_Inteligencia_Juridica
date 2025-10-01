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
```

## 🧪 Testes

```bash
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
