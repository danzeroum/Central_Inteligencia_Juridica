/**
 * RetificacaoScreen — S-G.2
 * Retificação SPED: comparação de registros, validação de layout e nota de correção.
 */

import React, { useState } from 'react';
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

const SAMPLE_ORIG = JSON.stringify([
  { tipo_registro: 'C100', numero_linha: 10, dados: { VL_DOC: '1000.00' } },
  { tipo_registro: 'E110', numero_linha: 20, dados: { VL_TOT_DEBITOS: '500.00' } },
], null, 2);

const SAMPLE_RET = JSON.stringify([
  { tipo_registro: 'C100', numero_linha: 10, dados: { VL_DOC: '1500.00' } },
  { tipo_registro: 'E110', numero_linha: 21, dados: { VL_TOT_DEBITOS: '600.00' } },
], null, 2);

// ── Comparar tab ─────────────────────────────────────────────────────────────

function ComparacaoTab() {
  const [origJson,  setOrigJson]  = useState(SAMPLE_ORIG);
  const [retJson,   setRetJson]   = useState(SAMPLE_RET);
  const [result,    setResult]    = useState(null);
  const [busy,      setBusy]      = useState(false);
  const [err,       setErr]       = useState('');

  const comparar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const originais   = JSON.parse(origJson);
      const retificados = JSON.parse(retJson);
      const data = await api.post('/api/v1/fiscal/retificacao/comparar', {
        registros_originais:   originais,
        registros_retificados: retificados,
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao comparar.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 900 }}>
      <ErrAlert msg={err} />
      <form onSubmit={comparar}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <Label>Registros Originais (JSON)</Label>
            <textarea className="input" rows={12} value={origJson}
              onChange={e => setOrigJson(e.target.value)}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
          </div>
          <div>
            <Label>Registros Retificados (JSON)</Label>
            <textarea className="input" rows={12} value={retJson}
              onChange={e => setRetJson(e.target.value)}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Comparando…' : '⟺ Comparar'}
        </button>
      </form>

      {result && (
        <OkBox>
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontWeight: 600, color: result.tem_diferencas ? 'var(--warn)' : 'var(--ok)' }}>
              {result.tem_diferencas ? `${result.total_alteracoes} diferença(s) encontrada(s)` : '✓ Sem diferenças'}
            </span>
          </div>
          {result.adicionados.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: 'var(--ok)', fontWeight: 600 }}>
                +{result.adicionados.length} adicionado(s):
              </span>{' '}
              {result.adicionados.map(r => r.tipo_registro).join(', ')}
            </div>
          )}
          {result.removidos.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: 'var(--crit)', fontWeight: 600 }}>
                -{result.removidos.length} removido(s):
              </span>{' '}
              {result.removidos.map(r => r.tipo_registro).join(', ')}
            </div>
          )}
          {result.modificados.length > 0 && (
            <div>
              <span style={{ color: 'var(--warn)', fontWeight: 600 }}>
                ~{result.modificados.length} modificado(s):
              </span>
              {result.modificados.map((m, i) => (
                <div key={i} style={{ marginTop: 6, paddingLeft: 12, borderLeft: '2px solid var(--warn)' }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{m.tipo_registro}</span>
                  {' linha '}{m.numero_linha}
                  {Object.entries(m.campos_alterados).map(([campo, vals]) => (
                    <div key={campo} style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2 }}>
                      {campo}: <span style={{ color: 'var(--crit)' }}>{JSON.stringify(vals.original)}</span>
                      {' → '}<span style={{ color: 'var(--ok)' }}>{JSON.stringify(vals.retificado)}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </OkBox>
      )}
    </div>
  );
}

// ── Validar Layout tab ────────────────────────────────────────────────────────

const SAMPLE_LAYOUT = JSON.stringify([
  { tipo_registro: 'C100', numero_linha: 1, dados: { _raw: new Array(26).fill(0) } },
  { tipo_registro: '9999', numero_linha: 2, dados: { _raw: [0, 0] } },
], null, 2);

function ValidarLayoutTab() {
  const [regJson, setRegJson] = useState(SAMPLE_LAYOUT);
  const [result,  setResult]  = useState(null);
  const [busy,    setBusy]    = useState(false);
  const [err,     setErr]     = useState('');

  const validar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const registros = JSON.parse(regJson);
      const data = await api.post('/api/v1/fiscal/retificacao/validar-layout', { registros });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao validar layout.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 640 }}>
      <ErrAlert msg={err} />
      <form onSubmit={validar}>
        <div style={{ marginBottom: 12 }}>
          <Label>Registros (JSON)</Label>
          <textarea className="input" rows={14} value={regJson}
            onChange={e => setRegJson(e.target.value)}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Validando…' : '✓ Validar Layout'}
        </button>
      </form>

      {result && (
        <OkBox>
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            {result.valido
              ? <span style={{ color: 'var(--ok)' }}>✓ Layout válido</span>
              : <span style={{ color: 'var(--crit)' }}>✗ Layout inválido</span>}
            {' — '}{result.registros_validados}/{result.total_registros} registro(s) validado(s)
          </div>
          {result.erros?.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ color: 'var(--crit)', fontWeight: 600, marginBottom: 4 }}>Erros:</div>
              {result.erros.map((e, i) => (
                <div key={i} style={{ fontSize: 11, marginBottom: 4, color: 'var(--crit)' }}>
                  <strong>{e.tipo_registro}</strong>: esperados {e.campos_esperados} campos,
                  encontrados {e.campos_encontrados}
                </div>
              ))}
            </div>
          )}
          {result.avisos?.length > 0 && (
            <div>
              <div style={{ color: 'var(--warn)', fontWeight: 600, marginBottom: 4 }}>Avisos:</div>
              {result.avisos.map((av, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--warn)' }}>{av}</div>
              ))}
            </div>
          )}
        </OkBox>
      )}
    </div>
  );
}

// ── Nota de Correção tab ──────────────────────────────────────────────────────

function NotaCorrecaoTab() {
  const [origId,  setOrigId]  = useState('');
  const [retId,   setRetId]   = useState('');
  const [motivo,  setMotivo]  = useState('');
  const [result,  setResult]  = useState(null);
  const [busy,    setBusy]    = useState(false);
  const [err,     setErr]     = useState('');

  const criar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/fiscal/retificacao/nota-correcao', {
        escrituracao_original_id:   origId.trim(),
        escrituracao_retificada_id: retId.trim(),
        motivo: motivo.trim(),
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao criar nota de correção.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={criar}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Nova Nota de Correção</h3>
        <div style={{ marginBottom: 10 }}>
          <Label>ID Escrituração Original (UUID) *</Label>
          <input className="input" required value={origId}
            onChange={e => setOrigId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000001"
            style={{ fontFamily: 'monospace', fontSize: 12 }} />
        </div>
        <div style={{ marginBottom: 10 }}>
          <Label>ID Escrituração Retificada (UUID) *</Label>
          <input className="input" required value={retId}
            onChange={e => setRetId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000002"
            style={{ fontFamily: 'monospace', fontSize: 12 }} />
        </div>
        <div style={{ marginBottom: 14 }}>
          <Label>Motivo *</Label>
          <textarea className="input" rows={4} required maxLength={1000} value={motivo}
            onChange={e => setMotivo(e.target.value)}
            placeholder="Descreva o motivo da retificação…"
            style={{ width: '100%', fontSize: 13, resize: 'vertical' }} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Criando…' : '+ Criar Nota'}
        </button>
      </form>

      {result && (
        <OkBox>
          <div style={{ fontWeight: 600, color: 'var(--ok)', marginBottom: 8 }}>
            ✓ Nota criada {result.simulado ? '(simulado — sem DB)' : '(persistida)'}
          </div>
          <div style={{ fontSize: 12, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
            <span style={{ color: 'var(--faint)' }}>ID:</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{result.id}</span>
            <span style={{ color: 'var(--faint)' }}>Motivo:</span>
            <span>{result.motivo}</span>
          </div>
        </OkBox>
      )}
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

const TABS = [
  { id: 'comparar', label: 'Comparar Registros' },
  { id: 'layout',   label: 'Validar Layout' },
  { id: 'nota',     label: 'Nota de Correção' },
];

export default function RetificacaoScreen() {
  const [tab, setTab] = useState('comparar');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Retificação SPED</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Comparação antes/depois, validação de layout EFD e nota de correção
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

      {tab === 'comparar' && <ComparacaoTab />}
      {tab === 'layout'   && <ValidarLayoutTab />}
      {tab === 'nota'     && <NotaCorrecaoTab />}
    </div>
  );
}
