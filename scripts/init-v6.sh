#!/usr/bin/env bash
set -euo pipefail

echo "🚀 BuildToFlip v6 - Project Initializer"

# Criar estrutura de diretórios
mkdir -p {.buildtoflip/{consensus,responses,validations,ledger},docs/{API,UX,ADR}}
mkdir -p {src/{main,test},terraform,ansible,docker,k6,scripts}
mkdir -p .github/workflows

# Criar arquivos base
touch docs/API/openapi.yaml
touch docs/UX/ui-kit.md
touch docs/ADR/ADR-Template.md
touch k6/load-test.js
touch .env.example
touch .buildtoflip/ledger/decisions.log
touch .buildtoflip/ledger/overrides.log

# Criar discovery consensus placeholder
cat > .buildtoflip/consensus/discovery-consensus.v6.json <<'JSON'
{
  "version": "6.0",
  "project": {
    "name": "TODO",
    "domain": "TODO",
    "buyer": "TODO"
  }
}
JSON

# Criar decision tree placeholder
cat > .buildtoflip/consensus/decision-tree-pro.v6.json <<'JSON'
{
  "version": "6.0",
  "foundation_level": "TODO",
  "consensus": {
    "method": "fast-consensus-majority"
  }
}
JSON

echo "✅ Estrutura v6 criada com sucesso!"
echo "📝 Próximos passos:"
echo "   1. Preencher discovery-consensus.v6.json"
echo "   2. Configurar .env.dev"
echo "   3. Rodar ./scripts/gates-v6.sh"
