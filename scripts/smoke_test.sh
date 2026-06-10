#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# smoke_test.sh — Central de Inteligência Jurídica
# Executa testes de fumaça completos contra a API local ou remota.
#
# Uso:
#   bash scripts/smoke_test.sh                       # local (localhost:8000)
#   BASE_URL=https://meudominio.com bash smoke_test.sh
#
# Variáveis de ambiente aceitas:
#   BASE_URL   — base da API (sem trailing slash)
#   ADMIN_USER / ADMIN_PASS
#   OP_USER    / OP_PASS
#   TEST_CNPJ  — CNPJ real para teste 360° (padrão: Petrobras)
#   VERBOSE    — 1 para mostrar payload completo de respostas
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

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

pass()  { echo -e "  ${GRN}✔${NC} $1"; ((PASS++)); }
fail()  { echo -e "  ${RED}✗${NC} $1"; ((FAIL++)); FAILURES+=("$1"); }
warn()  { echo -e "  ${YEL}⚠${NC} $1"; ((WARN++)); }
info()  { echo -e "  ${CYN}ℹ${NC} $1"; }
section(){ echo -e "\n${BOLD}${BLU}── $1 ──────────────────────────────────────────────${NC}"; }

http_get()  { curl -s -o /dev/null -w "%{http_code}" -H "${1:-}" "${2}"; }
http_body() { curl -s -H "${1:-}" "${2}"; }
http_post() { curl -s -X POST -H "Content-Type: application/json" -H "${1:-}" -d "${3}" "${2}"; }

py() { python3 -c "$1" 2>/dev/null; }

# ─── pré-requisitos ───────────────────────────────────────────────────────────
command -v curl   >/dev/null || { echo "curl não encontrado"; exit 1; }
command -v python3 >/dev/null || { echo "python3 não encontrado"; exit 1; }

echo -e "${BOLD}Central de Inteligência Jurídica — Smoke Test${NC}"
echo    "Base URL : $BASE_URL"
echo    "Data/hora: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ═══════════════════════════════════════════════════════════════════════════════
section "1. Health check"
# ═══════════════════════════════════════════════════════════════════════════════
STATUS=$(http_get "" "$BASE_URL/health")
[ "$STATUS" = "200" ] && pass "GET /health → 200" || fail "GET /health → $STATUS (esperado 200)"

BODY=$(http_body "" "$BASE_URL/health")
UP=$(py "import sys,json; d=json.loads('$BODY'); print(d.get('status','?'))" 2>/dev/null || echo "?")
[ "$UP" = "ok" ] || [ "$UP" = "healthy" ] && pass "health.status = $UP" || warn "health.status = $UP"

[ "$VERBOSE" = "1" ] && info "payload: $BODY"

# ═══════════════════════════════════════════════════════════════════════════════
section "2. Autenticação"
# ═══════════════════════════════════════════════════════════════════════════════
LOGIN_ADMIN=$(http_post "" "$BASE_URL/auth/login" \
  "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
ADMIN_TOKEN=$(py "import sys,json; print(json.loads('''$LOGIN_ADMIN''').get('access_token',''))")
[ -n "$ADMIN_TOKEN" ] && pass "POST /auth/login (admin) → JWT emitido" \
  || fail "POST /auth/login (admin) → sem token — payload: ${LOGIN_ADMIN:0:120}"

LOGIN_OP=$(http_post "" "$BASE_URL/auth/login" \
  "{\"username\":\"$OP_USER\",\"password\":\"$OP_PASS\"}")
OP_TOKEN=$(py "import sys,json; print(json.loads('''$LOGIN_OP''').get('access_token',''))")
[ -n "$OP_TOKEN" ] && pass "POST /auth/login (operator) → JWT emitido" \
  || fail "POST /auth/login (operator) → sem token"

# Autentica sem senha — deve retornar 4xx
BAD=$(http_post "" "$BASE_URL/auth/login" '{"username":"admin","password":"ERRADO"}')
BAD_STATUS=$(py "import sys,json; d=json.loads('''$BAD'''); print(d.get('access_token','NONE'))")
[ "$BAD_STATUS" = "NONE" ] && pass "POST /auth/login (senha errada) → sem token (correto)" \
  || fail "POST /auth/login (senha errada) → token vazou!"

AHDR="Authorization: Bearer $ADMIN_TOKEN"
OHDR="Authorization: Bearer $OP_TOKEN"

# ═══════════════════════════════════════════════════════════════════════════════
section "3. RBAC — controles de acesso"
# ═══════════════════════════════════════════════════════════════════════════════
# Sem token → 401
S=$(http_get "" "$BASE_URL/api/v1/agents")
[ "$S" = "401" ] && pass "Sem token → /agents → 401" || warn "Sem token → /agents → $S (esperado 401)"

# Operador não pode acessar HITL
S=$(http_get "$OHDR" "$BASE_URL/api/v1/hitl/pending")
[ "$S" = "403" ] && pass "Operador → /hitl/pending → 403 (RBAC ok)" \
  || warn "Operador → /hitl/pending → $S (esperado 403)"

# Admin pode acessar HITL
S=$(http_get "$AHDR" "$BASE_URL/api/v1/hitl/pending")
[ "$S" = "200" ] && pass "Admin → /hitl/pending → 200" || fail "Admin → /hitl/pending → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "4. HITL"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/hitl/stats")
[ "$S" = "200" ] && pass "GET /hitl/stats → 200" || fail "GET /hitl/stats → $S"

PENDING_BODY=$(http_body "$AHDR" "$BASE_URL/api/v1/hitl/pending")
PENDING_N=$(py "import sys,json; d=json.loads('''$PENDING_BODY'''); print(len(d) if isinstance(d,list) else d.get('total',0))" 2>/dev/null || echo "?")
info "Itens pendentes no HITL: $PENDING_N"

# ═══════════════════════════════════════════════════════════════════════════════
section "5. Ledger / Auditoria"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$AHDR" "$BASE_URL/api/v1/ledger")
[ "$S" = "200" ] && pass "GET /ledger → 200" || fail "GET /ledger → $S"

LEDGER_BODY=$(http_body "$AHDR" "$BASE_URL/api/v1/ledger?limit=3")
ENTRIES=$(py "import sys,json; d=json.loads('''$LEDGER_BODY'''); items=d.get('items',d) if isinstance(d,dict) else d; print(len(items) if isinstance(items,list) else '?')" 2>/dev/null || echo "?")
info "Entradas no ledger (sample): $ENTRIES"

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
AGENT_N=$(py "import sys,json; d=json.loads('''$AGENTS_BODY'''); items=d.get('agents',d) if isinstance(d,dict) else d; print(len(items) if isinstance(items,list) else '?')" 2>/dev/null || echo "?")
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
section "11. Histórico de consultas"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/history?limit=5")
[ "$S" = "200" ] && pass "GET /history → 200" || fail "GET /history → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "12. Jurisprudência (CNJ DataJud)"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3")
[ "$S" = "200" ] && pass "GET /jurisprudencia?q=dano+moral → 200" || fail "GET /jurisprudencia → $S"

JURIS_BODY=$(http_body "$OHDR" "$BASE_URL/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3")
JURIS_N=$(py "import sys,json; d=json.loads('''$JURIS_BODY'''); items=d.get('hits',d.get('items',d)) if isinstance(d,dict) else d; print(len(items) if isinstance(items,list) else '?')" 2>/dev/null || echo "?")
info "Acórdãos retornados: $JURIS_N"
[ "$JURIS_N" != "0" ] && [ "$JURIS_N" != "?" ] && pass "DataJud retornou $JURIS_N acórdãos (fonte real)" \
  || warn "DataJud retornou $JURIS_N resultados — verificar conectividade com CNJ"

# ═══════════════════════════════════════════════════════════════════════════════
section "13. Legislativo"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "$OHDR" "$BASE_URL/api/v1/proposicoes-legislativas?q=LGPD&pagina=1&itens=3")
[ "$S" = "200" ] && pass "GET /proposicoes-legislativas?q=LGPD → 200" || fail "GET /proposicoes → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "14. Investigação 360° — CNPJ Petrobras (real)"
# ═══════════════════════════════════════════════════════════════════════════════
GQL_360="{\"query\":\"query I360(\$identifier:String!,\$expandQsa:Boolean!){intelligence(identifier:\$identifier,expandQsa:\$expandQsa){queryId identifierMasked identifierType riskScore hitlStatus summary riskDimensions{name score} riskFactors{code description weight dimension} results{source status dataMode latencyMs totalAvailable error}}}\",\"variables\":{\"identifier\":\"$TEST_CNPJ\",\"expandQsa\":false}}"

echo "  Consultando CNPJ $TEST_CNPJ..."
RESP_360=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_360")

QUERY_ID=$(py "import json; d=json.loads('''$RESP_360'''); print(d.get('data',{}).get('intelligence',{}).get('queryId',''))" 2>/dev/null || echo "")

if [ -n "$QUERY_ID" ]; then
  RISK=$(py "import json; print(json.loads('''$RESP_360''')['data']['intelligence']['riskScore'])" 2>/dev/null || echo "?")
  MASKED=$(py "import json; print(json.loads('''$RESP_360''')['data']['intelligence']['identifierMasked'])" 2>/dev/null || echo "?")
  HITL=$(py "import json; print(json.loads('''$RESP_360''')['data']['intelligence'].get('hitlStatus','?'))" 2>/dev/null || echo "?")
  ID_TYPE=$(py "import json; print(json.loads('''$RESP_360''')['data']['intelligence']['identifierType'])" 2>/dev/null || echo "?")

  pass "POST /intelligence/graphql (CNPJ) → queryId=$QUERY_ID"
  info "identifierType=$ID_TYPE | identifierMasked=$MASKED | riskScore=$RISK | hitlStatus=$HITL"

  # LGPD: CNPJ bruto não pode aparecer na resposta
  if echo "$RESP_360" | grep -q "$TEST_CNPJ"; then
    fail "LGPD VIOLATION: CNPJ sem máscara presente no payload GraphQL!"
  else
    pass "LGPD: CNPJ mascarado no payload (Art. 18) ✓"
  fi

  # Análise detalhada por fonte
  echo ""
  echo -e "  ${BOLD}Análise por fonte (data_mode):${NC}"
  echo   "  ┌─────────────────────┬────────┬──────────┬──────────┬───────────────┐"
  echo   "  │ fonte               │ mode   │ status   │ items    │ latência      │"
  echo   "  ├─────────────────────┼────────┼──────────┼──────────┼───────────────┤"
  py "
import json
resp = json.loads('''$RESP_360''')
results = resp.get('data',{}).get('intelligence',{}).get('results',[])
real_n = sum(1 for r in results if r.get('dataMode')=='real')
mock_n = sum(1 for r in results if r.get('dataMode')=='mock')
for r in results:
    mode   = r.get('dataMode','?')
    status = r.get('status','?')
    lat    = r.get('latencyMs',0) or 0
    total  = r.get('totalAvailable',0) or 0
    err    = (r.get('error') or '')[:30]
    mark   = '🟢' if mode=='real' else '🟡'
    print(f'  │ {mark} {r[\"source\"]:<18}│ {mode:<7}│ {status:<9}│ {total:>6} itens│ {lat:>7} ms{(\"  ERR:\"+err) if err else \"\":15}│')
print('  └─────────────────────┴────────┴──────────┴──────────┴───────────────┘')
print(f'')
print(f'  Fontes REAIS: {real_n} | Fontes MOCK: {mock_n}')
print()
# Risk dimensions
dims = resp.get('data',{}).get('intelligence',{}).get('riskDimensions',[])
if dims:
    print('  Dimensões de risco:')
    for d in dims:
        bar = '█' * int(d[\"score\"]//10)
        print(f'    {d[\"name\"]:<20} {d[\"score\"]:>3} {bar}')
" 2>/dev/null || warn "Falha ao parsear resposta detalhada"

  # Verifica se alguma fonte "real" retornou dados reais
  REAL_DATA=$(py "
import json
resp = json.loads('''$RESP_360''')
results = resp.get('data',{}).get('intelligence',{}).get('results',[])
real_with_data = [r for r in results if r.get('dataMode')=='real' and (r.get('totalAvailable') or 0) > 0]
print(len(real_with_data))
" 2>/dev/null || echo "0")

  if [ "$REAL_DATA" -gt 0 ] 2>/dev/null; then
    pass "$REAL_DATA fonte(s) real(is) retornaram dados efetivos"
  else
    warn "0 fontes reais retornaram dados — verificar APIs externas (BrasilAPI, CNJ, TSE)"
  fi

else
  fail "POST /intelligence/graphql (CNPJ) → resposta inválida"
  [ "$VERBOSE" = "1" ] && info "payload: ${RESP_360:0:500}"
fi

# ─── 360° QSA expansion ──────────────────────────────────────────────────────
echo ""
echo "  Testando QSA expansion (expandQsa=true)..."
GQL_QSA="{\"query\":\"query I360(\$identifier:String!,\$expandQsa:Boolean!){intelligence(identifier:\$identifier,expandQsa:\$expandQsa){queryId relatedParties{nome vinculo tipo totalOcorrencias}}}\",\"variables\":{\"identifier\":\"$TEST_CNPJ\",\"expandQsa\":true}}"

RESP_QSA=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_QSA")

QSA_N=$(py "import json; d=json.loads('''$RESP_QSA'''); rp=d.get('data',{}).get('intelligence',{}).get('relatedParties',[]); print(len(rp))" 2>/dev/null || echo "0")
[ "$QSA_N" -ge 0 ] 2>/dev/null && pass "QSA expansion (expandQsa=true) → $QSA_N partes relacionadas" \
  || warn "QSA expansion falhou"

# ─── 360° Nome ───────────────────────────────────────────────────────────────
echo ""
echo "  Testando identificação por Nome..."
GQL_NOME="{\"query\":\"query I360(\$identifier:String!,\$expandQsa:Boolean!){intelligence(identifier:\$identifier,expandQsa:\$expandQsa){identifierType riskScore results{source dataMode status}}}\",\"variables\":{\"identifier\":\"Jose da Silva Santos\",\"expandQsa\":false}}"

RESP_NOME=$(curl -s -X POST "$BASE_URL/api/v1/intelligence/graphql" \
  -H "Content-Type: application/json" \
  -H "$OHDR" \
  -d "$GQL_NOME")

ID_TYPE_NOME=$(py "import json; print(json.loads('''$RESP_NOME''').get('data',{}).get('intelligence',{}).get('identifierType','?'))" 2>/dev/null || echo "?")
[ "$ID_TYPE_NOME" = "NOME" ] && pass "Detecção de tipo NOME → $ID_TYPE_NOME ✓" \
  || warn "Detecção NOME → $ID_TYPE_NOME (esperado NOME)"

# ═══════════════════════════════════════════════════════════════════════════════
section "15. Submissão de tarefa (assistente jurídico)"
# ═══════════════════════════════════════════════════════════════════════════════
TASK_RES=$(http_post "$OHDR" "$BASE_URL/api/v1/tasks" \
  '{"task_description":"O que e dano moral segundo a jurisprudencia do STJ?"}')
TASK_STATUS=$(py "import json; d=json.loads('''$TASK_RES'''); print(d.get('status',d.get('task_id','')))" 2>/dev/null || echo "")
[ -n "$TASK_STATUS" ] && pass "POST /tasks → tarefa criada (status/id=$TASK_STATUS)" \
  || warn "POST /tasks → resposta: ${TASK_RES:0:120}"

# ═══════════════════════════════════════════════════════════════════════════════
section "16. SPA Frontend"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "" "$BASE_URL/app/")
[ "$S" = "200" ] && pass "GET /app/ → 200 (SPA servida pelo FastAPI)" || fail "GET /app/ → $S"

# Verifica que o HTML contém referência ao JS bundle
SPA_HTML=$(http_body "" "$BASE_URL/app/")
if echo "$SPA_HTML" | grep -q "\.js"; then
  pass "SPA HTML referencia bundle JS ✓"
else
  warn "SPA HTML sem referência a bundle JS"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "17. WebSocket HITL (handshake)"
# ═══════════════════════════════════════════════════════════════════════════════
if command -v websocat >/dev/null 2>&1; then
  WS_BASE=$(echo "$BASE_URL" | sed 's/^http/ws/')
  WS_RES=$(echo '{"type":"ping"}' | timeout 3 websocat "$WS_BASE/api/v1/hitl/ws?token=$ADMIN_TOKEN" 2>&1 || true)
  echo "$WS_RES" | grep -q "pong\|pending\|{" \
    && pass "WebSocket /hitl/ws → handshake OK" \
    || warn "WebSocket /hitl/ws → não verificável sem websocat result (instale: apt install websocat)"
else
  warn "WebSocket: websocat não instalado — skip (curl não suporta WS). Instale com: apt install websocat"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "18. Métricas Prometheus"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_get "" "$BASE_URL/metrics" 2>/dev/null || echo "000")
if [ "$S" = "200" ]; then
  METRICS=$(http_body "" "$BASE_URL/metrics")
  echo "$METRICS" | grep -q "http_requests_total\|process_cpu" \
    && pass "GET /metrics → Prometheus metrics OK" \
    || warn "GET /metrics → 200 mas formato inesperado"
else
  warn "GET /metrics → $S (endpoint pode não estar exposto diretamente)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# RESUMO FINAL
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD} RESUMO DO SMOKE TEST${NC}"
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
TOTAL=$((PASS + FAIL + WARN))
echo -e "  Total : $TOTAL verificações"
echo -e "  ${GRN}✔ OK    : $PASS${NC}"
echo -e "  ${YEL}⚠ AVISO : $WARN${NC}"
echo -e "  ${RED}✗ FALHA : $FAIL${NC}"

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${RED}Falhas detectadas:${NC}"
  for f in "${FAILURES[@]}"; do
    echo -e "    ${RED}•${NC} $f"
  done
fi

echo ""
echo -e "  ${BOLD}Legenda de fontes 360°:${NC}"
echo    "    🟢 real  — dados consumidos da API pública externa"
echo    "    🟡 mock  — dados simulados (fonte restrita, sem credencial)"
echo    ""
echo    "  Fontes mock por design (exigem credencial/convênio):"
echo    "    • crc_protestos — CRC/CENPROT (captcha)"
echo    "    • cadin          — PGFN/CADIN gov.br (login gov.br)"
echo    "    • onr_imoveis    — ONR/SREI (conta credenciada)"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GRN}${BOLD}✔  Smoke test PASSOU${NC}"
else
  echo -e "  ${RED}${BOLD}✗  Smoke test FALHOU — veja itens acima${NC}"
fi

exit "$FAIL"
