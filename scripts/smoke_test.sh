#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# smoke_test.sh — Central de Inteligência Jurídica
#
# Modo de execução (auto-detectado, ou forçado via SMOKE_MODE):
#
#   docker  (padrão quando o container está rodando):
#     Executa curl DENTRO do container → acessa localhost:8000 diretamente,
#     sem precisar expor a porta no host ou passar pelo nginx.
#     Comando: bash scripts/smoke_test.sh
#
#   http    (externo via nginx/domínio):
#     Usa BASE_URL para todas as chamadas (segue o caminho nginx → TLS).
#     Comando: SMOKE_MODE=http BASE_URL=https://dominio.com bash scripts/smoke_test.sh
#
# Variáveis de ambiente aceitas:
#   SMOKE_MODE      — docker|http  (padrão: docker se container estiver up)
#   CONTAINER       — nome do container (padrão: central-inteligencia-juridica)
#   BASE_URL        — usado apenas em SMOKE_MODE=http
#   ADMIN_USER/PASS — credenciais admin (padrão: admin/admin)
#   OP_USER/PASS    — credenciais operador (padrão: operator/operator)
#   TEST_CNPJ       — CNPJ para teste 360° (padrão: Petrobras)
#   VERBOSE         — 1 para mostrar payloads completos
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

CONTAINER="${CONTAINER:-central-inteligencia-juridica}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin}"
OP_USER="${OP_USER:-operator}"
OP_PASS="${OP_PASS:-operator}"
TEST_CNPJ="${TEST_CNPJ:-33000167000101}"
VERBOSE="${VERBOSE:-0}"

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

PASS=0; FAIL=0; WARN=0
FAILURES=()

pass()    { echo -e "  ${GRN}✔${NC} $1"; PASS=$((PASS+1)); }
fail()    { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL+1)); FAILURES+=("$1"); }
warn()    { echo -e "  ${YEL}⚠${NC} $1"; WARN=$((WARN+1)); }
info()    { echo -e "  ${CYN}ℹ${NC} $1"; }
section() { echo -e "\n${BOLD}${BLU}── $1 ──────────────────────────────────────────────${NC}"; }

command -v python3 >/dev/null || { echo "ERRO: python3 não encontrado"; exit 1; }

# ─── Auto-detect modo de execução ───────────────────────────────────────────
if [ -z "${SMOKE_MODE:-}" ]; then
  if docker inspect "$CONTAINER" >/dev/null 2>&1 \
      && [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
    SMOKE_MODE="docker"
  else
    SMOKE_MODE="http"
    BASE_URL="${BASE_URL:-http://localhost:8000}"
  fi
fi

if [ "$SMOKE_MODE" = "docker" ]; then
  IBASE="http://localhost:8000"
  _raw_curl() { docker exec "$CONTAINER" curl -s "$@" 2>/dev/null; }
  info_mode="docker exec $CONTAINER curl → $IBASE"
else
  command -v curl >/dev/null || { echo "ERRO: curl não encontrado"; exit 1; }
  IBASE="${BASE_URL:-http://localhost:8000}"
  _raw_curl() { curl -s "$@" 2>/dev/null; }
  info_mode="curl direto → $IBASE"
fi

http_code() { _raw_curl -o /dev/null -w "%{http_code}" ${1:+-H "$1"} "$IBASE$2"; }
http_body() { _raw_curl ${1:+-H "$1"} "$IBASE$2"; }
http_post() { _raw_curl -X POST -H "Content-Type: application/json" ${1:+-H "$1"} -d "$3" "$IBASE$2"; }

jval() {
  # lê JSON de stdin, avalia a expressão python $1 sobre o dict d
  python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null || echo ""
}

# ─── Auto-detecção de credenciais do AUTH_USERS do container ────────────────
# Só ativa quando SMOKE_MODE=docker e o usuário não passou ADMIN_USER explícito.
# Usa variável de ambiente AUTH_JSON para passar o dado ao Python (evita
# conflito pipe+heredoc onde heredoc sobrescreve stdin do pipe).
_CRED_AUTODETECT=0
if [ "$SMOKE_MODE" = "docker" ] && [ "${ADMIN_USER}" = "admin" ]; then
  _AUTH_USERS_JSON=$(docker exec "$CONTAINER" sh -c 'printf "%s" "$AUTH_USERS"' 2>/dev/null || echo "")
  if [ -n "$_AUTH_USERS_JSON" ] && [ "$_AUTH_USERS_JSON" != "{}" ]; then
    _DETECTED=$(AUTH_JSON="$_AUTH_USERS_JSON" python3 -c '
import json, os, sys
try:
    users = json.loads(os.environ.get("AUTH_JSON","{}"))
    admin = next(
        ((k, v["password"]) for k,v in users.items() if "admin" in v.get("roles",[])),
        None
    )
    op = next(
        ((k, v["password"]) for k,v in users.items()
         if any(r in v.get("roles",[]) for r in ("operator","auditor"))
         and "admin" not in v.get("roles",[])),
        admin
    )
    if admin:
        print(f"ADMIN_USER={admin[0]}")
        print(f"ADMIN_PASS={admin[1]}")
    if op:
        print(f"OP_USER={op[0]}")
        print(f"OP_PASS={op[1]}")
    print("AUTODETECT=1")
except Exception as e:
    sys.stderr.write(f"autodetect error: {e}\n")
' 2>/dev/null || echo "")
    if echo "$_DETECTED" | grep -q "AUTODETECT=1"; then
      eval "$_DETECTED"
      _CRED_AUTODETECT=1
    fi
  fi
fi

echo -e "${BOLD}Central de Inteligência Jurídica — Smoke Test${NC}"
echo    "Modo     : $info_mode"
if [ "$_CRED_AUTODETECT" = "1" ]; then
  echo  "Auth     : credenciais detectadas do AUTH_USERS (admin=${ADMIN_USER}, op=${OP_USER})"
elif [ "$SMOKE_MODE" = "docker" ] && [ -z "$_AUTH_USERS_JSON" ]; then
  echo  "Auth     : AUTH_USERS vazio no container — usando padrões (admin=${ADMIN_USER})"
  echo  "           DICA: defina AUTH_USERS no .env ou passe: ADMIN_PASS=suasenha bash smoke_test.sh"
else
  echo  "Auth     : ADMIN_USER=${ADMIN_USER} OP_USER=${OP_USER} (passe ADMIN_PASS=xxx se falhar)"
fi
echo    "Data/hora: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ═══════════════════════════════════════════════════════════════════════════════
section "0. Modos de integração (mock vs real)"
# ═══════════════════════════════════════════════════════════════════════════════
# Lê variáveis de ambiente do container para saber quais fontes estão em mock
if [ "$SMOKE_MODE" = "docker" ]; then
  ENV_OUT=$(docker exec "$CONTAINER" env 2>/dev/null || echo "")
  for SRC in DATAJUD DJEN RECEITA_CNPJ TSE CRC_PROTESTOS CADIN ONR_IMOVEIS; do
    MODE=$(echo "$ENV_OUT" | grep "^INTEGRATIONS_${SRC}_MODE=" | cut -d= -f2)
    MODE="${MODE:-mock}"
    if [ "$MODE" = "real" ]; then
      pass "INTEGRATIONS_${SRC}_MODE = real ✓"
    else
      warn "INTEGRATIONS_${SRC}_MODE = mock (dados simulados) — adicione ao .env para ativar real"
    fi
  done
else
  warn "Modo http: não é possível inspecionar variáveis do container"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "1. Health"
# ═══════════════════════════════════════════════════════════════════════════════
STATUS=$(http_code "" "/health")
[ "$STATUS" = "200" ] && pass "GET /health → 200" || fail "GET /health → $STATUS"

BODY=$(http_body "" "/health")
UP=$(echo "$BODY" | jval "d.get('status','?')")
if [ "$UP" = "ok" ] || [ "$UP" = "healthy" ]; then
  pass "health.status = $UP"
else
  warn "health.status = '$UP' — payload: ${BODY:0:120}"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "2. Autenticação"
# ═══════════════════════════════════════════════════════════════════════════════
LOGIN_ADMIN=$(http_post "" "/auth/login" \
  "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}")
ADMIN_TOKEN=$(echo "$LOGIN_ADMIN" | jval "d.get('access_token','')")
[ -n "$ADMIN_TOKEN" ] \
  && pass "POST /auth/login (admin) → JWT emitido" \
  || fail "POST /auth/login (admin) → sem token — payload: ${LOGIN_ADMIN:0:200}"

LOGIN_OP=$(http_post "" "/auth/login" \
  "{\"username\":\"${OP_USER}\",\"password\":\"${OP_PASS}\"}")
OP_TOKEN=$(echo "$LOGIN_OP" | jval "d.get('access_token','')")
[ -n "$OP_TOKEN" ] \
  && pass "POST /auth/login (operator) → JWT emitido" \
  || fail "POST /auth/login (operator) → sem token"

BAD=$(http_post "" "/auth/login" '{"username":"admin","password":"ERRADO"}')
BAD_TOK=$(echo "$BAD" | jval "d.get('access_token','NONE')")
[ -z "$BAD_TOK" ] || [ "$BAD_TOK" = "NONE" ] \
  && pass "POST /auth/login (senha errada) → sem token ✓" \
  || fail "POST /auth/login (senha errada) → token vazou!"

AHDR="Authorization: Bearer ${ADMIN_TOKEN}"
OHDR="Authorization: Bearer ${OP_TOKEN}"

# ═══════════════════════════════════════════════════════════════════════════════
section "3. RBAC"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "" "/api/v1/agents")
[ "$S" = "401" ] && pass "Sem token → /agents → 401" \
  || warn "Sem token → /agents → $S (esperado 401)"

S=$(http_code "$OHDR" "/api/v1/hitl/pending")
[ "$S" = "403" ] && pass "Operador → /hitl/pending → 403 ✓" \
  || warn "Operador → /hitl/pending → $S (esperado 403)"

S=$(http_code "$AHDR" "/api/v1/hitl/pending")
[ "$S" = "200" ] && pass "Admin → /hitl/pending → 200" \
  || fail "Admin → /hitl/pending → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "4. HITL"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$AHDR" "/api/v1/hitl/stats")
[ "$S" = "200" ] && pass "GET /hitl/stats → 200" || fail "GET /hitl/stats → $S"

PENDING_N=$(http_body "$AHDR" "/api/v1/hitl/pending" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(len(d) if isinstance(d,list) else d.get('total',d.get('count',0)))
" 2>/dev/null || echo "?")
info "Itens pendentes no HITL: $PENDING_N"

# ═══════════════════════════════════════════════════════════════════════════════
section "5. Ledger / Auditoria"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$AHDR" "/api/v1/ledger")
[ "$S" = "200" ] && pass "GET /ledger → 200" || fail "GET /ledger → $S"

ENTRIES=$(http_body "$AHDR" "/api/v1/ledger?limit=3" | python3 -c "
import sys,json; d=json.load(sys.stdin)
items=d.get('items',d) if isinstance(d,dict) else d
print(len(items) if isinstance(items,list) else '?')
" 2>/dev/null || echo "?")
info "Entradas no ledger (amostra): $ENTRIES"

# ═══════════════════════════════════════════════════════════════════════════════
section "6. Treinamento"
# ═══════════════════════════════════════════════════════════════════════════════
for ep in "stats" "history?limit=5" "active-sessions"; do
  S=$(http_code "$AHDR" "/api/v1/training/$ep")
  [ "$S" = "200" ] && pass "GET /training/$ep → 200" || fail "GET /training/$ep → $S"
done

# ═══════════════════════════════════════════════════════════════════════════════
section "7. Agentes MCP"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$AHDR" "/api/v1/agents")
[ "$S" = "200" ] && pass "GET /agents → 200" || fail "GET /agents → $S"

AGENT_N=$(http_body "$AHDR" "/api/v1/agents" | python3 -c "
import sys,json; d=json.load(sys.stdin)
items=d.get('agents',d) if isinstance(d,dict) else d
print(len(items) if isinstance(items,list) else '?')
" 2>/dev/null || echo "?")
info "Agentes registrados: $AGENT_N"

# ═══════════════════════════════════════════════════════════════════════════════
section "8. Autonomia (DMN)"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$AHDR" "/api/v1/autonomy/config")
[ "$S" = "200" ] && pass "GET /autonomy/config → 200" || fail "GET /autonomy/config → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "9. Monitoramento"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$AHDR" "/api/v1/monitoring/health")
[ "$S" = "200" ] && pass "GET /monitoring/health → 200" || fail "GET /monitoring/health → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "10. Perfil"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$OHDR" "/api/v1/profile")
[ "$S" = "200" ] && pass "GET /profile → 200" || fail "GET /profile → $S"

S=$(http_code "$OHDR" "/api/v1/profile/area")
[ "$S" = "200" ] && pass "GET /profile/area → 200" || fail "GET /profile/area → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "11. Histórico"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$OHDR" "/api/v1/history?limit=5")
[ "$S" = "200" ] && pass "GET /history → 200" || fail "GET /history → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "12. Jurisprudência (CNJ DataJud)"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$OHDR" "/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3")
[ "$S" = "200" ] && pass "GET /jurisprudencia → 200" || fail "GET /jurisprudencia → $S"

JURIS_N=$(http_body "$OHDR" "/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3" | python3 -c "
import sys,json; d=json.load(sys.stdin)
if isinstance(d,list): print(len(d))
elif isinstance(d,dict):
    for k in ('hits','items','results','acordaos','total'):
        v=d.get(k)
        if isinstance(v,list): print(len(v)); break
        elif isinstance(v,(int,float)) and k=='total': print(int(v)); break
    else: print(sum(len(v) for v in d.values() if isinstance(v,list)) or 0)
else: print(0)
" 2>/dev/null || echo "0")
[ "${JURIS_N:-0}" != "0" ] \
  && pass "DataJud retornou ${JURIS_N} acórdão(s)" \
  || warn "DataJud retornou 0 — verifique INTEGRATIONS_DATAJUD_MODE e CNJ API"

# ═══════════════════════════════════════════════════════════════════════════════
section "13. Legislativo"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "$OHDR" "/api/v1/proposicoes-legislativas?q=LGPD&pagina=1&itens=3")
[ "$S" = "200" ] && pass "GET /proposicoes-legislativas → 200" || fail "GET /proposicoes → $S"

# ═══════════════════════════════════════════════════════════════════════════════
section "14. Investigação 360° — CNPJ Petrobras"
# ═══════════════════════════════════════════════════════════════════════════════
info "Consultando CNPJ ${TEST_CNPJ}..."

GQL_BODY=$(cat <<'HEREDOC'
{
  "query": "query I360($identifier: String!, $expandQsa: Boolean!) { intelligence(identifier: $identifier, expandQsa: $expandQsa) { queryId identifierMasked identifierType riskScore hitlStatus riskDimensions { name score } results { source status dataMode latencyMs totalAvailable error } } }",
  "variables": {}
}
HEREDOC
)
# Injeta CNPJ no campo variables após o heredoc para evitar escaping
GQL_BODY=$(echo "$GQL_BODY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
d['variables']={'identifier':'${TEST_CNPJ}','expandQsa':False}
print(json.dumps(d))
")

RESP_360=$(http_post "$OHDR" "/api/v1/intelligence/graphql" "$GQL_BODY")
QUERY_ID=$(echo "$RESP_360" | jval "d.get('data',{}).get('intelligence',{}).get('queryId','')")

if [ -n "$QUERY_ID" ]; then
  RISK=$(echo "$RESP_360"   | jval "d['data']['intelligence']['riskScore']")
  MASKED=$(echo "$RESP_360" | jval "d['data']['intelligence']['identifierMasked']")
  HITL_ST=$(echo "$RESP_360"| jval "d['data']['intelligence'].get('hitlStatus','?')")
  ID_TYPE=$(echo "$RESP_360"| jval "d['data']['intelligence']['identifierType']")

  pass "POST /intelligence/graphql (CNPJ) → queryId=${QUERY_ID}"
  info "tipo=${ID_TYPE} | mascarado=${MASKED} | riskScore=${RISK} | hitlStatus=${HITL_ST}"

  # LGPD: CNPJ bruto não pode aparecer na resposta
  if echo "$RESP_360" | grep -qF "$TEST_CNPJ"; then
    fail "LGPD VIOLATION: CNPJ sem máscara no payload!"
  else
    pass "LGPD: CNPJ mascarado ✓"
  fi

  # Tabela por fonte
  echo ""
  echo -e "  ${BOLD}Fontes (data_mode):${NC}"
  echo   "  ┌─────────────────────┬────────┬──────────┬────────┬─────────────┐"
  echo   "  │ fonte               │ mode   │ status   │ itens  │ latência    │"
  echo   "  ├─────────────────────┼────────┼──────────┼────────┼─────────────┤"
  # Usa arquivo temp para o script Python — evita conflito pipe+heredoc
  # (heredoc sobrescreve stdin do python3 -, pipe fica sem destino)
  _TBL=$(mktemp /tmp/cij_tbl_XXXXXX.py)
  cat > "$_TBL" << 'PYEOF'
import sys,json
resp = json.load(sys.stdin)
results = resp.get('data',{}).get('intelligence',{}).get('results',[])
real_n = sum(1 for r in results if r.get('dataMode')=='real')
mock_n = sum(1 for r in results if r.get('dataMode')=='mock')
for r in results:
    mode  = r.get('dataMode','?')
    status= r.get('status','?')
    lat   = r.get('latencyMs') or 0
    total = r.get('totalAvailable') or 0
    err   = (r.get('error') or '')[:28]
    mark  = '*' if mode=='real' else 'o'
    print(f"  | {mark} {r['source']:<18}| {mode:<7}| {status:<9}| {total:>5}  | {lat:>6} ms   |{' ERR:'+err if err else ''}")
print("  └─────────────────────┴────────┴──────────┴────────┴─────────────┘")
print(f"\n  [*] REAL: {real_n}  [o] MOCK: {mock_n}")
dims = resp.get('data',{}).get('intelligence',{}).get('riskDimensions',[])
if dims:
    print("\n  Dimensões de risco:")
    for d in dims:
        bar = '█' * max(1,int(d['score']//10))
        print(f"    {d['name']:<22} {d['score']:>3}  {bar}")
PYEOF
  echo "$RESP_360" | python3 "$_TBL" 2>/dev/null || warn "Falha ao renderizar tabela de fontes"
  rm -f "$_TBL"

  REAL_DATA=$(echo "$RESP_360" | python3 -c "
import sys,json
r=json.load(sys.stdin).get('data',{}).get('intelligence',{}).get('results',[])
print(sum(1 for x in r if x.get('dataMode')=='real' and (x.get('totalAvailable') or 0)>0))
" 2>/dev/null || echo "0")
  [ "${REAL_DATA:-0}" -gt 0 ] \
    && pass "${REAL_DATA} fonte(s) real(is) com dados efetivos" \
    || warn "0 fontes reais com dados — todas as fontes estão em MOCK (ver seção 0)"
else
  fail "POST /intelligence/graphql → resposta inválida"
  [ "$VERBOSE" = "1" ] && info "raw: ${RESP_360:0:400}"
fi

# ─── QSA expansion ────────────────────────────────────────────────────────────
echo ""
info "QSA expansion (expandQsa=true)..."
QSA_BODY=$(python3 -c "import json; print(json.dumps({'query':'query I360(\$i:String!,\$e:Boolean!){intelligence(identifier:\$i,expandQsa:\$e){queryId relatedParties{nome vinculo}}}','variables':{'i':'${TEST_CNPJ}','e':True}}))")
RESP_QSA=$(http_post "$OHDR" "/api/v1/intelligence/graphql" "$QSA_BODY")
QSA_ID=$(echo "$RESP_QSA" | jval "d.get('data',{}).get('intelligence',{}).get('queryId','')")
QSA_N=$(echo "$RESP_QSA"  | jval "len(d.get('data',{}).get('intelligence',{}).get('relatedParties',[]))")
[ -n "$QSA_ID" ] \
  && pass "QSA expansion → ${QSA_N:-0} partes relacionadas" \
  || fail "QSA expansion → resposta inválida (sem queryId)"

# ─── Detecção por Nome ────────────────────────────────────────────────────────
echo ""
info "Detecção por Nome..."
NOME_BODY='{"query":"query I360($i:String!,$e:Boolean!){intelligence(identifier:$i,expandQsa:$e){identifierType}}","variables":{"i":"Jose da Silva Santos","e":false}}'
RESP_NOME=$(http_post "$OHDR" "/api/v1/intelligence/graphql" "$NOME_BODY")
ID_TYPE_NOME=$(echo "$RESP_NOME" | jval "d.get('data',{}).get('intelligence',{}).get('identifierType','?')")
[ "$ID_TYPE_NOME" = "NOME" ] \
  && pass "Detecção NOME → ${ID_TYPE_NOME} ✓" \
  || warn "Tipo detectado: '${ID_TYPE_NOME}' (esperado: NOME)"

# ═══════════════════════════════════════════════════════════════════════════════
section "15. Submissão de tarefa (assistente)"
# ═══════════════════════════════════════════════════════════════════════════════
TASK_RES=$(http_post "$OHDR" "/api/v1/tasks" \
  '{"task_description":"O que e dano moral segundo a jurisprudencia do STJ?"}')
TASK_ID=$(echo "$TASK_RES" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(d.get('task_id') or d.get('id') or d.get('status',''))
" 2>/dev/null || echo "")
[ -n "$TASK_ID" ] \
  && pass "POST /tasks → tarefa criada (id/status=${TASK_ID})" \
  || warn "POST /tasks → resposta: ${TASK_RES:0:120}"

# ═══════════════════════════════════════════════════════════════════════════════
section "16. SPA Frontend"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "" "/app/")
[ "$S" = "200" ] && pass "GET /app/ → 200 (SPA servida)" || fail "GET /app/ → $S"

SPA_HTML=$(http_body "" "/app/")
echo "$SPA_HTML" | grep -q "\.js" && pass "SPA HTML referencia bundle JS" \
  || warn "SPA HTML sem referência a bundle JS"

# ═══════════════════════════════════════════════════════════════════════════════
section "17. WebSocket HITL"
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$SMOKE_MODE" = "docker" ]; then
  # Usa curl dentro do container para verificar o upgrade
  WS_STATUS=$(docker exec "$CONTAINER" curl -s -o /dev/null -w "%{http_code}" \
    -H "Upgrade: websocket" \
    -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    "http://localhost:8000/api/v1/hitl/ws" 2>/dev/null || echo "000")
  [ "$WS_STATUS" = "101" ] && pass "WebSocket /hitl/ws → 101 Switching Protocols ✓" \
    || warn "WebSocket → $WS_STATUS (101 esperado)"
else
  warn "WebSocket: instale websocat para teste completo em modo http"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "18. Métricas Prometheus"
# ═══════════════════════════════════════════════════════════════════════════════
S=$(http_code "" "/metrics")
if [ "$S" = "200" ]; then
  http_body "" "/metrics" | grep -qE "http_requests_total|process_cpu|python_" \
    && pass "GET /metrics → Prometheus OK" \
    || warn "GET /metrics → 200 mas sem métricas reconhecíveis"
else
  warn "GET /metrics → $S"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════════════════════
TOTAL=$((PASS+FAIL+WARN))
echo ""
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD} RESUMO${NC}"
echo -e "${BOLD}${BLU}═══════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}✔ OK    : $PASS${NC}  ${YEL}⚠ Aviso: $WARN${NC}  ${RED}✗ Falha: $FAIL${NC}  (total: $TOTAL)"

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${RED}Falhas:${NC}"
  for f in "${FAILURES[@]}"; do echo -e "    • $f"; done
fi

echo ""
echo    "  Para ativar dados reais (fontes públicas gratuitas), adicione ao .env:"
echo -e "    ${CYN}INTEGRATIONS_DATAJUD_MODE=real${NC}   # CNJ DataJud (processo por número)"
echo -e "    ${CYN}INTEGRATIONS_DJEN_MODE=real${NC}      # Comunica PJe"
echo -e "    ${CYN}INTEGRATIONS_RECEITA_CNPJ_MODE=real${NC} # BrasilAPI (CNPJ → gratuito)"
echo -e "    ${CYN}INTEGRATIONS_TSE_MODE=real${NC}       # TSE dados eleitorais (gratuito)"
echo    "  Depois: docker compose restart agent-system"
echo ""

[ "$FAIL" -eq 0 ] \
  && echo -e "  ${GRN}${BOLD}✔  Smoke test PASSOU${NC}" \
  || echo -e "  ${RED}${BOLD}✗  Smoke test FALHOU${NC}"

exit "$FAIL"
