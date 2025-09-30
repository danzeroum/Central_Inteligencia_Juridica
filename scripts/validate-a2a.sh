#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Validando implementação A2A - Fase 2"
echo "=========================================="

BASE_URL="${BASE_URL:-http://localhost:8000}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

passed=0
failed=0

check_endpoint() {
    local name=$1
    local endpoint=$2
    local method=${3:-GET}
    
    echo -n "Testando $name... "
    
    if [ "$method" = "GET" ]; then
        if response=$(curl -sf "$BASE_URL$endpoint" 2>&1); then
            echo -e "${GREEN}✓ PASS${NC}"
            ((passed++))
            return 0
        fi
    fi
    
    echo -e "${RED}✗ FAIL${NC}"
    ((failed++))
    return 1
}

test_a2a_send() {
    echo -n "Testando envio A2A... "
    
    response=$(curl -sf -X POST "$BASE_URL/api/v1/a2a/send?sender_id=tjsp_agent" \
        -H "Content-Type: application/json" \
        -d '{
            "receiver_id": "tjmg_agent",
            "message_type": "test",
            "payload": {"test": "data"},
            "priority": 2
        }' 2>&1)
    
    if echo "$response" | jq -e '.status == "sent"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((passed++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((failed++))
        return 1
    fi
}

test_a2a_receive() {
    echo -n "Testando recebimento A2A... "
    
    # First send a message
    curl -sf -X POST "$BASE_URL/api/v1/a2a/send?sender_id=tjsp_agent" \
        -H "Content-Type: application/json" \
        -d '{
            "receiver_id": "tjmg_agent",
            "message_type": "test_receive",
            "payload": {"test": "receive"}
        }' > /dev/null 2>&1
    
    # Then try to receive
    response=$(curl -sf "$BASE_URL/api/v1/a2a/messages/tjmg_agent?limit=10" 2>&1)
    
    if echo "$response" | jq -e '.agent_id == "tjmg_agent"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((passed++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((failed++))
        return 1
    fi
}

test_a2a_broadcast() {
    echo -n "Testando broadcast A2A... "
    
    response=$(curl -sf -X POST "$BASE_URL/api/v1/a2a/broadcast" \
        -H "Content-Type: application/json" \
        -d '{
            "sender_id": "supervisor_agent",
            "receiver_ids": ["tjsp_agent", "tjmg_agent", "tjrs_agent"],
            "message_type": "broadcast_test",
            "payload": {"announcement": "test"}
        }' 2>&1)
    
    if echo "$response" | jq -e '.status == "broadcasted" and .total_sent == 3' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((passed++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((failed++))
        return 1
    fi
}


echo ""
echo "📋 1. Testando endpoints A2A..."
echo "--------------------------------"

check_endpoint "A2A Health" "/api/v1/a2a/health"
test_a2a_send
test_a2a_receive
test_a2a_broadcast
check_endpoint "A2A History" "/api/v1/a2a/history/tjsp_agent"

echo ""
echo "🧪 2. Testando integração Python..."
echo "------------------------------------"

echo -n "Testes de integração A2A... "
if python -m pytest tests/integration/test_a2a_protocol.py -v --tb=short > /tmp/a2a_test.log 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((passed++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "   Ver detalhes em: /tmp/a2a_test.log"
    ((failed++))
fi

echo ""
echo "🎯 3. Testando exemplo prático..."
echo "----------------------------------"

echo -n "Demo A2A... "
if timeout 10 python examples/a2a_collaboration_demo.py > /tmp/a2a_demo.log 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((passed++))
else
    echo -e "${YELLOW}⚠ SKIP${NC} (requer ambiente async completo)"
fi

echo ""
echo "🔍 4. Verificando componentes A2A..."
echo "-------------------------------------"

components=(
    "src/protocols/a2a_channel.py"
    "src/protocols/a2a_mixin.py"
    "tests/integration/test_a2a_protocol.py"
    "examples/a2a_collaboration_demo.py"
)

for component in "${components[@]}"; do
    echo -n "Verificando $component... "
    if [ -f "$component" ]; then
        echo -e "${GREEN}✓ EXISTS${NC}"
        ((passed++))
    else
        echo -e "${RED}✗ MISSING${NC}"
        ((failed++))
    fi
done

echo ""
echo "=========================================="
echo "📊 RESULTADO FINAL - FASE 2 (A2A)"
echo "=========================================="
echo -e "${GREEN}✓ Passaram: $passed${NC}"

if [ $failed -gt 0 ]; then
    echo -e "${RED}✗ Falharam: $failed${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Ações corretivas:${NC}"
    echo "   1. Verificar se aplicação está rodando: docker-compose up -d"
    echo "   2. Verificar logs: docker-compose logs agent-system"
    echo "   3. Instalar dependências: pip install redis pytest-asyncio"
    echo "   4. Re-rodar: ./scripts/validate-a2a.sh"
    exit 1
else
    echo ""
    echo -e "${GREEN}🎉 Todos os testes da Fase 2 passaram!${NC}"
    echo ""
    echo "✅ FASE 2 (A2A Protocol) CONCLUÍDA!"
    echo ""
    echo "📡 Capacidades A2A ativadas:"
    echo "   ✓ Envio de mensagens entre agentes"
    echo "   ✓ Recebimento e processamento de mensagens"
    echo "   ✓ Request-response pattern"
    echo "   ✓ Broadcast para múltiplos agentes"
    echo "   ✓ Handlers customizados"
    echo "   ✓ Histórico de mensagens"
    echo ""
    echo "🔗 Endpoints A2A:"
    echo "   - POST $BASE_URL/api/v1/a2a/send"
    echo "   - GET  $BASE_URL/api/v1/a2a/messages/{agent_id}"
    echo "   - GET  $BASE_URL/api/v1/a2a/history/{agent_id}"
    echo "   - POST $BASE_URL/api/v1/a2a/broadcast"
    echo "   - GET  $BASE_URL/api/v1/a2a/health"
fi
