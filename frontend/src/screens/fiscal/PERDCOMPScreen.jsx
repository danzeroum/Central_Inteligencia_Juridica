/**
 * PERDCOMPScreen — S-G.2
 * Gerador de fichas PER/DCOMP: tipos disponíveis, geração e validação.
 */

import React, { useState, useEffect } from 'react';
import { api } from '../../api/client.js';

// ── helpers ──────────────────────────────────────────────────────────────────

function ErrAlert({ msg }) {
  if (!msg) return null;
  return (
    <div role="alert" style={{
      background: 'var(--crit-bg, #fee2e2)', color: 'var(--crit)', borderRadius: 6,
      padding: '10px 14px', marginBottom: 12, fontSize: 13,
    }}>{msg}</div>
  );
}

function OkBox({ children }) {
  return (
    <div style={{
      background: 'var(--surface2, #1e293b)', borderRadius: 6,
      padding: '12px 16px', marginTop: 12, fontSize: 12,
    }}>{children}</div>
  );
}

function Label({ children }) {
  return (
    <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
      {children}
    </label>
  );
}

function FichaCard({ ficha }) {
  if (!ficha) return null;
  const f = ficha.ficha || ficha;
  return (
    <OkBox>
      <div style={{ fontWeight: 600, color: 'var(--ok)', marginBottom: 8 }}>✓ Ficha gerada</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', marginBottom: 8 }}>
        <span style={{ color: 'var(--faint)' }}>ID:</span>
        <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{f.ficha_id || f.id || '—'}</span>
        <span style={{ color: 'var(--faint)' }}>Tipo:</span>
        <span>{f.tipo_ficha || '—'}</span>
        <span style={{ color: 'var(--faint)' }}>Tributo:</span>
        <span>{f.tributo || '—'}</span>
        <span style={{ color: 'var(--faint)' }}>Crédito:</span>
        <span style={{ color: 'var(--ok)', fontWeight: 600 }}>{f.valor_credito || '—'}</span>
        <span style={{ color: 'var(--faint)' }}>Status:</span>
        <span>{f.status || f.situacao || '—'}</span>
      </div>
      {f.xml_b64 && (
        <details style={{ fontSize: 11 }}>
          <summary style={{ cursor: 'pointer', color: 'var(--faint)' }}>XML (base64)</summary>
          <pre style={{ marginTop: 6, overflowX: 'auto', color: 'var(--faint)', fontSize: 10 }}>
            {f.xml_b64.slice(0, 300)}{f.xml_b64.length > 300 ? '…' : ''}
          </pre>
        </details>
      )}
    </OkBox>
  );
}

// ── Tipos Sidebar ─────────────────────────────────────────────────────────────

function TiposSidebar({ tipos, selected, onSelect }) {
  if (!tipos.length) return null;
  return (
    <section className="card" style={{ padding: 12, marginBottom: 16 }}>
      <h3 style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--faint)' }}>
        TIPOS DISPONÍVEIS
      </h3>
      {tipos.map(t => (
        <button key={t.tipo}
          onClick={() => onSelect(t.tipo)}
          style={{
            width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 4,
            marginBottom: 4, fontSize: 12, cursor: 'pointer',
            background: selected === t.tipo ? 'var(--accent-bg, #1e3a5f)' : 'transparent',
            border: selected === t.tipo ? '1px solid var(--accent)' : '1px solid transparent',
            color: 'var(--fg)',
          }}>
          <div style={{ fontWeight: 600 }}>{t.nome}</div>
          <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2 }}>{t.descricao.slice(0, 80)}…</div>
          <div style={{ fontSize: 11, marginTop: 4, color: 'var(--info)' }}>
            {t.tributos_elegiveis.join(' · ')}
            {t.requer_debitos ? ' · requer débitos' : ''}
          </div>
        </button>
      ))}
    </section>
  );
}

// ── Gerar tab ─────────────────────────────────────────────────────────────────

function GerarTab({ tipos }) {
  const [tipoFicha,      setTipoFicha]      = useState('');
  const [cnpj,           setCnpj]           = useState('');
  const [nome,           setNome]           = useState('');
  const [tributo,        setTributo]        = useState('PIS');
  const [periodo,        setPeriodo]        = useState('');
  const [valorCredito,   setValorCredito]   = useState('');
  const [result,         setResult]         = useState(null);
  const [busy,           setBusy]           = useState(false);
  const [err,            setErr]            = useState('');

  const tipoInfo = tipos.find(t => t.tipo === tipoFicha);

  const gerar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/fiscal/per-dcomp/gerar', {
        cnpj_masked:       cnpj.trim(),
        nome_empresarial:  nome.trim(),
        tributo:           tributo.toUpperCase(),
        periodo_apuracao:  periodo.trim(),
        valor_credito:     valorCredito.trim(),
        tipo_ficha:        tipoFicha || undefined,
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao gerar ficha.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, maxWidth: 900 }}>
      <TiposSidebar tipos={tipos} selected={tipoFicha} onSelect={setTipoFicha} />

      <div>
        <ErrAlert msg={err} />
        <form className="card" style={{ padding: 16 }} onSubmit={gerar}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Gerar Ficha PER/DCOMP</h3>
          {tipoInfo && (
            <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 12, padding: '8px 10px',
              background: 'var(--surface2)', borderRadius: 4 }}>
              {tipoInfo.descricao}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
            <div style={{ gridColumn: '1/-1' }}>
              <Label>CNPJ mascarado (LGPD) *</Label>
              <input className="input" required placeholder="11.222.***.**/0001-**"
                value={cnpj} onChange={e => setCnpj(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <Label>Nome empresarial *</Label>
              <input className="input" required placeholder="Razão Social Ltda."
                value={nome} onChange={e => setNome(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div>
              <Label>Tributo *</Label>
              <select className="input" value={tributo} onChange={e => setTributo(e.target.value)}
                style={{ fontSize: 12 }}>
                {['PIS', 'COFINS', 'IRPJ', 'CSLL', 'IPI'].map(t => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <Label>Período de Apuração *</Label>
              <input className="input" required placeholder="2025-01" type="month"
                value={periodo} onChange={e => setPeriodo(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <Label>Valor do crédito (R$) *</Label>
              <input className="input" required placeholder="1500.00" type="number"
                step="0.01" min="0"
                value={valorCredito} onChange={e => setValorCredito(e.target.value)}
                style={{ fontSize: 12 }} />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={busy} style={{ justifyContent: 'center' }}>
            {busy ? 'Gerando…' : '⚙ Gerar Ficha'}
          </button>
        </form>
        <FichaCard ficha={result} />
      </div>
    </div>
  );
}

// ── Gerar de Apuração tab ────────────────────────────────────────────────────

function GerarDeApuracaoTab({ tipos }) {
  const [tipoFicha,    setTipoFicha]    = useState('');
  const [cnpj,         setCnpj]         = useState('');
  const [nome,         setNome]         = useState('');
  const [tributo,      setTributo]      = useState('PIS');
  const [periodo,      setPeriodo]      = useState('');
  const [saldo,        setSaldo]        = useState('');
  const [situacao,     setSituacao]     = useState('credor');
  const [result,       setResult]       = useState(null);
  const [busy,         setBusy]         = useState(false);
  const [err,          setErr]          = useState('');

  const gerar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/fiscal/per-dcomp/gerar-de-apuracao', {
        cnpj_masked:      cnpj.trim(),
        nome_empresarial: nome.trim(),
        tipo_ficha:       tipoFicha || undefined,
        apuracao: {
          tributo:             tributo.toUpperCase(),
          periodo_competencia: periodo.trim(),
          saldo_apurado:       saldo.trim(),
          situacao:            situacao,
        },
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao gerar ficha de apuração.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, maxWidth: 900 }}>
      <TiposSidebar tipos={tipos} selected={tipoFicha} onSelect={setTipoFicha} />

      <div>
        <ErrAlert msg={err} />
        <form className="card" style={{ padding: 16 }} onSubmit={gerar}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Gerar de Apuração</h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
            <div style={{ gridColumn: '1/-1' }}>
              <Label>CNPJ mascarado (LGPD) *</Label>
              <input className="input" required placeholder="11.222.***.**/0001-**"
                value={cnpj} onChange={e => setCnpj(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <Label>Nome empresarial *</Label>
              <input className="input" required
                value={nome} onChange={e => setNome(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div>
              <Label>Tributo *</Label>
              <select className="input" value={tributo} onChange={e => setTributo(e.target.value)}
                style={{ fontSize: 12 }}>
                {['PIS', 'COFINS', 'IRPJ', 'CSLL', 'IPI'].map(t => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <Label>Período (AAAA-MM) *</Label>
              <input className="input" required type="month"
                value={periodo} onChange={e => setPeriodo(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div>
              <Label>Saldo apurado (R$) *</Label>
              <input className="input" required type="number" step="0.01" min="0"
                value={saldo} onChange={e => setSaldo(e.target.value)} style={{ fontSize: 12 }} />
            </div>
            <div>
              <Label>Situação</Label>
              <select className="input" value={situacao} onChange={e => setSituacao(e.target.value)}
                style={{ fontSize: 12 }}>
                {['credor', 'devedor', 'equilibrado'].map(s => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Gerando…' : '⚙ Gerar de Apuração'}
          </button>
        </form>
        <FichaCard ficha={result} />
      </div>
    </div>
  );
}

// ── Validar tab ───────────────────────────────────────────────────────────────

function ValidarTab() {
  const [cnpj,        setCnpj]        = useState('');
  const [nome,        setNome]        = useState('');
  const [tributo,     setTributo]     = useState('PIS');
  const [periodo,     setPeriodo]     = useState('');
  const [valorCred,   setValorCred]   = useState('');
  const [tipoFicha,   setTipoFicha]   = useState('per_restituicao');
  const [result,      setResult]      = useState(null);
  const [busy,        setBusy]        = useState(false);
  const [err,         setErr]         = useState('');

  const validar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/fiscal/per-dcomp/validar', {
        cnpj_masked:      cnpj.trim(),
        nome_empresarial: nome.trim(),
        tributo:          tributo.toUpperCase(),
        periodo_apuracao: periodo.trim(),
        valor_credito:    valorCred.trim(),
        tipo_ficha:       tipoFicha,
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao validar ficha.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={validar}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Validar Ficha PER/DCOMP</h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <div style={{ gridColumn: '1/-1' }}>
            <Label>CNPJ mascarado *</Label>
            <input className="input" required value={cnpj}
              onChange={e => setCnpj(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div style={{ gridColumn: '1/-1' }}>
            <Label>Nome empresarial *</Label>
            <input className="input" required value={nome}
              onChange={e => setNome(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div>
            <Label>Tributo *</Label>
            <select className="input" value={tributo} onChange={e => setTributo(e.target.value)}
              style={{ fontSize: 12 }}>
              {['PIS', 'COFINS', 'IRPJ', 'CSLL', 'IPI'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <Label>Período *</Label>
            <input className="input" required type="month"
              value={periodo} onChange={e => setPeriodo(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div>
            <Label>Valor crédito (R$) *</Label>
            <input className="input" required type="number" step="0.01" min="0"
              value={valorCred} onChange={e => setValorCred(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div>
            <Label>Tipo ficha *</Label>
            <input className="input" required value={tipoFicha}
              onChange={e => setTipoFicha(e.target.value)} style={{ fontSize: 12 }} />
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Validando…' : '✓ Validar'}
        </button>
      </form>

      {result && (
        <div style={{
          marginTop: 12, padding: '12px 16px', borderRadius: 6, fontSize: 12,
          background: result.valido ? 'var(--ok-bg, #e6f4ea)' : 'var(--crit-bg, #fde7e7)',
          color: result.valido ? 'var(--ok)' : 'var(--crit)',
        }}>
          {result.valido ? '✓ Ficha válida' : '✗ Ficha inválida'}
          {result.erros?.length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>
              {result.erros.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
          {result.avisos?.length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: 16, color: 'var(--warn)' }}>
              {result.avisos.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

const TABS = [
  { id: 'gerar',     label: 'Gerar Ficha' },
  { id: 'apuracao',  label: 'Gerar de Apuração' },
  { id: 'validar',   label: 'Validar' },
];

export default function PERDCOMPScreen() {
  const [tab,  setTab]  = useState('gerar');
  const [tipos, setTipos] = useState([]);

  useEffect(() => {
    api.get('/api/v1/fiscal/per-dcomp/tipos').then(setTipos).catch(() => {});
  }, []);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>PER/DCOMP</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Pedido de Restituição e Declaração de Compensação tributária
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

      {tab === 'gerar'    && <GerarTab tipos={tipos} />}
      {tab === 'apuracao' && <GerarDeApuracaoTab tipos={tipos} />}
      {tab === 'validar'  && <ValidarTab />}
    </div>
  );
}
