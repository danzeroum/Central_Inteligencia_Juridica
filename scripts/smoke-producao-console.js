// ══════════════════════════════════════════════════════════════════════════════
//  Central de Inteligência Jurídica — Suite de Testes de Produção
//
//  USO: Abra o browser no domínio da aplicação, F12 → Console → cole e Enter.
//       Altere USER e PASS antes de executar.
//       BASE vazio = URL relativa (funciona com CSP connect-src 'self').
//       Se rodar de outra aba, preencha BASE com o domínio completo.
// ══════════════════════════════════════════════════════════════════════════════
(async () => {

  const BASE = '';          // deixe vazio se estiver na aba da própria aplicação
  const USER = 'admin';
  const PASS = 'SuaSenhaAqui';

  // ── Utilitários ─────────────────────────────────────────────────────────────
  let token = null, p = 0, f = 0;
  const H = () => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  });
  const req = async (method, path, body) => {
    try {
      return await fetch(BASE + path, {
        method,
        headers: H(),
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) { return null; }
  };
  const ok  = (label, info = '') => { p++; console.log(`✅ ${label}`, info ? `(${info})` : ''); };
  const ko  = (label, info = '') => { f++; console.error(`❌ ${label}`, info ? `(${info})` : ''); };
  const chk = (label, r, codes) => {
    if (!r) return ko(label, 'sem resposta / CORS');
    codes.includes(r.status) ? ok(label, r.status) : ko(label, `HTTP ${r.status}`);
  };

  console.log('🏛️  Central de Inteligência Jurídica — Teste de Produção\n' + '═'.repeat(60));

  // ── 1. HEALTH ────────────────────────────────────────────────────────────────
  console.log('\n── 1. Health');
  chk('GET /health',                   await req('GET', '/health'),                    [200]);
  chk('GET /health?verbose=true',      await req('GET', '/health?verbose=true'),       [200]);
  chk('GET /api/v1/monitoring/health', await req('GET', '/api/v1/monitoring/health'), [200]);
  chk('GET /metrics (Prometheus)',     await req('GET', '/metrics'),                   [200]);

  // ── 2. AUTENTICAÇÃO ──────────────────────────────────────────────────────────
  console.log('\n── 2. Autenticação');
  const rAuth = await req('POST', '/auth/login', { username: USER, password: PASS });
  if (rAuth && rAuth.status === 200) {
    const j = await rAuth.json();
    token = j.access_token;
    ok('POST /auth/login → token JWT obtido', `roles: ${j.roles}`);
  } else {
    ko('POST /auth/login', `HTTP ${rAuth?.status} — verifique USER/PASS`);
    console.warn('⚠️  Sem token — endpoints autenticados retornarão 401/403.');
  }

  // ── 3. TAREFAS ───────────────────────────────────────────────────────────────
  console.log('\n── 3. Tarefas (Tasks)');
  chk('POST /api/v1/tasks (canônico)',
    await req('POST', '/api/v1/tasks',         { task_description: 'Consulta jurisprudência trabalhista TJSP' }), [200]);
  chk('POST /tasks (legado/deprecated)',
    await req('POST', '/tasks',                { task_description: 'Consulta processo TJSP' }),                   [200]);
  chk('POST /api/v1/tasks/advanced',
    await req('POST', '/api/v1/tasks/advanced', { task_description: 'Análise tributária complexa' }),             [200]);

  // ── 4. PROPOSIÇÕES LEGISLATIVAS ──────────────────────────────────────────────
  console.log('\n── 4. Proposições Legislativas');
  chk('GET /api/v1/proposicoes-legislativas?q=reforma',
    await req('GET', '/api/v1/proposicoes-legislativas?q=reforma+tributaria'), [200]);
  chk('GET /consultar-projetos-lei/?q=reforma (legado)',
    await req('GET', '/consultar-projetos-lei/?q=reforma'),                    [200]);
  chk('GET /consultar-projetos-lei/?q=   → 400 (query vazia)',
    await req('GET', '/consultar-projetos-lei/?q=   '),                        [400]);

  // ── 5. ANÁLISE LEGISLATIVA ───────────────────────────────────────────────────
  console.log('\n── 5. Análise Legislativa');
  chk('POST /api/v1/analises-legislativas → 201',
    await req('POST', '/api/v1/analises-legislativas', { tema: 'reforma tributária' }), [201]);
  chk('POST /analise-legislativa/ (legado)',
    await req('POST', '/analise-legislativa/',          { tema: 'reforma trabalhista' }), [200]);
  chk('POST /analise-legislativa/ tema vazio → 400',
    await req('POST', '/analise-legislativa/',          { tema: '   ' }),               [400]);

  // ── 6. JURISPRUDÊNCIA (DataJud) ──────────────────────────────────────────────
  console.log('\n── 6. Jurisprudência / DataJud');
  chk('GET /api/v1/jurisprudencia?tribunal=TJSP',
    await req('GET', '/api/v1/jurisprudencia?tribunal=TJSP'), [200]);

  // ── 7. PERFIL ────────────────────────────────────────────────────────────────
  console.log('\n── 7. Perfil');
  chk('GET /api/v1/profile',
    await req('GET', '/api/v1/profile'),   [200, 401, 403]);
  chk('GET /api/v1/profile/area',
    await req('GET', '/api/v1/profile/area'),   [200, 401, 403]);
  chk('GET /api/v1/profile/clientes',
    await req('GET', '/api/v1/profile/clientes'), [200, 401, 403]);
  chk('POST /api/v1/profile/clientes → 201',
    await req('POST', '/api/v1/profile/clientes', { nome: 'Cliente Teste', cpf_cnpj: '00000000000' }), [201, 400, 401, 403]);
  chk('DELETE /api/v1/profile → 204/404',
    await req('DELETE', '/api/v1/profile'), [204, 401, 403, 404]);

  // ── 8. AGENTES (MCP) ────────────────────────────────────────────────────────
  console.log('\n── 8. Agentes (MCP)');
  chk('GET /api/v1/agents',
    await req('GET', '/api/v1/agents'),           [200]);
  chk('GET /api/v1/agents/capabilities',
    await req('GET', '/api/v1/agents/capabilities'), [200]);
  chk('POST /api/v1/agents/supervisor_agent/invoke',
    await req('POST', '/api/v1/agents/supervisor_agent/invoke', { task_description: 'Teste' }), [200]);
  chk('POST /api/v1/agents/inexistente/invoke → 404',
    await req('POST', '/api/v1/agents/inexistente/invoke',      { task_description: 'Teste' }), [404]);

  // ── 9. A2A (AGENT-TO-AGENT) ──────────────────────────────────────────────────
  console.log('\n── 9. A2A Broadcast');
  chk('POST /api/v1/a2a/broadcast',
    await req('POST', '/api/v1/a2a/broadcast', {
      sender_id: 'agent_a', receiver_ids: ['agent_b', 'agent_c'],
      message_type: 'ping', payload: {},
    }), [200]);
  chk('GET /api/v1/a2a/health',
    await req('GET', '/api/v1/a2a/health'), [200]);

  // ── 10. HITL ────────────────────────────────────────────────────────────────
  console.log('\n── 10. HITL (Human-in-the-Loop)');
  chk('GET /api/v1/hitl/stats',
    await req('GET', '/api/v1/hitl/stats'),   [200]);
  chk('GET /api/v1/hitl/pending',
    await req('GET', '/api/v1/hitl/pending'), [200]);

  // ── 11. LEDGER (TRILHA DE AUDITORIA) ────────────────────────────────────────
  console.log('\n── 11. Ledger (Auditoria)');
  chk('GET /api/v1/ledger',
    await req('GET', '/api/v1/ledger'),            [200, 401, 403]);
  chk('GET /api/v1/ledger/export.csv',
    await req('GET', '/api/v1/ledger/export.csv'), [200, 401, 403]);

  // ── 12. TREINAMENTO ─────────────────────────────────────────────────────────
  console.log('\n── 12. Treinamento');
  chk('GET /api/v1/training/stats',
    await req('GET', '/api/v1/training/stats'),   [200, 401, 403]);
  chk('GET /api/v1/training/history',
    await req('GET', '/api/v1/training/history'), [200, 401, 403]);

  // ── 13. AUTONOMIA ───────────────────────────────────────────────────────────
  console.log('\n── 13. Autonomia');
  chk('GET /api/v1/autonomy/config',
    await req('GET', '/api/v1/autonomy/config'), [200, 401, 403]);

  // ── 14. LGPD ────────────────────────────────────────────────────────────────
  console.log('\n── 14. LGPD');
  chk('GET /api/v1/lgpd/data/test-subject → 200/404',
    await req('GET', '/api/v1/lgpd/data/test-subject'), [200, 404, 401, 403]);

  // ── 15. HISTÓRICO ───────────────────────────────────────────────────────────
  console.log('\n── 15. Histórico');
  chk('GET /api/v1/history',
    await req('GET', '/api/v1/history'), [200, 401, 403]);

  // ── RESULTADO FINAL ─────────────────────────────────────────────────────────
  console.log('\n' + '═'.repeat(60));
  console.log(`📊 RESULTADO: ${p} ✅ passou  |  ${f} ❌ falhou  |  ${p + f} total`);
  if (f === 0) console.log('🎉 Todos os endpoints responderam conforme esperado!');
  else         console.warn(`⚠️  ${f} endpoint(s) fora do esperado — verifique os ❌ acima.`);
  console.log('═'.repeat(60));

})();
