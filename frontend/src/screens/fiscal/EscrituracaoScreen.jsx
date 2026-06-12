/**
 * EscrituracaoScreen — S-G.1
 * Painel operacional SPED: upload, detalhe + achados + registros, apurações.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../../api/client.js';
import { getToken } from '../../api/auth.js';

const BASE = import.meta.env.VITE_API_BASE || '';

// ── helpers ──────────────────────────────────────────────────────────────────

const SEV_COLOR = {
  erro:       'var(--crit, #ef4444)',
  aviso:      'var(--warn, #f59e0b)',
  informacao: 'var(--info, #3b82f6)',
};

const SIT_COLOR = {
  devedor:     'var(--crit)',
  credor:      'var(--ok)',
  equilibrado: 'var(--faint)',
  erro:        'var(--crit)',
};

function SevBadge({ sev }) {
  return (
    <span style={{
      background: SEV_COLOR[sev] || 'var(--faint)',
      color: '#fff', borderRadius: 4, padding: '1px 6px',
      fontSize: 11, fontWeight: 600,
    }}>{sev}</span>
  );
}

function LoadingCard() {
  return (
    <div className="card" style={{ padding: 16, opacity: 0.5, fontSize: 13 }}>
      Carregando…
    </div>
  );
}

function EmptyState({ msg }) {
  return (
    <div style={{ textAlign: 'center', color: 'var(--faint)', fontSize: 13, padding: '24px 0' }}>
      {msg}
    </div>
  );
}

function ErrAlert({ msg }) {
  if (!msg) return null;
  return (
    <div role="alert" style={{
      background: 'var(--crit-bg, #fee2e2)', color: 'var(--crit)', borderRadius: 6,
      padding: '10px 14px', marginBottom: 12, fontSize: 13,
    }}>{msg}</div>
  );
}

// ── Upload ───────────────────────────────────────────────────────────────────

const TIPOS  = ['efd_icms', 'efd_contrib', 'xml', 'pdf', 'outro'];
const REGIMES = ['lucro_real', 'lucro_presumido', 'simples'];
const YEAR    = new Date().getFullYear();

function UploadTab({ onUploaded }) {
  const fileRef  = useRef(null);
  const [tipo,   setTipo]   = useState('efd_icms');
  const [ano,    setAno]    = useState(String(YEAR));
  const [mes,    setMes]    = useState('');
  const [cnpj,   setCnpj]   = useState('');
  const [regime, setRegime] = useState('lucro_real');
  const [uf,     setUf]     = useState('');
  const [busy,   setBusy]   = useState(false);
  const [err,    setErr]    = useState('');
  const [result, setResult] = useState(null);

  const doUpload = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    const fd = new FormData();
    fd.append('file', file);
    fd.append('tipo', tipo);
    fd.append('ano', ano);
    if (mes)        fd.append('mes', mes);
    if (cnpj.trim()) fd.append('cnpj_masked', cnpj.trim());
    fd.append('regime', regime);
    if (uf.trim())  fd.append('uf', uf.trim().toUpperCase());

    setBusy(true);
    setErr('');
    setResult(null);
    try {
      const token = getToken();
      const res = await fetch(`${BASE}/api/v1/fiscal/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
      if (data.db_id) onUploaded(data.db_id);
    } catch (ex) {
      setErr(ex?.message || 'Falha no upload.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={doUpload}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Upload de Arquivo Fiscal</h3>

        <div className="field" style={{ marginBottom: 10 }}>
          <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
            Arquivo *
          </label>
          <input ref={fileRef} type="file" accept=".txt,.xml,.pdf,.zip" required
            className="input" style={{ fontSize: 12 }} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <div className="field">
            <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>Tipo</label>
            <select className="input" value={tipo} onChange={e => setTipo(e.target.value)} style={{ fontSize: 12 }}>
              {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>Regime</label>
            <select className="input" value={regime} onChange={e => setRegime(e.target.value)} style={{ fontSize: 12 }}>
              {REGIMES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 70px', gap: 8, marginBottom: 10 }}>
          <div className="field">
            <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>Ano *</label>
            <input className="input" type="number" min="2000" max="2100" required
              value={ano} onChange={e => setAno(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div className="field">
            <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>Mês</label>
            <input className="input" type="number" min="1" max="12" placeholder="1–12"
              value={mes} onChange={e => setMes(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div className="field">
            <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>UF</label>
            <input className="input" maxLength={2} placeholder="SP"
              value={uf} onChange={e => setUf(e.target.value)} style={{ fontSize: 12 }} />
          </div>
        </div>

        <div className="field" style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
            CNPJ mascarado (LGPD)
          </label>
          <input className="input" placeholder="ex: 11.222.***.**/0001-**"
            value={cnpj} onChange={e => setCnpj(e.target.value)} style={{ fontSize: 12 }} />
        </div>

        <button type="submit" className="btn btn-primary" disabled={busy}
          style={{ justifyContent: 'center' }}>
          {busy ? 'Enviando…' : '↑ Enviar arquivo'}
        </button>
      </form>

      {result && (
        <div className="card" style={{ padding: 16, marginTop: 12, fontSize: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--ok)' }}>✓ Upload aceito</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
            <span style={{ color: 'var(--faint)' }}>Arquivo:</span>
            <span>{result.filename}</span>
            <span style={{ color: 'var(--faint)' }}>Tipo:</span>
            <span>{result.file_type}</span>
            <span style={{ color: 'var(--faint)' }}>Tamanho:</span>
            <span>{(result.size_bytes / 1024).toFixed(1)} KB</span>
            <span style={{ color: 'var(--faint)' }}>Correlation ID:</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{result.correlation_id}</span>
            {result.db_id && (
              <>
                <span style={{ color: 'var(--faint)' }}>Escrituração ID:</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{result.db_id}</span>
              </>
            )}
          </div>
          {result.db_id && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--faint)' }}>
              Navegando para Detalhe automaticamente…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Detalhe ──────────────────────────────────────────────────────────────────

function StatusChip({ status }) {
  const colors = {
    pendente:     'var(--warn)',
    processando:  'var(--info)',
    concluido:    'var(--ok)',
    erro:         'var(--crit)',
    retificado:   'var(--accent)',
  };
  return (
    <span style={{ color: colors[status] || 'inherit', fontWeight: 600 }}>{status}</span>
  );
}

function AchadosTable({ achados }) {
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Achados ({achados.total})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Reg', 'Linha', 'Regra', 'Campo', 'Sev.', 'Descrição'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '4px 8px',
                  color: 'var(--faint)', fontWeight: 600,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {achados.achados.map((a, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{a.tipo_registro}</td>
                <td style={{ padding: '5px 8px' }}>{a.numero_linha}</td>
                <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 11 }}>{a.regra_id}</td>
                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{a.campo}</td>
                <td style={{ padding: '5px 8px' }}><SevBadge sev={a.severidade} /></td>
                <td style={{ padding: '5px 8px', color: 'var(--faint)' }}>{a.descricao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RegistrosTable({ registros }) {
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Registros ({registros.total} total, exibindo {registros.registros.length})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Bloco', 'Tipo', 'Linha', 'Campos (prévia)'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '4px 8px',
                  color: 'var(--faint)', fontWeight: 600,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {registros.registros.map((r) => (
              <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{r.bloco}</td>
                <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 600 }}>{r.tipo_registro}</td>
                <td style={{ padding: '5px 8px' }}>{r.numero_linha}</td>
                <td style={{ padding: '5px 8px', color: 'var(--faint)', fontSize: 11 }}>
                  {Object.keys(r.campos).slice(0, 5).join(', ')}
                  {Object.keys(r.campos).length > 5 ? ' …' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DetalheTab({ preloadId }) {
  const [inputId,    setInputId]    = useState(preloadId || '');
  const [eid,        setEid]        = useState('');
  const [sub,        setSub]        = useState('achados');
  const [loading,    setLoading]    = useState(false);
  const [err,        setErr]        = useState('');
  const [escrit,     setEscrit]     = useState(null);
  const [achados,    setAchados]    = useState(null);
  const [registros,  setRegistros]  = useState(null);
  const [apurBusy,   setApurBusy]   = useState(false);
  const [apurResult, setApurResult] = useState(null);

  const fetchEscrit = useCallback(async (id) => {
    setLoading(true);
    setErr('');
    setEscrit(null);
    setAchados(null);
    setRegistros(null);
    setApurResult(null);
    try {
      const e = await api.get(`/api/v1/fiscal/escrituracoes/${id}`);
      setEscrit(e);
      setEid(id);
    } catch (ex) {
      setErr(ex?.message || 'Escrituração não encontrada.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (preloadId) {
      setInputId(preloadId);
      fetchEscrit(preloadId);
    }
  }, [preloadId]);

  const onSearch = (e) => {
    e.preventDefault();
    const id = inputId.trim();
    if (id) fetchEscrit(id);
  };

  const loadAchados = useCallback(async () => {
    if (!eid || achados) return;
    try {
      const a = await api.get(`/api/v1/fiscal/escrituracoes/${eid}/achados?limit=100`);
      setAchados(a);
    } catch (ex) {
      setAchados({ achados: [], total: 0, _err: ex?.message });
    }
  }, [eid, achados]);

  const loadRegistros = useCallback(async () => {
    if (!eid || registros) return;
    try {
      const r = await api.get(`/api/v1/fiscal/escrituracoes/${eid}/registros?limit=100`);
      setRegistros(r);
    } catch (ex) {
      setRegistros({ registros: [], total: 0, _err: ex?.message });
    }
  }, [eid, registros]);

  useEffect(() => {
    if (sub === 'achados')   loadAchados();
    if (sub === 'registros') loadRegistros();
  }, [sub, eid]);

  const triggerApuracao = async () => {
    if (!eid) return;
    setApurBusy(true);
    try {
      const r = await api.post(`/api/v1/fiscal/escrituracoes/${eid}/apuracao`);
      setApurResult(r);
    } catch (ex) {
      setApurResult({ _err: ex?.message });
    } finally {
      setApurBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 900 }}>
      <form onSubmit={onSearch} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input className="input" placeholder="ID da escrituração (UUID)"
          value={inputId} onChange={e => setInputId(e.target.value)}
          style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }} />
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? '…' : 'Consultar'}
        </button>
      </form>

      <ErrAlert msg={err} />

      {escrit && (
        <>
          <div className="card" style={{ padding: 16, marginBottom: 12 }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', marginBottom: 12,
            }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>
                Escrituração{' '}
                <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
                  {escrit.id.slice(0, 8)}…
                </span>
              </h3>
              <button className="btn btn-sm" onClick={triggerApuracao} disabled={apurBusy}>
                {apurBusy ? 'Calculando…' : '⚡ Calcular Apuração'}
              </button>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: 8, fontSize: 12,
            }}>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Status</div>
                <StatusChip status={escrit.status} />
              </div>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Tipo</div>
                {escrit.tipo}
              </div>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Origem</div>
                {escrit.origem}
              </div>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Registros</div>
                {escrit.total_registros ?? '—'}
              </div>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Erros</div>
                <span style={{ color: 'var(--crit)' }}>{escrit.total_erros ?? 0}</span>
              </div>
              <div>
                <div style={{ color: 'var(--faint)', marginBottom: 2 }}>Avisos</div>
                <span style={{ color: 'var(--warn)' }}>{escrit.total_avisos ?? 0}</span>
              </div>
            </div>

            {apurResult && (
              <div style={{
                marginTop: 12, padding: '10px 12px',
                background: 'var(--surface2)', borderRadius: 6, fontSize: 12,
              }}>
                {apurResult._err
                  ? <span style={{ color: 'var(--crit)' }}>{apurResult._err}</span>
                  : (
                    <><span style={{ color: 'var(--ok)', fontWeight: 600 }}>Apuração concluída</span>
                      {' — '}{apurResult.resumo}</>
                  )}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
            {[['achados', 'Achados'], ['registros', 'Registros']].map(([k, l]) => (
              <button key={k}
                className={'btn btn-sm' + (sub === k ? ' btn-primary' : '')}
                onClick={() => setSub(k)}>{l}</button>
            ))}
          </div>

          {sub === 'achados' && (
            achados === null
              ? <LoadingCard />
              : achados._err
                ? <ErrAlert msg={achados._err} />
                : achados.achados.length === 0
                  ? <EmptyState msg="Nenhum achado registrado." />
                  : <AchadosTable achados={achados} />
          )}

          {sub === 'registros' && (
            registros === null
              ? <LoadingCard />
              : registros._err
                ? <ErrAlert msg={registros._err} />
                : registros.registros.length === 0
                  ? <EmptyState msg="Nenhum registro carregado." />
                  : <RegistrosTable registros={registros} />
          )}
        </>
      )}
    </div>
  );
}

// ── Apurações ────────────────────────────────────────────────────────────────

function ApuracoesTab() {
  const [items,   setItems]   = useState(null);
  const [err,     setErr]     = useState('');
  const [loading, setLoading] = useState(false);
  const [periodo, setPeriodo] = useState('');
  const [tributo, setTributo] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setErr('');
    try {
      const qs = new URLSearchParams({ limit: '50' });
      if (periodo.trim()) qs.set('periodo', periodo.trim());
      if (tributo.trim()) qs.set('tributo', tributo.trim().toUpperCase());
      const data = await api.get(`/api/v1/fiscal/apuracoes?${qs.toString()}`);
      setItems(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao carregar apurações.');
    } finally {
      setLoading(false);
    }
  }, [periodo, tributo]);

  useEffect(() => { load(); }, []);

  const onFilter = (e) => { e.preventDefault(); load(); };

  return (
    <div style={{ maxWidth: 900 }}>
      <form onSubmit={onFilter} style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'flex-end' }}>
        <div>
          <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
            Período (AAAA-MM)
          </label>
          <input className="input" placeholder="2025-01" value={periodo}
            onChange={e => setPeriodo(e.target.value)} style={{ width: 110, fontSize: 12 }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
            Tributo
          </label>
          <select className="input" value={tributo}
            onChange={e => setTributo(e.target.value)} style={{ fontSize: 12 }}>
            <option value="">Todos</option>
            {['ICMS', 'PIS', 'COFINS'].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button type="submit" className="btn" disabled={loading} style={{ marginBottom: 0 }}>
          {loading ? 'Buscando…' : 'Filtrar'}
        </button>
      </form>

      <ErrAlert msg={err} />

      {items === null && !err && <LoadingCard />}
      {items !== null && items.length === 0 && (
        <EmptyState msg="Nenhuma apuração encontrada para os filtros selecionados." />
      )}
      {items && items.length > 0 && (
        <section className="card" style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Apurações ({items.length})
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Escrituração', 'Período', 'Tributo', 'Débitos', 'Créditos', 'Saldo', 'Situação'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '4px 8px',
                      color: 'var(--faint)', fontWeight: 600,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                      {a.escrituracao_id.slice(0, 8)}…
                    </td>
                    <td style={{ padding: '5px 8px' }}>{a.periodo_competencia || '—'}</td>
                    <td style={{ padding: '5px 8px', fontWeight: 600 }}>{a.tributo}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: SIT_COLOR.devedor }}>
                      {a.total_debitos}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: SIT_COLOR.credor }}>
                      {a.total_creditos}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 600 }}>
                      {a.saldo_apurado}
                    </td>
                    <td style={{ padding: '5px 8px' }}>
                      <span style={{ color: SIT_COLOR[a.situacao] || 'inherit' }}>{a.situacao}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

const TABS = [
  { id: 'upload',    label: 'Upload' },
  { id: 'detalhe',   label: 'Detalhe / Achados' },
  { id: 'apuracoes', label: 'Apurações' },
];

export default function EscrituracaoScreen() {
  const [tab,          setTab]          = useState('upload');
  const [lastUploadId, setLastUploadId] = useState(null);

  const onUploaded = (id) => {
    setLastUploadId(id);
    setTab('detalhe');
  };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Escriturações SPED</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Upload, análise de achados, registros e apuração tributária
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {TABS.map(t => (
          <button key={t.id}
            className={'btn btn-sm' + (tab === t.id ? ' btn-primary' : '')}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'upload'    && <UploadTab onUploaded={onUploaded} />}
      {tab === 'detalhe'   && <DetalheTab preloadId={lastUploadId} />}
      {tab === 'apuracoes' && <ApuracoesTab />}
    </div>
  );
}
