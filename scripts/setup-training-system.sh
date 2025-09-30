#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_info "🎓 BuildToFlip v6.1 - Training System Setup"
log_info "Projeto: ${PROJECT_ROOT}"

cd "${PROJECT_ROOT}"

if ! command -v python >/dev/null 2>&1; then
  log_error "Python não encontrado. Instale Python 3.10+ antes de continuar."
  exit 1
fi

if ! command -v pip >/dev/null 2>&1; then
  log_error "pip não encontrado. Verifique sua instalação do Python."
  exit 1
fi

log_info "Instalando dependências Python"
pip install --upgrade pip >/dev/null 2>&1 || log_warn "Falha ao atualizar pip"
pip install -r requirements.txt

if ! command -v uvicorn >/dev/null 2>&1; then
  log_warn "uvicorn não encontrado no PATH. Instalando..."
  pip install uvicorn
fi

log_info "Criando diretórios necessários"
mkdir -p .buildtoflip/training logs

log_info "Validando estrutura de treinamento"
python - <<'PY'
from src.training.training_manager import TrainingManager
from src.training.learning_metrics import get_metrics_collector

manager = TrainingManager()
collector = get_metrics_collector()

print("TrainingManager pronto com feedback mínimo:", manager.min_feedback_for_training)
print("MetricsCollector janela padrão:", collector.window_size)
PY

log_info "Executando testes de integração do treinamento"
if command -v pytest >/dev/null 2>&1; then
  pytest tests/integration/test_training_system.py -q
else
  log_warn "pytest não encontrado. Pule os testes ou instale com 'pip install pytest'."
fi

log_success "Setup do sistema de treinamento concluído!"
log_info "Inicie o servidor com: uvicorn src.api.main:app --reload"
log_info "Acesse o dashboard em: http://localhost:8000/training-dashboard"
