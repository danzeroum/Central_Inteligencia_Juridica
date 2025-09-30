#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Validando implementação MCP - Fase 1"
echo "=========================================="

BASE_URL="${BASE_URL:-http://localhost:8000}"

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0

check_endpoint() {
    local name=$1
    local endpoint=$2
    local expected_field=$3

    echo -n "Testando $name... "

    if response=$(curl -sf "$BASE_URL$endpoint" 2>&1); then
        if echo "$response" | jq -e ".$expected_field" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ PASS${NC}"
            ((passed++))
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} (campo '$expected_field' ausente)"
            ((failed++))
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (endpoint inacessível)"
        ((failed++))
        return 1
    fi
}

check_json_structure() {
    local name=$1
    local endpoint=$2
    local jq_query=$3

    echo -n "Validando $name... "

    if response=$(curl -sf "$BASE_URL$endpoint" 2>&1); then
        if echo "$response" | jq -e "$jq_query" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ PASS${NC}"
            ((passed++))
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} (estrutura inválida)"
            echo "Query: $jq_query"
            ((failed++))
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (endpoint inacessível)"
        ((failed++))
        return 1
    fi
}

echo ""
echo "📋 1. Testando endpoints MCP..."
echo "--------------------------------"

check_endpoint "Capabilities Endpoint" "/api/v1/agents/capabilities" "protocol"
check_endpoint "Agent List" "/api/v1/agents" "total"
check_endpoint "Supervisor Details" "/api/v1/agents/supervisor_agent" "agent_id"

echo ""
echo "🔍 2. Validando estrutura MCP..."
echo "--------------------------------"

check_json_structure \
    "MCP Protocol Version" \
    "/api/v1/agents/capabilities" \
    '.protocol == "MCP/1.0"'

check_json_structure \
    "Agents Array" \
    "/api/v1/agents/capabilities" \
    '.agents | type == "array" and length > 0'

check_json_structure \
    "Capabilities Summary" \
    "/api/v1/agents/capabilities" \
    '.capabilities_summary | has("capabilities") and has("tools")'

check_json_structure \
    "Supervisor Present" \
    "/api/v1/agents/capabilities" \
    '.agents[] | select(.agent_id == "supervisor_agent") | .agent_type == "SupervisorAgent"'

echo ""
echo "🎯 3. Testando invocação direta..."
echo "-----------------------------------"

echo -n "Invocando supervisor via MCP... "
if response=$(curl -sf -X POST "$BASE_URL/api/v1/agents/supervisor_agent/invoke" \
    -H "Content-Type: application/json" \
    -d '{"task_description": "Status TJSP"}' 2>&1); then
    if echo "$response" | jq -e '.status == "success"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((passed++))
    else
        echo -e "${RED}✗ FAIL${NC} (resposta inválida)"
        ((failed++))
    fi
else
    echo -e "${RED}✗ FAIL${NC} (invocação falhou)"
    ((failed++))
fi

echo ""
echo "🔍 4. Testando busca por capacidade..."
echo "---------------------------------------"

check_json_structure \
    "Search by Capability" \
    "/api/v1/agents/by-capability/task_routing" \
    '.total_matches >= 1 and (.agents[].agent_id == "supervisor_agent")'

echo ""
echo "=========================================="
echo "📊 RESULTADO FINAL"
echo "=========================================="
echo -e "${GREEN}✓ Passaram: $passed${NC}"
if [ $failed -gt 0 ]; then
    echo -e "${RED}✗ Falharam: $failed${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Verifique se a aplicação está rodando:${NC}"
    echo "   docker-compose up -d"
    echo "   # OU"
    echo "   uvicorn src.api.main:app --reload"
    exit 1
else
    echo -e "${GREEN}🎉 Todos os testes passaram!${NC}"
    echo ""
    echo "✅ FASE 1 (MCP Server Activation) CONCLUÍDA!"
    echo ""
    echo "🔗 Endpoints disponíveis:"
    echo "   - GET  $BASE_URL/api/v1/agents/capabilities"
    echo "   - GET  $BASE_URL/api/v1/agents"
    echo "   - GET  $BASE_URL/api/v1/agents/{agent_id}"
    echo "   - POST $BASE_URL/api/v1/agents/{agent_id}/invoke"
    echo "   - GET  $BASE_URL/api/v1/agents/by-capability/{capability}"
fi
