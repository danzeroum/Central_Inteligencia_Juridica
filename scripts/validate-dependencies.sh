#!/usr/bin/env bash
# scripts/validate-dependencies.sh
set -euo pipefail

echo "🔍 Validando Dependências..."

# Reinstalar com versões corretas
pip install --upgrade pip
pip install -r requirements-dev.txt

# Verificar versões
echo ""
echo "📦 Versões Instaladas:"
pip list | grep -E "(numpy|chromadb|fastapi|pytest)"

# Executar testes
echo ""
echo "🧪 Executando Testes..."
pytest -q

# Verificar compatibilidade
echo ""
echo "✅ Validação de Dependências:"
python -c "
import numpy as np
import sys

version = np.__version__
major = int(version.split('.')[0])

if major >= 2:
    print(f'❌ NumPy {version} detectado - requer < 2.0')
    sys.exit(1)
else:
    print(f'✅ NumPy {version} - compatível')
    
try:
    import chromadb
    print(f'✅ ChromaDB {chromadb.__version__} importado com sucesso')
except Exception as e:
    print(f'⚠️  ChromaDB opcional não disponível: {e}')
"

echo ""
echo "✅ Todas as validações passaram!"
