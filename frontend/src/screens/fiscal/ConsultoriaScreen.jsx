/**
 * ConsultoriaScreen — S-G.3
 * Consultoria Tributária Assistida via RAG: parecer preliminar com citações verificáveis.
 */

import React, { useState } from 'react';
import { api } from '../../api/client.js';

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

const REGIMES = ['lucro_real', 'lucro_presumido', 'simples_nacional', 'mei'];
const PORTES  = ['mei', 'me', 'epp', 'medio', 'grande'];

function ParecerView({ parecer }) {
  if (!parecer) return null;

  return (
    <div>
      {/* Aviso legal */}
      <div style={{
        fontSize: 11, color: 'var(--faint)', padding: '8px 12px',
        background: 'var(--surface2)', borderRadius: 6, marginBottom: 16,
        borderLeft: '3px solid var(--warn)',
      }}>
        Parecer preliminar gerado por IA para apoio à análise. Não substitui consultoria
        profissional registrada — CJ-001.
      </div>

      {/* Texto do parecer */}
      {(parecer.parecer || parecer.texto) && (
        <section className="card" style={{ padding: 16, marginBottom: 12 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Parecer</h3>
          <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {parecer.parecer || parecer.texto}
          </div>
        </section>
      )}

      {/* Citações */}
      {parecer.citacoes?.length > 0 && (
        <section className="card" style={{ padding: 16, marginBottom: 12 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
            Citações ({parecer.citacoes.length})
          </h3>
          <div>
            {parecer.citacoes.map((c, i) => (
              <div key={i} style={{
                marginBottom: 10, paddingBottom: 10,
                borderBottom: i < parecer.citacoes.length - 1 ? '1px solid var(--border)' : 'none',
                fontSize: 12,
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 4 }}>
                  <span style={{
                    background: 'var(--accent-bg, #1e3a5f)', color: 'var(--accent)',
                    borderRadius: 3, padding: '1px 6px', fontSize: 11, fontWeight: 600,
                    flexShrink: 0,
                  }}>[{i + 1}]</span>
                  <span style={{ fontWeight: 600 }}>{c.fonte || c.source || '—'}</span>
                </div>
                {(c.trecho || c.texto) && (
                  <div style={{ color: 'var(--faint)', fontSize: 12, paddingLeft: 28,
                    fontStyle: 'italic', lineHeight: 1.5 }}>
                    "{c.trecho || c.texto}"
                  </div>
                )}
                {c.url && (
                  <div style={{ paddingLeft: 28, marginTop: 4, fontSize: 11 }}>
                    <a href={c.url} target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--accent)' }}>{c.url}</a>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Metadados */}
      {(parecer.regime || parecer.porte || parecer.cnae) && (
        <section className="card" style={{ padding: 16, marginBottom: 12 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Parâmetros</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 16px', fontSize: 12 }}>
            {parecer.regime && <><span style={{ color: 'var(--faint)' }}>Regime:</span><span>{parecer.regime}</span></>}
            {parecer.porte  && <><span style={{ color: 'var(--faint)' }}>Porte:</span><span>{parecer.porte}</span></>}
            {parecer.cnae   && <><span style={{ color: 'var(--faint)' }}>CNAE:</span><span>{parecer.cnae}</span></>}
          </div>
        </section>
      )}

      {/* JSON raw toggle */}
      <details style={{ fontSize: 11 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--faint)' }}>Ver JSON completo</summary>
        <pre style={{ marginTop: 8, overflowX: 'auto', fontSize: 10, color: 'var(--faint)',
          background: 'var(--surface2)', padding: 12, borderRadius: 6 }}>
          {JSON.stringify(parecer, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export default function ConsultoriaScreen() {
  const [regime,    setRegime]    = useState('lucro_real');
  const [cnae,      setCnae]      = useState('');
  const [porte,     setPorte]     = useState('epp');
  const [pergunta,  setPergunta]  = useState('');
  const [nCitacoes, setNCitacoes] = useState(3);
  const [parecer,   setParecer]   = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [err,       setErr]       = useState('');

  const consultar = async (e) => {
    e.preventDefault();
    setLoading(true); setErr(''); setParecer(null);
    try {
      const data = await api.post('/api/v1/fiscal/consultoria', {
        regime,
        cnae:       cnae.trim(),
        porte,
        pergunta:   pergunta.trim(),
        n_citacoes: Number(nCitacoes),
      });
      setParecer(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao gerar parecer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Consultoria Tributária</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Parecer preliminar assistido por IA com citações verificáveis (RAG) — S-A.2
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 20, alignItems: 'start' }}>
        <form className="card" style={{ padding: 16 }} onSubmit={consultar}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Parâmetros</h3>

          <div style={{ marginBottom: 10 }}>
            <Label>Regime tributário *</Label>
            <select className="input" value={regime} onChange={e => setRegime(e.target.value)}
              style={{ fontSize: 12 }}>
              {REGIMES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div style={{ marginBottom: 10 }}>
            <Label>CNAE *</Label>
            <input className="input" required placeholder="ex: 6201-5/01"
              value={cnae} onChange={e => setCnae(e.target.value)} style={{ fontSize: 12 }} />
          </div>

          <div style={{ marginBottom: 10 }}>
            <Label>Porte da empresa *</Label>
            <select className="input" value={porte} onChange={e => setPorte(e.target.value)}
              style={{ fontSize: 12 }}>
              {PORTES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div style={{ marginBottom: 10 }}>
            <Label>Nº de citações (1–10)</Label>
            <input className="input" type="number" min="1" max="10"
              value={nCitacoes} onChange={e => setNCitacoes(e.target.value)}
              style={{ fontSize: 12, width: 80 }} />
          </div>

          <div style={{ marginBottom: 14 }}>
            <Label>Pergunta / tema tributário *</Label>
            <textarea className="input" rows={6} required minLength={5} maxLength={2000}
              placeholder="Ex: Qual a alíquota de PIS/COFINS aplicável a serviços de desenvolvimento de software no regime de lucro real?"
              value={pergunta} onChange={e => setPergunta(e.target.value)}
              style={{ width: '100%', fontSize: 13, resize: 'vertical' }} />
            <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2, textAlign: 'right' }}>
              {pergunta.length}/2000
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}
            style={{ width: '100%', justifyContent: 'center' }}>
            {loading ? 'Gerando parecer…' : '⚡ Gerar Parecer'}
          </button>
        </form>

        <div>
          <ErrAlert msg={err} />
          {loading && (
            <div className="card" style={{ padding: 16, opacity: 0.5, fontSize: 13 }}>
              Consultando base normativa e gerando parecer…
            </div>
          )}
          {!loading && !parecer && !err && (
            <div style={{ textAlign: 'center', color: 'var(--faint)', fontSize: 13, padding: '32px 0' }}>
              Preencha os parâmetros e clique em Gerar Parecer.
            </div>
          )}
          <ParecerView parecer={parecer} />
        </div>
      </div>
    </div>
  );
}
