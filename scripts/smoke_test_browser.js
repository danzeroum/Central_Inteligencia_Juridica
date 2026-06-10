/**
 * smoke_test_browser.js — Central de Inteligência Jurídica
 *
 * Cole no Console do DevTools (F12 → Console) enquanto estiver na
 * tela do app (http://seudominio/app/) já autenticado.
 *
 * O script usa o JWT gravado no localStorage pela aplicação e
 * executa todos os endpoints pela mesma origem (sem CORS).
 *
 * Ao final injeta um painel visual inline com o relatório completo.
 */
(async () => {
  /* ──────────────────────────────────────────────────────────────────────── */
  /* Configuração                                                              */
  /* ──────────────────────────────────────────────────────────────────────── */
  const BASE   = '';          // mesma origem — não altere (proxy do Vite)
  const CNPJ   = '33000167000101'; // Petrobras — CNPJ público para teste
  const NOME   = 'Jose da Silva Santos';

  // Chave exata definida em frontend/src/api/auth.js
  const TOKEN  = localStorage.getItem('cij.token')
               || localStorage.getItem('cij_token')
               || localStorage.getItem('token')
               || sessionStorage.getItem('token')
               || '';

  if (!TOKEN) {
    console.warn('[smoke] JWT não encontrado no localStorage — faça login primeiro.');
  }

  const H  = { 'Content-Type': 'application/json', ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) };
  const HA = H; // admin (se logado como admin)

  /* ──────────────────────────────────────────────────────────────────────── */
  /* Helpers                                                                   */
  /* ──────────────────────────────────────────────────────────────────────── */
  const results = [];

  const check = (label, ok, detail = '') => {
    const entry = { label, ok: ok === true, warn: ok === 'warn', detail };
    results.push(entry);
    const icon = ok === true ? '✅' : ok === 'warn' ? '⚠️' : '❌';
    console[ok === true ? 'log' : ok === 'warn' ? 'warn' : 'error'](`${icon} ${label}`, detail || '');
    return entry;
  };

  const GET  = (url) => fetch(BASE + url, { headers: H }).catch(e => ({ ok: false, status: 0, json: async () => ({ error: e.message }) }));
  const POST = (url, body) => fetch(BASE + url, { method: 'POST', headers: H, body: JSON.stringify(body) }).catch(e => ({ ok: false, status: 0, json: async () => ({ error: e.message }) }));

  const j = async (res) => { try { return await res.json(); } catch { return {}; } };

  console.group('%c🔎 CIJ Smoke Test', 'font-weight:bold; font-size:14px; color:#1e3a5f');

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 1. Health                                                                  */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('1. Health');
  const h = await GET('/health');
  const hb = await j(h);
  check('GET /health → 200', h.ok, `status=${hb.status || hb.message || h.status}`);
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 2. JWT do localStorage                                                     */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('2. Auth / Token');
  check('JWT presente no storage', !!TOKEN, TOKEN ? `${TOKEN.slice(0,20)}…` : 'não encontrado');

  if (TOKEN) {
    try {
      const payload = JSON.parse(atob(TOKEN.split('.')[1]));
      const exp = payload.exp ? new Date(payload.exp * 1000) : null;
      const expired = exp ? exp < new Date() : false;
      check('JWT não expirado', !expired, exp ? `expira ${exp.toLocaleString()}` : 'sem exp');
      check('JWT contém roles', Array.isArray(payload.roles) && payload.roles.length > 0, `roles=${JSON.stringify(payload.roles)}`);
      check('JWT contém sub (userId)', !!payload.sub, `sub=${payload.sub}`);
    } catch (e) {
      check('JWT decodificável', false, e.message);
    }
  }
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 3. Endpoints básicos                                                       */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('3. Endpoints');

  const endpoints = [
    ['/api/v1/hitl/pending',                  'HITL pending'],
    ['/api/v1/hitl/stats',                    'HITL stats'],
    ['/api/v1/ledger',                        'Ledger'],
    ['/api/v1/training/stats',                'Training stats'],
    ['/api/v1/training/active-sessions',      'Training active-sessions'],
    ['/api/v1/agents',                        'Agentes MCP'],
    ['/api/v1/autonomy/config',               'Autonomy config'],
    ['/api/v1/monitoring/health',             'Monitoring health'],
    ['/api/v1/profile',                       'Perfil'],
    ['/api/v1/history?limit=5',               'Histórico'],
    ['/api/v1/jurisprudencia?tribunal=tjsp&q=dano+moral&size=3', 'Jurisprudência'],
    ['/api/v1/proposicoes-legislativas?q=LGPD&pagina=1&itens=3', 'Legislativo'],
  ];

  for (const [url, label] of endpoints) {
    const r = await GET(url);
    check(`GET ${url.split('?')[0]}`, r.ok, `HTTP ${r.status}`);
  }
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 4. SPA assets                                                              */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('4. SPA assets');
  const spa = await fetch('/app/');
  const spaHtml = await spa.text();
  check('GET /app/ → 200', spa.ok, `HTTP ${spa.status}`);
  check('SPA HTML contém bundle JS', spaHtml.includes('.js'), '');
  check('SPA HTML contém bundle CSS', spaHtml.includes('.css'), '');
  // favicon 404 é esperado em dev — apenas aviso
  const faviconOk = (await fetch('/favicon.ico')).ok;
  check('GET /favicon.ico', faviconOk || 'warn', faviconOk ? 'ok' : '404 (normal em dev)');
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 5. Investigação 360° — CNPJ                                               */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('5. Investigação 360° — CNPJ Petrobras');

  const GQL = `query I360($identifier: String!, $expandQsa: Boolean!) {
    intelligence(identifier: $identifier, expandQsa: $expandQsa) {
      queryId identifierMasked identifierType riskScore hitlStatus summary
      riskDimensions { name score }
      riskFactors { code description weight dimension }
      results { source status dataMode latencyMs totalAvailable error }
    }
  }`;

  let report360 = null;
  const t0 = performance.now();
  const r360 = await POST('/api/v1/intelligence/graphql', { query: GQL, variables: { identifier: CNPJ, expandQsa: false } });
  const elapsed = Math.round(performance.now() - t0);
  const b360 = await j(r360);
  const intel = b360?.data?.intelligence;

  check('POST /intelligence/graphql → 200', r360.ok, `HTTP ${r360.status} em ${elapsed}ms`);
  check('GraphQL sem erros', !b360.errors, b360.errors ? JSON.stringify(b360.errors) : '');

  if (intel) {
    report360 = intel;
    check('queryId presente', !!intel.queryId, intel.queryId);
    check('identifierMasked presente', !!intel.identifierMasked, intel.identifierMasked);
    check('riskScore numérico', typeof intel.riskScore === 'number', `score=${intel.riskScore}`);

    // LGPD: CNPJ bruto não pode aparecer na resposta serializada
    const raw = JSON.stringify(b360);
    check('LGPD: CNPJ mascarado (sem dígitos brutos)', !raw.includes(CNPJ), `CNPJ ${CNPJ} NÃO deve aparecer`);

    // Análise por fonte
    const results360 = intel.results || [];
    const realSources = results360.filter(r => r.dataMode === 'real');
    const mockSources = results360.filter(r => r.dataMode === 'mock');
    const realWithData = realSources.filter(r => r.totalAvailable > 0);

    check(`Fontes reais com dados (${realWithData.length}/${realSources.length})`,
      realWithData.length > 0 || 'warn',
      realWithData.map(r => r.source).join(', ') || 'nenhuma');

    console.log('%c  Análise por fonte:', 'font-weight:bold');
    console.table(results360.map(r => ({
      fonte: r.source,
      mode: r.dataMode,
      status: r.status,
      items: r.totalAvailable,
      latência_ms: r.latencyMs,
      erro: r.error || '',
    })));

    if (intel.riskDimensions?.length) {
      console.log('%c  Risk Dimensions:', 'font-weight:bold');
      console.table(intel.riskDimensions);
    }

    if (intel.riskFactors?.length) {
      console.log('%c  Risk Factors:', 'font-weight:bold');
      console.table(intel.riskFactors);
    }
  }
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 6. 360° — Detecção de tipo por nome                                       */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('6. Investigação 360° — Detecção por Nome');
  const rNome = await POST('/api/v1/intelligence/graphql', {
    query: `query I360($identifier: String!, $expandQsa: Boolean!) { intelligence(identifier: $identifier, expandQsa: $expandQsa) { identifierType riskScore results { source dataMode } } }`,
    variables: { identifier: NOME, expandQsa: false }
  });
  const bNome = await j(rNome);
  const tipoNome = bNome?.data?.intelligence?.identifierType;
  check('Tipo detectado = NOME', tipoNome === 'NOME', `detectedType=${tipoNome}`);
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 7. WebSocket HITL (handshake)                                             */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('7. WebSocket HITL');
  await new Promise(resolve => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/api/v1/hitl/ws?token=${TOKEN}`);
    const timer = setTimeout(() => {
      check('WebSocket HITL handshake', 'warn', 'timeout 3s — servidor não enviou mensagem inicial');
      ws.close();
      resolve();
    }, 3000);
    ws.onopen = () => {
      check('WebSocket HITL → conectado', true, 'readyState=OPEN');
    };
    ws.onmessage = (e) => {
      clearTimeout(timer);
      check('WebSocket HITL → recebeu mensagem', true, e.data.slice(0, 80));
      ws.close();
      resolve();
    };
    ws.onerror = (e) => {
      clearTimeout(timer);
      check('WebSocket HITL conexão', false, 'erro ao conectar');
      resolve();
    };
  });
  console.groupEnd();

  /* ──────────────────────────────────────────────────────────────────────── */
  /* 8. LocalStorage integridade                                                */
  /* ──────────────────────────────────────────────────────────────────────── */
  console.group('8. LocalStorage / estado da sessão');
  const keys = Object.keys(localStorage);
  check('Sem dados sensíveis em plain text',
    !keys.some(k => {
      const v = localStorage.getItem(k) || '';
      return /\d{3}\.\d{3}\.\d{3}-\d{2}/.test(v) || /\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}/.test(v);
    }),
    'CPF/CNPJ formato claro não deve estar no storage'
  );
  check('Chaves gravadas no storage', true, keys.join(', ') || '(vazio)');
  console.groupEnd();

  console.groupEnd(); // main group

  /* ──────────────────────────────────────────────────────────────────────── */
  /* Painel visual inline                                                       */
  /* ──────────────────────────────────────────────────────────────────────── */
  const passN = results.filter(r => r.ok).length;
  const warnN = results.filter(r => r.warn).length;
  const failN = results.filter(r => !r.ok && !r.warn).length;
  const totalN = results.length;

  const panelHtml = `
<div id="cij-smoke-panel" style="
  position:fixed; top:20px; right:20px; z-index:99999;
  background:#fff; border:2px solid #1e3a5f; border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,0.18); padding:20px; width:420px;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:13px;
  max-height:80vh; overflow-y:auto;
">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <b style="font-size:15px; color:#1e3a5f">🔎 CIJ Smoke Test</b>
    <button onclick="document.getElementById('cij-smoke-panel').remove()"
      style="border:none;background:none;cursor:pointer;font-size:18px;color:#666">✕</button>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <span style="flex:1;text-align:center;background:#d4edda;border-radius:8px;padding:8px 4px;color:#155724">
      <b style="font-size:18px">${passN}</b><br><small>OK</small>
    </span>
    <span style="flex:1;text-align:center;background:#fff3cd;border-radius:8px;padding:8px 4px;color:#856404">
      <b style="font-size:18px">${warnN}</b><br><small>Aviso</small>
    </span>
    <span style="flex:1;text-align:center;background:${failN > 0 ? '#f8d7da' : '#e2e3e5'};border-radius:8px;padding:8px 4px;color:${failN > 0 ? '#721c24' : '#383d41'}">
      <b style="font-size:18px">${failN}</b><br><small>Falha</small>
    </span>
    <span style="flex:1;text-align:center;background:#e2e3e5;border-radius:8px;padding:8px 4px;color:#383d41">
      <b style="font-size:18px">${totalN}</b><br><small>Total</small>
    </span>
  </div>
  <div style="max-height:380px;overflow-y:auto;border:1px solid #dee2e6;border-radius:6px">
  ${results.map(r => {
    const bg = r.ok ? '#f0fff4' : r.warn ? '#fffde7' : '#fff5f5';
    const icon = r.ok ? '✅' : r.warn ? '⚠️' : '❌';
    return `<div style="padding:6px 10px;border-bottom:1px solid #f0f0f0;background:${bg}">
      ${icon} <span style="font-size:12px">${r.label}</span>
      ${r.detail ? `<br><span style="color:#666;font-size:11px;padding-left:22px">${r.detail}</span>` : ''}
    </div>`;
  }).join('')}
  </div>
  ${report360 ? `
  <div style="margin-top:12px;padding:10px;background:#f8f9ff;border-radius:8px;font-size:12px">
    <b>Investigação 360° — ${report360.identifierMasked}</b><br>
    Risk Score: <b style="color:${report360.riskScore >= 70 ? '#c62828' : report360.riskScore >= 40 ? '#e65100' : '#2e7d32'}">${report360.riskScore}</b>
    &nbsp;|&nbsp; HITL: ${report360.hitlStatus || 'N/A'}<br>
    <div style="margin-top:6px">
    ${(report360.results || []).map(r => `
      <span style="display:inline-block;margin:2px 3px;padding:2px 7px;border-radius:4px;
        background:${r.dataMode === 'real' ? '#e8f5e9' : '#fff8e1'};
        border:1px solid ${r.dataMode === 'real' ? '#a5d6a7' : '#ffe082'};
        color:${r.dataMode === 'real' ? '#1b5e20' : '#7c4d00'}">
        ${r.dataMode === 'real' ? '🟢' : '🟡'} ${r.source} (${r.totalAvailable || 0})
      </span>`).join('')}
    </div>
  </div>` : ''}
  <div style="margin-top:10px;font-size:11px;color:#888;text-align:center">
    ${new Date().toLocaleString('pt-BR')} · ${location.host}
  </div>
</div>`;

  // Remove painel anterior se existir
  document.getElementById('cij-smoke-panel')?.remove();
  const div = document.createElement('div');
  div.innerHTML = panelHtml;
  document.body.appendChild(div.firstElementChild);

  /* ──────────────────────────────────────────────────────────────────────── */
  /* Retorno para o console                                                     */
  /* ──────────────────────────────────────────────────────────────────────── */
  const summary = {
    pass: passN, warn: warnN, fail: failN, total: totalN,
    status: failN === 0 ? 'PASSOU' : 'FALHOU',
    intel360: report360 ? {
      queryId: report360.queryId,
      identifierMasked: report360.identifierMasked,
      riskScore: report360.riskScore,
      hitlStatus: report360.hitlStatus,
      sources: (report360.results || []).map(r => ({ source: r.source, mode: r.dataMode, items: r.totalAvailable })),
    } : null,
  };

  console.log(`%c${failN === 0 ? '✅' : '❌'} Smoke test ${summary.status}: ${passN}✔ ${warnN}⚠ ${failN}✗`, 'font-size:14px; font-weight:bold');
  return summary;
})();
