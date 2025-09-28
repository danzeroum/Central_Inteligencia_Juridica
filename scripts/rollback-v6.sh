#!/usr/bin/env bash
set -euo pipefail

echo "⚠️  BuildToFlip v6 - Rollback"

# Verificar se há backup
if [ ! -f ".buildtoflip/backup/last-deploy.tar.gz" ]; then
    echo "❌ Nenhum backup encontrado"
    exit 1
fi

# Confirmar rollback
read -p "Confirma rollback para versão anterior? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelado"
    exit 0
fi

# Registrar no ledger
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_initiated\",\"reason\":\"$1\"}" >> .buildtoflip/ledger/overrides.log

# Parar serviços atuais
echo "🛑 Parando serviços..."
docker-compose down

# Restaurar backup
echo "📦 Restaurando backup..."
tar -xzf .buildtoflip/backup/last-deploy.tar.gz

# Resubir serviços
echo "🚀 Reiniciando serviços..."
docker-compose up -d

# Verificar saúde
sleep 10
if curl -sf http://localhost:8080/actuator/health > /dev/null; then
    echo "✅ Rollback concluído com sucesso"
    echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_success\"}" >> .buildtoflip/ledger/decisions.log
else
    echo "❌ Falha no rollback - intervenção manual necessária"
    echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_failed\"}" >> .buildtoflip/ledger/overrides.log
    exit 1
fi
