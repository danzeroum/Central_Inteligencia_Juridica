/**
 * TransmissaoScreen — S-G.2
 * Transmissão e-CAC: envio, status, histórico e circuit breaker.
 */

import React, { useState, useEffect, useCallback } from 'react';
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

function Label({ children }) {
  return (
    <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
      {children}
    </label>
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

const SIT_COLOR = {
  transmitido: 'var(--ok)',
  processado:  'var(--ok)',
  pendente:    'var(--warn)',
  erro:        'var(--crit)',
  rejeitado:   'var(--crit)',
};

function SitChip({ situacao }) {
  return (
    <span style={{ color: SIT_COLOR[situacao] || 'inherit', fontWeight: 600 }}>{situacao}</span>
  );
}

function TransmissaoCard({ tx }) {
  if (!tx) return null;
  return (
    <div style={{ fontSize: 12, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
      <span style={{ color: 'var(--faint)' }}>TX ID:</span>
      <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{tx.transmissao_id}</span>
      <span style={{ color: 'var(--faint)' }}>Ficha ID:</span>
      <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{tx.ficha_id}</span>
      <span style={{ color: 'var(--faint)' }}>Situação:</span>
      <SitChip situacao={tx.situacao} />
      <span style={{ color: 'var(--faint)' }}>Protocolo:</span>
      <span>{tx.protocolo || '—'}</span>
      <span style={{ color: 'var(--faint)' }}>Modo:</span>
      <span>{tx.is_stub ? 'stub (sem e-CAC configurado)' : 'real'}</span>
      {tx.mensagem && (
        <>
          <span style={{ color: 'var(--faint)' }}>Mensagem:</span>
          <span style={{ color: 'var(--faint)' }}>{tx.mensagem}</span>
        </>
      )}
    </div>
  );
}

// ── Enviar tab ────────────────────────────────────────────────────────────────

const TIPOS_FICHA = ['per_restituicao', 'per_ressarcimento', 'dcomp_credito_apuracao', 'dcomp_pagamento_indevido'];

function EnviarTab() {
  const [fichaId,  setFichaId]  = useState('');
  const [tipoFicha,setTipoFicha]= useState('per_restituicao');
  const [cnpj,     setCnpj]     = useState('');
  const [xmlB64,   setXmlB64]   = useState('');
  const [result,   setResult]   = useState(null);
  const [busy,     setBusy]     = useState(false);
  const [err,      setErr]      = useState('');

  const enviar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/fiscal/transmissao/enviar', {
        ficha_id:   fichaId.trim(),
        tipo_ficha: tipoFicha,
        cnpj_masked: cnpj.trim(),
        xml_b64:    xmlB64.trim(),
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao transmitir.');
    } finally {
      setBusy(false);
    }
  };

  const xmlPlaceholder = btoa('<PER_DCOMP><Ficha id="test"/></PER_DCOMP>');

  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 12, padding: '8px 12px',
        background: 'var(--surface2)', borderRadius: 6 }}>
        Transmite a ficha PER/DCOMP ao webservice e-CAC. Em modo stub (sem certificado configurado),
        retorna <code>is_stub: true</code> com protocolo simulado.
      </div>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={enviar}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Enviar Transmissão</h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <div>
            <Label>ID da Ficha *</Label>
            <input className="input" required placeholder="uuid ou código"
              value={fichaId} onChange={e => setFichaId(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </div>
          <div>
            <Label>Tipo da Ficha *</Label>
            <select className="input" value={tipoFicha} onChange={e => setTipoFicha(e.target.value)}
              style={{ fontSize: 12 }}>
              {TIPOS_FICHA.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div style={{ gridColumn: '1/-1' }}>
            <Label>CNPJ mascarado (LGPD) *</Label>
            <input className="input" required placeholder="11.222.***.**/0001-**"
              value={cnpj} onChange={e => setCnpj(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div style={{ gridColumn: '1/-1' }}>
            <Label>XML em Base64 *</Label>
            <textarea className="input" rows={5} required
              placeholder={xmlPlaceholder}
              value={xmlB64} onChange={e => setXmlB64(e.target.value)}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
            <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2 }}>
              Base64 do XML da ficha PER/DCOMP
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Enviando…' : '↗ Transmitir'}
        </button>
      </form>

      {result && (
        <OkBox>
          <div style={{ fontWeight: 600, marginBottom: 8,
            color: result.situacao === 'erro' ? 'var(--crit)' : 'var(--ok)' }}>
            {result.situacao === 'erro' ? '✗' : '✓'} Transmissão {result.situacao}
            {result.is_stub ? ' (stub)' : ''}
          </div>
          <TransmissaoCard tx={result} />
        </OkBox>
      )}
    </div>
  );
}

// ── Status tab ────────────────────────────────────────────────────────────────

function StatusTab() {
  const [txId,   setTxId]   = useState('');
  const [result, setResult] = useState(null);
  const [busy,   setBusy]   = useState(false);
  const [err,    setErr]    = useState('');

  const consultar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.get(`/api/v1/fiscal/transmissao/status/${txId.trim()}`);
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Transmissão não encontrada.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <ErrAlert msg={err} />
      <form onSubmit={consultar} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input className="input" required placeholder="ID da transmissão"
          value={txId} onChange={e => setTxId(e.target.value)}
          style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }} />
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? '…' : 'Consultar'}
        </button>
      </form>
      {result && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>
            Status: <SitChip situacao={result.situacao} />
          </div>
          <TransmissaoCard tx={result} />
        </div>
      )}
    </div>
  );
}

// ── Histórico tab ─────────────────────────────────────────────────────────────

function HistoricoTab() {
  const [items,   setItems]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [err,     setErr]     = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const data = await api.get('/api/v1/fiscal/transmissao/historico');
      setItems(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao carregar histórico.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, []);

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button className="btn btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Atualizando…' : '↻ Atualizar'}
        </button>
      </div>
      <ErrAlert msg={err} />
      {loading && !items && (
        <div className="card" style={{ padding: 16, opacity: 0.5, fontSize: 13 }}>Carregando…</div>
      )}
      {items !== null && items.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--faint)', fontSize: 13, padding: '24px 0' }}>
          Nenhuma transmissão na sessão atual.
        </div>
      )}
      {items && items.length > 0 && (
        <section className="card" style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Histórico ({items.length})
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['TX ID', 'Ficha ID', 'Tipo', 'Situação', 'Protocolo', 'Stub', 'Enviado em'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '4px 8px',
                      color: 'var(--faint)', fontWeight: 600,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map(tx => (
                  <tr key={tx.transmissao_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                      {tx.transmissao_id.slice(0, 8)}…
                    </td>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                      {String(tx.ficha_id).slice(0, 8)}…
                    </td>
                    <td style={{ padding: '5px 8px' }}>{tx.tipo_ficha || '—'}</td>
                    <td style={{ padding: '5px 8px' }}><SitChip situacao={tx.situacao} /></td>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                      {tx.protocolo || '—'}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'center' }}>
                      {tx.is_stub ? 'sim' : 'não'}
                    </td>
                    <td style={{ padding: '5px 8px', color: 'var(--faint)', fontSize: 11 }}>
                      {tx.enviado_em ? tx.enviado_em.replace('T', ' ').slice(0, 16) : '—'}
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

// ── Circuit Breaker tab ────────────────────────────────────────────────────────

const CB_COLORS = { closed: 'var(--ok)', open: 'var(--crit)', half_open: 'var(--warn)' };

function CircuitTab() {
  const [cs,      setCs]      = useState(null);
  const [loading, setLoading] = useState(false);
  const [err,     setErr]     = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      const data = await api.get('/api/v1/fiscal/transmissao/circuit');
      setCs(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao carregar circuit breaker.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, []);

  return (
    <div style={{ maxWidth: 480 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button className="btn btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Atualizando…' : '↻ Atualizar'}
        </button>
      </div>
      <ErrAlert msg={err} />
      {cs && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              background: CB_COLORS[cs.state] || 'var(--faint)',
            }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                Circuit Breaker:{' '}
                <span style={{ color: CB_COLORS[cs.state] || 'inherit' }}>{cs.state?.toUpperCase()}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
                {cs.is_stub ? 'Modo stub (e-CAC não configurado)' : 'Modo real (e-CAC configurado)'}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
            <div className="card" style={{ padding: 12 }}>
              <div style={{ color: 'var(--faint)', marginBottom: 4 }}>Falhas consecutivas</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: cs.failure_count > 0 ? 'var(--crit)' : 'var(--ok)' }}>
                {cs.failure_count ?? 0}
              </div>
            </div>
            <div className="card" style={{ padding: 12 }}>
              <div style={{ color: 'var(--faint)', marginBottom: 4 }}>Threshold</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{cs.failure_threshold ?? '—'}</div>
            </div>
          </div>

          {cs.retry_after && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--crit-bg)', borderRadius: 6,
              fontSize: 12, color: 'var(--crit)' }}>
              Circuit aberto — retry após: {cs.retry_after}
            </div>
          )}

          {cs.last_failure_at && (
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--faint)' }}>
              Última falha: {cs.last_failure_at.replace('T', ' ').slice(0, 19)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main screen ────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'enviar',   label: 'Enviar' },
  { id: 'status',   label: 'Status' },
  { id: 'historico',label: 'Histórico' },
  { id: 'circuit',  label: 'Circuit Breaker' },
];

export default function TransmissaoScreen() {
  const [tab, setTab] = useState('enviar');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Transmissão e-CAC</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Envio de PER/DCOMP ao webservice SOAP da Receita Federal (e-CAC)
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

      {tab === 'enviar'    && <EnviarTab />}
      {tab === 'status'    && <StatusTab />}
      {tab === 'historico' && <HistoricoTab />}
      {tab === 'circuit'   && <CircuitTab />}
    </div>
  );
}
