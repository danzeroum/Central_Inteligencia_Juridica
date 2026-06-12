import React, { useState, useEffect } from 'react';
import { useToast } from '../../components/toast.jsx';

const BASE = '/api/v1/fiscal';

async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem('token');
  const res = await fetch(path, {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res;
}

// ── Reports tab ──────────────────────────────────────────────────────────────

function ReportsTab() {
  const { showToast } = useToast();
  const [tipos, setTipos] = useState([]);
  const [selectedTipo, setSelectedTipo] = useState('');
  const [tributo, setTributo] = useState('');
  const [periodoInicio, setPeriodoInicio] = useState('');
  const [periodoFim, setPeriodoFim] = useState('');
  const [limit, setLimit] = useState(200);
  const [resultado, setResultado] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch(`${BASE}/reports/tipos`)
      .then((r) => r.json())
      .then(setTipos)
      .catch(() => {});
  }, []);

  const gerar = async (formato = 'json') => {
    if (!selectedTipo) return;
    setBusy(true);
    setError('');
    setResultado(null);
    const params = new URLSearchParams({ tipo: selectedTipo, limit, formato });
    if (tributo) params.set('tributo', tributo);
    if (periodoInicio) params.set('periodo_inicio', periodoInicio);
    if (periodoFim) params.set('periodo_fim', periodoFim);
    try {
      const res = await apiFetch(`${BASE}/reports/gerar?${params}`);
      if (formato === 'csv') {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `relatorio_${selectedTipo}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV baixado com sucesso.', 'success');
      } else {
        const data = await res.json();
        setResultado(data);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const tipoInfo = tipos.find((t) => t.tipo === selectedTipo);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 16px' }}>Gerar Relatório Premium</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field" style={{ gridColumn: '1/-1' }}>
            <label>Tipo de relatório</label>
            <select className="input" value={selectedTipo} onChange={(e) => setSelectedTipo(e.target.value)}>
              <option value="">Selecione…</option>
              {tipos.map((t) => (
                <option key={t.tipo} value={t.tipo}>{t.nome}</option>
              ))}
            </select>
            {tipoInfo && <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 4 }}>{tipoInfo.descricao}</div>}
          </div>
          <div className="field">
            <label>Tributo (opcional)</label>
            <select className="input" value={tributo} onChange={(e) => setTributo(e.target.value)}>
              <option value="">Todos</option>
              {['ICMS', 'PIS', 'COFINS', 'ICMS-ST', 'IPI'].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Limite de linhas</label>
            <input className="input" type="number" min={1} max={2000} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Período início (AAAA-MM)</label>
            <input className="input" type="month" value={periodoInicio}
              onChange={(e) => setPeriodoInicio(e.target.value)} />
          </div>
          <div className="field">
            <label>Período fim (AAAA-MM)</label>
            <input className="input" type="month" value={periodoFim}
              onChange={(e) => setPeriodoFim(e.target.value)} />
          </div>
        </div>
        {error && <div style={{ color: 'var(--crit)', fontSize: 13, marginTop: 8 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary" disabled={busy || !selectedTipo} onClick={() => gerar('json')}>
            {busy ? 'Gerando…' : 'Visualizar JSON'}
          </button>
          <button className="btn" disabled={busy || !selectedTipo} onClick={() => gerar('csv')}>
            Baixar CSV
          </button>
        </div>
      </div>

      {resultado && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>{tipoInfo?.nome} — {resultado.total_linhas} linha(s)</h3>
            <span style={{ fontSize: 12, color: 'var(--faint)' }}>ID: {resultado.report_id}</span>
          </div>
          {resultado.dados.length === 0 ? (
            <div style={{ color: 'var(--faint)', fontSize: 13 }}>Nenhum dado encontrado para os filtros informados.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {Object.keys(resultado.dados[0]).map((col) => (
                      <th key={col} style={{ textAlign: 'left', padding: '6px 10px', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultado.dados.slice(0, 100).map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      {Object.values(row).map((val, j) => (
                        <td key={j} style={{ padding: '5px 10px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {String(val ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {resultado.dados.length > 100 && (
                <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 8 }}>
                  Exibindo primeiras 100 de {resultado.dados.length} linhas. Baixe o CSV para o conjunto completo.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Workbench tab ─────────────────────────────────────────────────────────────

function WorkbenchTab() {
  const [queries, setQueries] = useState([]);
  const [selectedQuery, setSelectedQuery] = useState('');
  const [tributo, setTributo] = useState('');
  const [operation, setOperation] = useState('');
  const [limit, setLimit] = useState(50);
  const [resultado, setResultado] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sqlValidar, setSqlValidar] = useState('');
  const [validacaoResult, setValidacaoResult] = useState(null);
  const [validarBusy, setValidarBusy] = useState(false);

  useEffect(() => {
    apiFetch(`${BASE}/workbench/queries`)
      .then((r) => r.json())
      .then(setQueries)
      .catch(() => {});
  }, []);

  const executar = async () => {
    if (!selectedQuery) return;
    setBusy(true);
    setError('');
    setResultado(null);
    const params = new URLSearchParams({ query_id: selectedQuery, limit });
    if (tributo) params.set('tributo', tributo);
    if (operation) params.set('operation', operation);
    try {
      const res = await apiFetch(`${BASE}/workbench/executar?${params}`, { method: 'POST' });
      setResultado(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const validar = async () => {
    if (!sqlValidar.trim()) return;
    setValidarBusy(true);
    setValidacaoResult(null);
    try {
      const res = await apiFetch(`${BASE}/workbench/validar`, {
        method: 'POST',
        body: JSON.stringify({ sql: sqlValidar }),
      });
      setValidacaoResult(await res.json());
    } catch (e) {
      setValidacaoResult({ seguro: false, mensagem: e.message });
    } finally {
      setValidarBusy(false);
    }
  };

  const queryInfo = queries.find((q) => q.query_id === selectedQuery);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 4px' }}>Executar Query Pré-definida</h3>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 16 }}>
          Somente templates validados da plataforma — sem SQL livre de entrada.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="field" style={{ gridColumn: '1/-1' }}>
            <label>Query</label>
            <select className="input" value={selectedQuery} onChange={(e) => setSelectedQuery(e.target.value)}>
              <option value="">Selecione…</option>
              {queries.map((q) => (
                <option key={q.query_id} value={q.query_id}>{q.nome}</option>
              ))}
            </select>
            {queryInfo && <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 4 }}>{queryInfo.descricao}</div>}
          </div>
          <div className="field">
            <label>Tributo (opcional)</label>
            <select className="input" value={tributo} onChange={(e) => setTributo(e.target.value)}>
              <option value="">Todos</option>
              {['ICMS', 'PIS', 'COFINS', 'ICMS-ST', 'IPI'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Operation (opcional)</label>
            <input className="input" placeholder="ex: gerar_retificado" value={operation}
              onChange={(e) => setOperation(e.target.value)} />
          </div>
          <div className="field">
            <label>Limite</label>
            <input className="input" type="number" min={1} max={200} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
        </div>
        {error && <div style={{ color: 'var(--crit)', fontSize: 13, marginTop: 8 }}>{error}</div>}
        <button className="btn btn-primary" style={{ marginTop: 16 }} disabled={busy || !selectedQuery} onClick={executar}>
          {busy ? 'Executando…' : 'Executar'}
        </button>
      </div>

      {resultado && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>{resultado.total_linhas} linha(s) — {resultado.duration_ms}ms</h3>
            <span style={{ fontSize: 12, color: 'var(--faint)' }}>exec: {resultado.execution_id}</span>
          </div>
          {resultado.dados.length === 0 ? (
            <div style={{ color: 'var(--faint)', fontSize: 13 }}>Nenhum resultado.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {Object.keys(resultado.dados[0]).map((col) => (
                      <th key={col} style={{ textAlign: 'left', padding: '6px 10px', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultado.dados.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      {Object.values(row).map((val, j) => (
                        <td key={j} style={{ padding: '5px 10px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {String(val ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 4px' }}>Validador de SQL (Admin)</h3>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 12 }}>
          Verifica se um SQL contém DDL/DML proibido ou padrões de injeção.
        </div>
        <textarea
          className="input"
          rows={4}
          style={{ width: '100%', fontFamily: 'monospace', fontSize: 13, resize: 'vertical' }}
          placeholder="SELECT id, tipo FROM escrituracao_fiscal WHERE status = 'processado' LIMIT 10"
          value={sqlValidar}
          onChange={(e) => setSqlValidar(e.target.value)}
        />
        {validacaoResult && (
          <div style={{
            marginTop: 8, padding: '8px 12px', borderRadius: 6, fontSize: 13,
            background: validacaoResult.seguro ? 'var(--ok-bg, #e6f4ea)' : 'var(--crit-bg, #fde7e7)',
            color: validacaoResult.seguro ? 'var(--ok)' : 'var(--crit)',
          }}>
            {validacaoResult.seguro ? '✓ Seguro — ' : '✗ Rejeitado — '}{validacaoResult.mensagem}
          </div>
        )}
        <button className="btn" style={{ marginTop: 10 }} disabled={validarBusy || !sqlValidar.trim()} onClick={validar}>
          {validarBusy ? 'Validando…' : 'Validar SQL'}
        </button>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function ReportsWorkbenchScreen() {
  const [tab, setTab] = useState('reports');

  return (
    <div className="page">
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button className={'btn' + (tab === 'reports' ? ' btn-primary' : '')} onClick={() => setTab('reports')}>
          Relatórios Premium
        </button>
        <button className={'btn' + (tab === 'workbench' ? ' btn-primary' : '')} onClick={() => setTab('workbench')}>
          Workbench SQL
        </button>
      </div>
      {tab === 'reports' ? <ReportsTab /> : <WorkbenchTab />}
    </div>
  );
}
