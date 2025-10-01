#!/usr/bin/env bash
# scripts/move-sandbox-to-experimental.sh
set -euo pipefail

echo "📦 Movendo componentes de sandbox para experimental..."

# Criar estrutura experimental
mkdir -p experimental/security/sandbox

# Mover arquivos
mv src/tools/sandbox/secure_executor.py experimental/security/sandbox/
mv src/tools/sandbox/docker_sandbox.py experimental/security/sandbox/
mv src/tools/sandbox/__init__.py experimental/security/sandbox/

# Criar README no experimental
cat > experimental/security/README.md <<'EOF_README'
# Experimental Security Components

## Sandbox de Segurança

**Status:** Experimental (não usado no MVP)

**Razão:** Conforme ADR-011, o sandbox não é necessário para o MVP atual pois não há execução de código arbitrário.

**Quando Reativar:**
- Execução dinâmica de código de usuários
- Plugins de terceiros
- Evolution para Foundation Level: Standard/Enterprise

**Arquivos:**
- `sandbox/secure_executor.py` - Executor seguro com validações
- `sandbox/docker_sandbox.py` - Isolamento via Docker

**Para Reintegrar:**
1. Mover de volta para `src/tools/sandbox/`
2. Atualizar imports em código que necessitar
3. Configurar Docker-in-Docker se necessário
4. Adicionar testes de integração
EOF_README

echo "✅ Sandbox movido para experimental/security/"
echo "📝 ADR-011 criada e documentada"
