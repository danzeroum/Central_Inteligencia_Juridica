/**
 * DueDiligenceScreen — S-G.3
 * Due Diligência 360° por CNPJ: relatório jurídico+fiscal cruzado.
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

function Section({ title, children }) {
  return (
    <section className="card" style={{ padding: 16, marginBottom: 12 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{title}</h3>
      {children}
    </section>
  );
}

function RiskBadge({ score }) {
  const s = Number(score);
  const color = s >= 0.7 ? 'var(--crit)' : s >= 0.4 ? 'var(--warn)' : 'var(--ok)';
  const label = s >= 0.7 ? 'Alto' : s >= 0.4 ? 'Médio' : 'Baixo';
  return (
    <span style={{ color, fontWeight: 700, fontSize: 18 }}>
      {(s * 100).toFixed(0)}% <span style={{ fontSize: 12 }}>({label})</span>
    </span>
  );
}

function ReportView({ report }) {
  if (!report) return null;
  const r = report.relatorio || report;

  return (
    <div>
      {/* Cabeçalho com risk score */}
      <Section title="Identificação">
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 2 }}>Risk Score</div>
            <RiskBadge score={r.risk_score ?? r.risco ?? 0} />
          </div>
          <div style={{ flex: 1, fontSize: 12 }}>
            <div><strong>{r.razao_social || r.nome || '—'}</strong></div>
            <div style={{ color: 'var(--faint)' }}>CNPJ: {r.cnpj_masked || r.cnpj || '—'}</div>
            <div style={{ color: 'var(--faint)' }}>Situação: {r.situacao_cadastral || r.situacao || '—'}</div>
          </div>
        </div>
      </Section>

      {/* Fatores de risco */}
      {(r.fatores_risco || r.risk_factors)?.length > 0 && (
        <Section title="Fatores de Risco">
          <div style={{ fontSize: 12 }}>
            {(r.fatores_risco || r.risk_factors).map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6,
                paddingBottom: 6, borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--warn)', fontFamily: 'monospace', fontSize: 11 }}>
                  [{f.codigo || f.code || i}]
                </span>
                <span style={{ flex: 1 }}>{f.descricao || f.description}</span>
                {(f.peso || f.weight) != null && (
                  <span style={{ color: 'var(--faint)', fontSize: 11 }}>
                    peso: {f.peso || f.weight}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Partes relacionadas */}
      {(r.partes_relacionadas || r.related_parties)?.length > 0 && (
        <Section title="Partes Relacionadas">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Nome', 'Vínculo', 'Tipo', 'Risco'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '4px 8px',
                      color: 'var(--faint)', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(r.partes_relacionadas || r.related_parties).map((p, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '5px 8px' }}>{p.nome || p.name || '—'}</td>
                    <td style={{ padding: '5px 8px' }}>{p.vinculo || p.vinculo_tipo || '—'}</td>
                    <td style={{ padding: '5px 8px' }}>{p.tipo || '—'}</td>
                    <td style={{ padding: '5px 8px', color: Number(p.risco || 0) > 0.5 ? 'var(--crit)' : 'inherit' }}>
                      {p.risco != null ? `${(p.risco * 100).toFixed(0)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Recomendações */}
      {(r.recomendacoes || r.recommendations)?.length > 0 && (
        <Section title="Recomendações">
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12 }}>
            {(r.recomendacoes || r.recommendations).map((rec, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{rec}</li>
            ))}
          </ul>
        </Section>
      )}

      {/* JSON raw toggle */}
      <details style={{ fontSize: 11, marginTop: 8 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--faint)' }}>Ver JSON completo</summary>
        <pre style={{ marginTop: 8, overflowX: 'auto', fontSize: 10, color: 'var(--faint)',
          background: 'var(--surface2)', padding: 12, borderRadius: 6 }}>
          {JSON.stringify(report, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export default function DueDiligenceScreen() {
  const [cnpj,    setCnpj]    = useState('');
  const [report,  setReport]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [err,     setErr]     = useState('');

  const buscar = async (e) => {
    e.preventDefault();
    setLoading(true); setErr(''); setReport(null);
    try {
      const clean = cnpj.trim().replace(/\D/g, '');
      const data = await api.get(`/api/v1/fiscal/due-diligence/${encodeURIComponent(clean || cnpj.trim())}`);
      setReport(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao gerar relatório.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Due Diligência 360°</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Relatório jurídico-fiscal por CNPJ: situação cadastral, risco, QSA e pendências
        </div>
      </div>

      <form onSubmit={buscar} style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <input className="input" required placeholder="CNPJ (14 dígitos ou formatado)"
          value={cnpj} onChange={e => setCnpj(e.target.value)}
          style={{ flex: 1, fontFamily: 'monospace', fontSize: 14, maxWidth: 340 }} />
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Buscando…' : '🔍 Gerar Relatório'}
        </button>
      </form>

      <ErrAlert msg={err} />
      {loading && (
        <div className="card" style={{ padding: 16, opacity: 0.5, fontSize: 13 }}>
          Gerando relatório 360°…
        </div>
      )}
      <ReportView report={report} />
    </div>
  );
}
