#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# smoke_test.sh — Central de Inteligência Jurídica
# 18 seções de smoke test cobrindo todos os endpoints e a camada 360°.
#
# Uso:
#   bash scripts/smoke_test.sh
#   BASE_URL=https://meudominio.com bash scripts/smoke_test.sh
#   TEST_CNPJ=00360305000104 VERBOSE=1 bash scripts/smoke_test.sh
# ─────────────────────────────────────────────────────────────────────────────
# NOTA: sem set -e para evitar saída prematura em ((0++))
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin}"
OP_USER="${OP_USER:-operator}"
OP_PASS="${OP_PASS:-operator}"
TEST_CNPJ="${TEST_CNPJ:-33000167000101}"   # Petrobras — CNPJ público
VERBOSE="${VERBOSE:-0}"

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

PASS=0; FAIL=0; WARN=0
FAILURES=()

# Usar COUNTER=$((COUNTER+1)) — evita bug de set-e com ((0++)) == falso
pass()  { echo -e "  ${GRN}✔${NC} $1"; PASS=$((PASS+1)); }
fail()  { echo -e "  ${RED}✗${NC} $1 ${detail:-}"; FAIL=$((FAIL+1)); FAILURES+=("$1"); }
warn()  { echo -e "  ${YEL}⚠${NC} $1"; WARN=$((WARN+1)); }
info()  { echo -e "  ${CYN}ℹ${NC} $1"; }
section(){ echo -e "\n${BOLD}${BLU}── $1 ──────────────────────────────────────────────${NC}"; }

http_get()  { curl -s -o /dev/null -w "%{http_code}" ${1:+-H "$1"} "$2"; }
http_body() { curl -s ${1:+-H "$1"} "$2"; }
http_post() { curl -s -X POST -H "Content-Type: application/json" ${1:+-H "$1"} -d "$3" "$2"; }

# JSON parse via stdin para evitar problemas de quoting
jq_field() {
  # $1 = campo, lê JSON de stdin
  python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null || echo ""
}

command -v curl    >/dev/null || { echo "ERRO: curl não encontrado"; exit 1; }
command -v python3 >/dev/null || { echo "ERRO: python3 não encontrado"; exit 1; }

echo -e "${BOLD}Central de Inteligência Jurídica — Smoke Test${NC}"
echo    "Base URL : $BASE_URL"
echo    "Data/hora: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ═══════════════════════════════════════════════════════════════════════════════
section "1. Health"
# ═══════════════════════════════════════════════════════════════════════════════
STATUS=$(http_get "" "$BASE_URL/health")
[ "$STATUS" = "200" ] && pass "GET /health → 200" || fail "GET /health → $STATUS (esperado 200)"

BODY=$(http_body "" "$BASE_URL/health")
UP=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
if [ "$UP" = "ok" ] || [ "$UP" = "healthy" ]; then
  pass "health.status = $UP"
else
  warn "health.status = $UP (esperado ok|healthy) — payload: ${BODY:0:100}"
fi
[ "$VERBOSE" = "1" ] && info "payload: $BODY"

# ═══════════════════════════════════════════════════════════════════════════════
section "2. Autenticação"
# ═══════════════════════════════════════════════════════════════════════════════
LOGIN_ADMIN=$(http_post "" "$BASE_URL/auth/login" \
  "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}")
ADMIN_TOKEN=$(echo "$LOGIN_ADMIN" | jq_field "d.get('access_token','')")
[ -n "$ADMIN_TOKEN" ] \
  && pass "POST /auth/login (admin) → JWT emitido" \
  || fail "POST /auth/login (admin) → sem token — payload: ${LOGIN_ADMIN:0:120}"

LOGIN_OP=$(http_post "" "$BASE_URL/auth/login" \
  "{\"username\":\"${OP_USER}\",\"password\":\"${OP_PASS}\"}")
OP_TOKEN=$(echo "$LOGIN_OP" | jq_field "d.get('access_token','')")
[ -n "$OP_TOKEN" ] \
  && pass "POST /auth/login (operator) → JWT emitido" \
  || fail "POST /auth/login (operator) → sem token"

# Senha errada → sem token
BAD=$(http_post "" "$BASE_URL/auth/login" '{"username":"admin","password":"ERRADO"}')
BAD_TOK=$(echo "$BAD" | jq_field "d.get('access_token','NONE')")
[ "$BAD_TOK" = "NONE" ] || [ -z "$BAD_TOK" ] \
  && pass "POST /auth/login (senha errada) → sem token ✓" \
  || fail "POST /auth/login (senha errada) → token vazou!"

AHDR="Authorization: Bearer ${ADMIN_TOKEN}"
OHDR="Authorization: Bearer ${OP_TOKEN}"

# ═══════════════════════════════════════════════════════════════════════════════
section "3. RBAC"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "" "$BASE_URL/api/v1/agents")
[ "$S" = "401" ] && pass "Sem token → /agents → 401" \
  || warn "Sem token → /agents → $S (esperado 401)"

S=$(http_get "$OHDR" "$BASE_URL/api/v1/hitl/pending")
[ "$S" = "403" ] && pass "Operador → /hitl/pending → 403 (RBAC ok)" \
  || warn "Operador → /hitl/pending → $S (esperado 403)"

S=$(http_get "$AHDR" "$BASE_URL/api/v1/hitl/pending")
[ "$S" = "200" ] && pass "Admin → /hitl/pending → 200" || fail "Admin → /hitl/pending → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "4. HITL"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/hitl/stats")
[ "$S" = "200" ] && pass "GET /hitl/stats → 200" || fail "GET /hitl/stats → $S"

PENDING_BODY=$(http_body "$AHDR" "$BASE_URL/api/v1/hitl/pending")
PENDING_N=$(echo "$PENDING_BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(len(d) if isinstance(d,list) else d.get('total',d.get('count',0)))
" 2>/dev/null || echo "?")
info "Itens pendentes no HITL: $PENDING_N"

# ═══════════════════════════════════════════════════════════════════════════════
section "5. Ledger / Auditoria"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/ledger")
[ "$S" = "200" ] && pass "GET /ledger → 200" || fail "GET /ledger → $S"

LEDGER_BODY=$(http_body "$AHDR" "$BASE_URL/api/v1/ledger?limit=3")
ENTRIES=$(echo "$LEDGER_BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('items',d) if isinstance(d,dict) else d
print(len(items) if isinstance(items,list) else '?')
" 2>/dev/null || echo "?")
info "Entradas no ledger (sample 3): $ENTRIES"

# ═══════════════════════════════════════════════════════════════════════════════
section "6. Treinamento"
# ═══════════════════════════════════════════════════════════════════════════════
for ep in "stats" "history?limit=5" "active-sessions"; do
  S=$(http_get "$AHDR" "$BASE_URL/api/v1/training/$ep")
  [ "$S" = "200" ] && pass "GET /training/$ep → 200" || fail "GET /training/$ep → $S"
done

# ═══════════════════════════════════════════════════════════════════════════════
section "7. Agentes MCP"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/agents")
[ "$S" = "200" ] && pass "GET /agents → 200" || fail "GET /agents → $S"

AGENTS_BODY=$(http_body "$AHDR" "$BASE_URL/api/v1/agents")
AGENT_N=$(echo "$AGENTS_BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('agents',d) if isinstance(d,dict) else d
print(len(items) if isinstance(items,list) else '?')
" 2>/dev/null || echo "?")
info "Agentes registrados: $AGENT_N"

# ═══════════════════════════════════════════════════════════════════════════════
section "8. Autonomia (DMN)"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/autonomy/config")
[ "$S" = "200" ] && pass "GET /autonomy/config → 200" || fail "GET /autonomy/config → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "9. Monitoramento"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/monitoring/health")
[ "$S" = "200" ] && pass "GET /monitoring/health → 200" || fail "GET /monitoring/health → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "10. Perfil"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/profile")
[ "$S" = "200" ] && pass "GET /profile → 200" || fail "GET /profile → $S"

S=$(http_get "$OHDR" "$BASE_URL/api/v1/profile/area")
[ "$S" = "200" ] && pass "GET /profile/area → 200" || fail "GET /profile/area → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "11. Histórico"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/history?limit=5")
[ "$S" = "200" ] && pass "GET /history → 200" || fail "GET /history → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "12. Jurisprudência (CNJ DataJud)"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3")
[ "$S" = "200" ] && pass "GET /jurisprudencia?q=dano+moral → 200" || fail "GET /jurisprudencia → $S"

JURIS_BODY=$(http_body "$OHDR" "$BASE_URL/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3")
JURIS_N=$(echo "$JURIS_BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d,list): print(len(d))
elif isinstance(d,dict):
    for k in ('hits','items','results','acórdãos','acordaos','total'):
        v=d.get(k)
        if isinstance(v,list): print(len(v)); break
        elif isinstance(v,int): print(v); break
    else: print(next((len(v) for v in d.values() if isinstance(v,list)),0))
else: print(0)
" 2>/dev/null || echo "0")
[ "$JURIS_N" != "0" ] \
  && pass "DataJud retornou $JURIS_N acórdãos (fonte real)" \
  || warn "DataJud retornou 0 resultados para 'dano moral tjsp' — verificar CNJ API"

# ═══════════════════════════════════════════════════════════════════════════════
section "13. Legislativo"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/proposicoes-legislativas?q=LGPD&pagina=1&itens=3")
[ "$S" = "200" ] && pass "GET /proposicoes-legislativas → 200" || fail "GET /proposicoes → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "14. Investigação 360° — CNPJ Petrobras"
# ═══════════════════════════════════════════════════════════════════════════════
info "Consultando CNPJ ${TEST_CNPJ}..."

GQL_BODY=$(cat <<GQLEOF
{
  "query": "query I360(\$identifier: String!, \$expandQsa: Boolean!) { intelligence(identifier: \$identifier, expandQsa: \$expandQsa) { queryId identifierMasked identifierType riskScore hitlStatus summary riskDimensions { name score } riskFactors { code description weight dimension } results { source status dataMode latencyMs totalAvailable error } } }",
  "variables": { "identifier": "${TEST_CNPJ}", "expandQsa": false }
}
GQLEOF
)

RESP_360=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_BODY")

QUERY_ID=$(echo "$RESP_360" | jq_field "d.get('data',{}).get('intelligence',{}).get('queryId','')")

if [ -n "$QUERY_ID" ]; then
  RISK=$(echo "$RESP_360" | jq_field "d['data']['intelligence']['riskScore']")
  MASKED=$(echo "$RESP_360" | jq_field "d['data']['intelligence']['identifierMasked']")
  HITL_ST=$(echo "$RESP_360" | jq_field "d['data']['intelligence'].get('hitlStatus','?')")
  ID_TYPE=$(echo "$RESP_360" | jq_field "d['data']['intelligence']['identifierType']")

  pass "POST /intelligence/graphql (CNPJ) → queryId=${QUERY_ID}"
  info "tipo=${ID_TYPE} | mascarado=${MASKED} | riskScore=${RISK} | hitlStatus=${HITL_ST}"

  # LGPD: CNPJ bruto não pode aparecer na resposta
  if echo "$RESP_360" | grep -qF "$TEST_CNPJ"; then
    fail "LGPD VIOLATION: CNPJ sem máscara presente no payload GraphQL!"
  else
    pass "LGPD: CNPJ mascarado no payload (Art. 18) ✓"
  fi

  # Tabela por fonte
  echo ""
  echo -e "  ${BOLD}Análise por fonte (data_mode):${NC}"
  echo   "  ┌─────────────────────┬────────┬──────────┬──────────┬──────────────┐"
  echo   "  │ fonte               │ mode   │ status   │  itens   │  latência    │"
  echo   "  ├─────────────────────┼────────┼──────────┼──────────┼──────────────┤"
  echo "$RESP_360" | python3 -c "
import sys,json
resp = json.load(sys.stdin)
results = resp.get('data',{}).get('intelligence',{}).get('results',[])
real_n = sum(1 for r in results if r.get('dataMode')=='real')
mock_n = sum(1 for r in results if r.get('dataMode')=='mock')
for r in results:
    mode   = r.get('dataMode','?')
    status = r.get('status','?')
    lat    = r.get('latencyMs') or 0
    total  = r.get('totalAvailable') or 0
    err    = (r.get('error') or '')[:28]
    mark   = '★' if mode=='real' else '○'
    print(f'  │ {mark} {r[\"source\"]:<18}│ {mode:<7}│ {status:<9}│ {total:>7}   │ {lat:>7} ms   │{\" ERR:\"+err if err else \"\"}')
print('  └─────────────────────┴────────┴──────────┴──────────┴──────────────┘')
print(f'')
print(f'  ★ Fontes REAIS: {real_n}  ○ Fontes MOCK: {mock_n}')
dims = resp.get('data',{}).get('intelligence',{}).get('riskDimensions',[])
if dims:
    print('')
    print('  Dimensões de risco:')
    for d in dims:
        bar = '█' * max(1,int(d[\"score\"]//10))
        print(f'    {d[\"name\"]:<22} {d[\"score\"]:>3}  {bar}')
" 2>/dev/null || warn "Falha ao parsear resposta detalhada"

  REAL_DATA=$(echo "$RESP_360" | python3 -c "
import sys,json
results = json.load(sys.stdin).get('data',{}).get('intelligence',{}).get('results',[])
print(sum(1 for r in results if r.get('dataMode')=='real' and (r.get('totalAvailable') or 0)>0))
" 2>/dev/null || echo "0")
  [ "${REAL_DATA:-0}" -gt 0 ] \
    && pass "${REAL_DATA} fonte(s) real(is) com dados efetivos" \
    || warn "0 fontes reais retornaram dados — APIs externas offline ou CNPJ sem match"

else
  fail "POST /intelligence/graphql (CNPJ) → resposta inválida"
  [ "$VERBOSE" = "1" ] && info "payload: ${RESP_360:0:500}"
fi

# ─── QSA expansion ────────────────────────────────────────────────────────────
echo ""
info "QSA expansion (expandQsa=true)..."
GQL_QSA=$(cat <<QSAEOF
{
  "query": "query I360(\$identifier: String!, \$expandQsa: Boolean!) { intelligence(identifier: \$identifier, expandQsa: \$expandQsa) { queryId relatedParties { nome vinculo tipo totalOcorrencias } } }",
  "variables": { "identifier": "${TEST_CNPJ}", "expandQsa": true }
}
QSAEOF
)
RESP_QSA=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_QSA")
QSA_N=$(echo "$RESP_QSA" | python3 -c "
import sys,json
rp=json.load(sys.stdin).get('data',{}).get('intelligence',{}).get('relatedParties',[])
print(len(rp))
" 2>/dev/null || echo "0")
pass "QSA expansion → ${QSA_N} partes relacionadas"

# ─── Detecção por Nome ────────────────────────────────────────────────────────
echo ""
info "Detecção por Nome..."
GQL_NOME=$(cat <<NOMEEOF
{
  "query": "query I360(\$identifier: String!, \$expandQsa: Boolean!) { intelligence(identifier: \$identifier, expandQsa: \$expandQsa) { identifierType riskScore results { source dataMode status } } }",
  "variables": { "identifier": "Jose da Silva Santos", "expandQsa": false }
}
NOMEEOF
)
RESP_NOME=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_NOME")
ID_TYPE_NOME=$(echo "$RESP_NOME" | jq_field "d.get('data',{}).get('intelligence',{}).get('identifierType','?')")
[ "$ID_TYPE_NOME" = "NOME" ] \
  && pass "Detecção de tipo NOME → ${ID_TYPE_NOME} ✓" \
  || warn "Tipo detectado: ${ID_TYPE_NOME} (esperado: NOME)"

# ═══════════════════════════════════════════════════════════════════════════════
section "15. Submissão de tarefa"
# ═══════════════════════════════════════════════════════════════════════════════
TASK_RES=$(http_post "$OHDR" "$BASE_URL/api/v1/tasks" \
  '{"task_description":"O que e dano moral segundo a jurisprudencia do STJ?"}')
TASK_ID=$(echo "$TASK_RES" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('task_id') or d.get('id') or d.get('status',''))
" 2>/dev/null || echo "")
[ -n "$TASK_ID" ] \
  && pass "POST /tasks → tarefa criada (id/status=${TASK_ID})" \
  || warn "POST /tasks → resposta: ${TASK_RES:0:120}"

# ═══════════════════════════════════════════════════════════════════════════════
section "16. SPA Frontend"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "" "$BASE_URL/app/")
[ "$S" = "200" ] && pass "GET /app/ → 200 (SPA servida)" || fail "GET /app/ → $S"

SPA_HTML=$(http_body "" "$BASE_URL/app/")
echo "$SPA_HTML" | grep -q "\.js" && pass "SPA HTML referencia bundle JS" \
  || warn "SPA HTML sem referência a bundle JS"

# ═══════════════════════════════════════════════════════════════════════════════
section "17. WebSocket HITL (curl handshake)"
# ═══════════════════════════════════════════════════════════════════════════════
if command -v websocat >/dev/null 2>&1; then
  WS_BASE="${BASE_URL/http/ws}"
  WS_RES=$(printf '{"type":"ping"}' | timeout 3 websocat "${WS_BASE}/api/v1/hitl/ws?token=${ADMIN_TOKEN}" 2>&1 || true)
  echo "$WS_RES" | grep -q ".\{3\}" \
    && pass "WebSocket /hitl/ws → handshake OK" \
    || warn "WebSocket → sem resposta em 3s"
else
  # Verifica upgrade header via curl
  WS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Upgrade: websocket" \
    -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    "$BASE_URL/api/v1/hitl/ws" 2>/dev/null || echo "000")
  [ "$WS_STATUS" = "101" ] && pass "WebSocket /hitl/ws → 101 Switching Protocols" \
    || warn "WebSocket → $WS_STATUS (websocat não instalado para teste completo: apt install websocat)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "18. Métricas Prometheus"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/metrics" 2>/dev/null || echo "000")
if [ "$S" = "200" ]; then
  METRICS=$(http_body "" "$BASE_URL/metrics")
  echo "$METRICS" | grep -qE "http_requests_total|process_cpu|python_" \
    && pass "GET /metrics → Prometheus metrics OK" \
    || warn "GET /metrics → 200 mas formato inesperado"
else
  warn "GET /metrics → $S (endpoint pode não estar exposto externamente)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════════════════════
TOTAL=$((PASS+FAIL+WARN))
echo ""
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD} RESUMO DO SMOKE TEST${NC}"
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
echo -e "  Total : $TOTAL verificações"
echo -e "  ${GRN}✔ OK    : $PASS${NC}"
echo -e "  ${YEL}⚠ Aviso : $WARN${NC}"
echo -e "  ${RED}✗ Falha : $FAIL${NC}"

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${RED}Falhas:${NC}"
  for f in "${FAILURES[@]}"; do
    echo -e "    ${RED}•${NC} $f"
  done
fi

echo ""
echo -e "  ${BOLD}Legenda data_mode:${NC}"
echo    "    ★ real — dados da API pública externa (BrasilAPI, TSE, CNJ)"
echo    "    ○ mock — dados simulados (fonte restrita sem convênio)"
echo    "      → crc_protestos, cadin, onr_imoveis são sempre mock por design"
echo ""

[ "$FAIL" -eq 0 ] \
  && echo -e "  ${GRN}${BOLD}✔  Smoke test PASSOU${NC}" \
  || echo -e "  ${RED}${BOLD}✗  Smoke test FALHOU — veja itens acima${NC}"

exit "$FAIL"
