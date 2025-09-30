#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Configurando Observabilidade BuildToFlip v6.1..."

# Criar estrutura de diretórios
mkdir -p monitoring/{dashboards,grafana/provisioning/{datasources,dashboards}}
mkdir -p logs

# Verificar se Prometheus e Grafana estão rodando
echo "📊 Iniciando stack de observabilidade..."
docker-compose up -d prometheus grafana

# Aguardar serviços
echo "⏳ Aguardando Prometheus e Grafana iniciarem..."
sleep 10

# Verificar Prometheus
if curl -sf http://localhost:9090/-/healthy > /dev/null; then
    echo "✅ Prometheus rodando em http://localhost:9090"
else
    echo "❌ Prometheus não está saudável"
    exit 1
fi

# Verificar Grafana
if curl -sf http://localhost:3000/api/health > /dev/null; then
    echo "✅ Grafana rodando em http://localhost:3000"
    echo "   Credenciais: admin / admin"
else
    echo "❌ Grafana não está saudável"
    exit 1
fi

echo ""
echo "🎯 PRÓXIMOS PASSOS:"
echo "1. Acesse Grafana: http://localhost:3000"
echo "2. Login: admin / admin"
echo "3. Dashboard já provisionado em 'BuildToFlip' folder"
echo "4. Métricas disponíveis em: http://localhost:8000/metrics"
echo ""
echo "✅ Observabilidade configurada com sucesso!"
