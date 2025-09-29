#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "❌ OPENAI_API_KEY não configurada. Exporte a variável antes de rodar o script." >&2
  exit 1
fi

if ! curl -sf "http://localhost:8000/api/v1/heartbeat" > /dev/null; then
  echo "❌ ChromaDB não está respondendo em http://localhost:8000." >&2
  echo "   Dica: execute 'docker-compose up -d chromadb' em outro terminal." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

echo "✅ Executando testes de integração da memória vetorial..."
pytest tests/integration/test_vector_memory.py -m integration -s

echo "✅ Executando testes emergentes de aprendizado contínuo..."
pytest tests/emergent/test_memory_learning.py -m emergent -s

