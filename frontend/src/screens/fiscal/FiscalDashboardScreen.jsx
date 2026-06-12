/**
 * FiscalDashboardScreen — S-E.1
 * Dashboard de KPIs fiscais: escriturações, apurações, achados e anomalias.
 * Usa SVG puro + primitives existentes (sem dependência de biblioteca de charts).
 */

import React, { useEffect, useState, useCallback } from 'react';
import { Stat } from '../../components/primitives.jsx';
import { api } from '../../api/client.js';

// ─── helpers ────────────────────────────────────────────────────────────────

const COLORS = {
  devedor:     'var(--crit, #ef4444)',
  credor:      'var(--ok,   #22c55e)',
  equilibrado: 'var(--faint,#64748b)',
  erro:        'var(--crit, #ef4444)',
  aviso:       'var(--warn, #f59e0b)',
  informacao:  'var(--info, #3b82f6)',
};

function pct(part, total) {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

/** Barra horizontal simples com label e porcentagem */
function BarRow({ label, value, total, color = 'var(--accent)' }) {
  const w = pct(value, total);
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
        <span style={{ color: 'var(--fg)' }}>{label}</span>
        <span style={{ color: 'var(--faint)' }}>{value} ({w}%)</span>
      </div>
      <div style={{ background: 'var(--surface2, #1e293b)', borderRadius: 4, height: 8 }}>
        <div style={{ background: color, borderRadius: 4, height: 8, width: `${w}%`, transition: 'width 0.4s' }} />
      </div>
    </div>
  );
}

/** Mini donut SVG para proporções */
function Donut({ slices, size = 80 }) {
  const r = 30;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (total === 0) return <div style={{ width: size, height: size, opacity: 0.3 }}>—</div>;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {slices.map((sl, i) => {
        const frac = sl.value / total;
        const dash = frac * circ;
        const gap = circ - dash;
        const el = (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={sl.color || 'var(--accent)'}
            strokeWidth={12}
            strokeDasharray={`${dash} ${gap}`}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        );
        offset += frac * circ;
        return el;
      })}
      <circle cx={cx} cy={cy} r={r - 8} fill="var(--surface, #0f172a)" />
    </svg>
  );
}

// ─── loading / error states ──────────────────────────────────────────────────

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

// ─── sub-components ──────────────────────────────────────────────────────────

function KpiCards({ kpis }) {
  if (!kpis) return <LoadingCard />;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
      <Stat label="Escriturações" value={kpis.total_escrituracoes} />
      <Stat label="Apurações" value={kpis.total_apuracoes} />
      <Stat label="Achados" value={kpis.total_achados} />
      <Stat label="Erros" value={kpis.por_severidade?.erro || 0} delta={-1} />
      <Stat label="Avisos" value={kpis.por_severidade?.aviso || 0} />
    </div>
  );
}

function StatusDistribution({ kpis }) {
  if (!kpis) return <LoadingCard />;
  const entries = Object.entries(kpis.por_status || {});
  const total = entries.reduce((s, [, v]) => s + v, 0);
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Escriturações por Status</h3>
      {entries.length === 0 ? <EmptyState msg="Nenhuma escrituração ainda." /> :
        entries.map(([k, v]) => (
          <BarRow key={k} label={k} value={v} total={total} />
        ))}
    </section>
  );
}

function SituacaoDonut({ kpis }) {
  if (!kpis) return <LoadingCard />;
  const entries = Object.entries(kpis.por_situacao || {});
  if (entries.length === 0) return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Apurações por Situação</h3>
      <EmptyState msg="Nenhuma apuração calculada." />
    </section>
  );
  const slices = entries.map(([k, v]) => ({ label: k, value: v, color: COLORS[k] || 'var(--accent)' }));
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Apurações por Situação</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Donut slices={slices} size={88} />
        <div style={{ flex: 1 }}>
          {slices.map((sl) => (
            <div key={sl.label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: sl.color, display: 'inline-block' }} />
              <span style={{ fontSize: 12 }}>{sl.label}</span>
              <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--faint)' }}>
                {sl.value} ({pct(sl.value, total)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function AchadosChart({ dist }) {
  if (!dist) return <LoadingCard />;
  const total = dist.total || 0;
  const entries = Object.entries(dist.por_severidade || {});
  const regras = Object.entries(dist.por_regra || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Achados — Top Regras ({total} total)</h3>
      {regras.length === 0 ? <EmptyState msg="Sem achados registrados." /> : (
        <>
          {entries.map(([k, v]) => (
            <BarRow key={k} label={k} value={v} total={total} color={COLORS[k] || 'var(--accent)'} />
          ))}
          <hr style={{ borderColor: 'var(--border)', margin: '12px 0' }} />
          <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 8 }}>Por regra:</div>
          {regras.map(([k, v]) => (
            <BarRow key={k} label={k} value={v} total={total} />
          ))}
        </>
      )}
    </section>
  );
}

function AnomaliasList({ anomalias }) {
  if (!anomalias) return <LoadingCard />;
  if (anomalias.length === 0) return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Anomalias Detectadas</h3>
      <EmptyState msg="Nenhuma anomalia detectada. Pipeline limpo." />
    </section>
  );
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
        Anomalias Detectadas ({anomalias.length})
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--faint)' }}>Escrituração</th>
              <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--faint)' }}>Tipo</th>
              <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--faint)' }}>Período</th>
              <th style={{ textAlign: 'right', padding: '4px 8px', color: 'var(--faint)' }}>Divergências</th>
              <th style={{ textAlign: 'center', padding: '4px 8px', color: 'var(--faint)' }}>Severidade</th>
            </tr>
          </thead>
          <tbody>
            {anomalias.map((a) => (
              <tr key={a.escrituracao_id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                  {a.escrituracao_id.slice(0, 8)}…
                </td>
                <td style={{ padding: '6px 8px' }}>{a.tipo}</td>
                <td style={{ padding: '6px 8px', color: 'var(--faint)' }}>{a.periodo || '—'}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{a.divergencias_count}</td>
                <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                  <span style={{
                    background: COLORS[a.severidade_maxima] || 'var(--faint)',
                    color: '#fff',
                    borderRadius: 4,
                    padding: '2px 6px',
                    fontSize: 11,
                    fontWeight: 600,
                  }}>
                    {a.severidade_maxima}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HistoricoTable({ historico }) {
  if (!historico) return <LoadingCard />;
  if (historico.length === 0) return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Histórico de Apurações</h3>
      <EmptyState msg="Nenhuma apuração no período." />
    </section>
  );
  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Histórico de Apurações</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Período', 'Tributo', 'Débitos', 'Créditos', 'Saldo', 'Situação'].map((h) => (
                <th key={h} style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--faint)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {historico.map((r, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '6px 8px' }}>{r.periodo}</td>
                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{r.tributo}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', color: COLORS.devedor }}>{r.total_debitos}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', color: COLORS.credor }}>{r.total_creditos}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600 }}>{r.saldo_apurado}</td>
                <td style={{ padding: '6px 8px' }}>
                  <span style={{ color: COLORS[r.situacao] || 'inherit' }}>{r.situacao}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ─── main screen ─────────────────────────────────────────────────────────────

export default function FiscalDashboardScreen() {
  const [kpis,      setKpis]      = useState(null);
  const [dist,      setDist]      = useState(null);
  const [anomalias, setAnomalias] = useState(null);
  const [historico, setHistorico] = useState(null);
  const [error,     setError]     = useState('');
  const [loading,   setLoading]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [k, d, a, h] = await Promise.all([
        api.get('/api/v1/fiscal/analytics/kpis'),
        api.get('/api/v1/fiscal/analytics/achados/distribuicao'),
        api.get('/api/v1/fiscal/analytics/anomalias?severidade_minima=aviso'),
        api.get('/api/v1/fiscal/analytics/apuracoes/historico?limit=20'),
      ]);
      setKpis(k);
      setDist(d);
      setAnomalias(a);
      setHistorico(h);
    } catch (e) {
      setError(e?.message || 'Erro ao carregar dados de analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Analytics Fiscal</h2>
          <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
            KPIs do pipeline de escrituração e apuração tributária
          </div>
        </div>
        <button className="btn btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Atualizando…' : '↻ Atualizar'}
        </button>
      </div>

      {error && (
        <div role="alert" style={{
          background: 'var(--crit-bg, #fee2e2)', color: 'var(--crit)', borderRadius: 6,
          padding: '10px 14px', marginBottom: 16, fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* KPI cards row */}
      <div style={{ marginBottom: 16 }}>
        <KpiCards kpis={kpis} />
      </div>

      {/* Middle row: status bars + situação donut */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <StatusDistribution kpis={kpis} />
        <SituacaoDonut kpis={kpis} />
      </div>

      {/* Achados */}
      <div style={{ marginBottom: 12 }}>
        <AchadosChart dist={dist} />
      </div>

      {/* Anomalias */}
      <div style={{ marginBottom: 12 }}>
        <AnomaliasList anomalias={anomalias} />
      </div>

      {/* Histórico de apurações */}
      <HistoricoTable historico={historico} />
    </div>
  );
}
