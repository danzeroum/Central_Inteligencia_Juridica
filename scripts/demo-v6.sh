#!/usr/bin/env bash
set -euo pipefail

echo "🚀 BuildToFlip v6 - Demo Runner"

# Verificar pré-requisitos
command -v docker >/dev/null 2>&1 || { echo "❌ Docker não instalado. Abortando."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "❌ curl não instalado. Abortando."; exit 1; }

# Subir ambiente
echo "📦 Iniciando containers em segundo plano..."
docker-compose up -d --build

# Aguardar serviços
echo "⏳ Aguardando a aplicação iniciar (15s)..."
sleep 15

# Verificar saúde da aplicação
echo "🔍 Verificando o endpoint de saúde..."
if curl -sf http://localhost:8000/health; then
    echo "✅ Aplicação saudável e respondendo."
else
    echo "❌ A aplicação não respondeu ao health check. Verifique os logs com 'docker-compose logs'."
    exit 1
fi

echo ""
echo "=================="
echo "DEMO PRONTA"
echo "=================="
echo "🌐 Aplicação disponível em: http://localhost:8000"
echo ""
echo "Para parar os serviços, execute: docker-compose down"
echo ""
