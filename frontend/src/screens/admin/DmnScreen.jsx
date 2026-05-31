import React, { useEffect, useState } from 'react';
import { Icon } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

// Limiares em fração (0–1) no backend; exibidos como vírgula decimal pt-BR.
const toInput = (n) => (n != null ? n.toString().replace('.', ',') : '');
const toFloat = (s) => parseFloat(String(s).replace(',', '.'));

export default function DmnScreen() {
  const toast = useToast();
  const [cfg, setCfg] = useState(null);
  const [table, setTable] = useState([]);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const res = await api.autonomyConfig();
      setCfg(res.config);
      setTable(res.decision_table);
      setDraft({
        consensus_threshold: toInput(res.config.consensus_threshold),
        trust_full_threshold: toInput(res.config.trust_full_threshold),
        trust_supervised_threshold: toInput(res.config.trust_supervised_threshold),
      });
    } catch (e) {
      toast.error(`Falha ao carregar configuração: ${e.message}`, { label: 'Tentar de novo', onClick: load });
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    setSaving(true);
    try {
      const res = await api.updateAutonomyConfig({
        consensus_threshold: toFloat(draft.consensus_threshold),
        trust_full_threshold: toFloat(draft.trust_full_threshold),
        trust_supervised_threshold: toFloat(draft.trust_supervised_threshold),
      });
      setCfg(res.config);
      setTable(res.decision_table);
      toast.success('Regras de autonomia atualizadas.');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) return <div className="screen"><div className="loading">Carregando regras…</div></div>;

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Regras de Autonomia</div>
        <div className="screen-sub">A regra "quando um humano precisa decidir" em tabela de decisão (DMN) — editável pelo jurídico, sem tocar no código.</div>
      </div>
      <div className="card">
        <div className="card-head" style={{ marginBottom: 14 }}>
          <div className="card-title">Limiares</div>
          <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}><Icon name="check" /> Salvar</button>
        </div>
        {/* M12: inputs numéricos com faixa válida (0–1) — rejeitam texto/valores fora do intervalo. */}
        <div className="grid3">
          <div className="field" style={{ marginBottom: 0 }}><label>Limiar de consenso</label>
            <input className="input" type="number" min="0" max="1" step="0.01" value={draft.consensus_threshold} onChange={(e) => setDraft({ ...draft, consensus_threshold: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Trust → Pleno (≥)</label>
            <input className="input" type="number" min="0" max="1" step="0.01" value={draft.trust_full_threshold} onChange={(e) => setDraft({ ...draft, trust_full_threshold: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Trust → Supervisionado (≥)</label>
            <input className="input" type="number" min="0" max="1" step="0.01" value={draft.trust_supervised_threshold} onChange={(e) => setDraft({ ...draft, trust_supervised_threshold: e.target.value })} /></div>
        </div>
      </div>

      <div className="card-head" style={{ marginTop: 22, marginBottom: 12 }}>
        <div className="card-title">Decisão · Requer revisão humana? <span className="mono faint">política First</span></div>
      </div>
      <div className="dmn">
        <table>
          <thead><tr><th className="rule-n">#</th><th>Ação crítica?</th><th>Consenso</th><th>Nível de autonomia</th><th className="out">Requer HITL</th></tr></thead>
          <tbody>
            {table.map((r) => (
              <tr key={r.rule}>
                <td className="rule-n">{r.rule}</td>
                <td>{r.critical}</td>
                <td>{r.consensus}</td>
                <td>{r.autonomy}</td>
                <td className="out" style={{ color: r.requires_hitl ? 'var(--crit)' : 'var(--ok)' }}>{r.requires_hitl ? 'SIM' : 'NÃO'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card-head" style={{ marginTop: 22, marginBottom: 12 }}><div className="card-title">Subdecisão · Nível de autonomia (trust score)</div></div>
      <div className="dmn" style={{ maxWidth: 420 }}>
        <table>
          <thead><tr><th className="rule-n">#</th><th>Trust score</th><th className="out">Nível</th></tr></thead>
          <tbody>
            <tr><td className="rule-n">1</td><td>≥ {toInput(cfg.trust_full_threshold)}</td><td className="out">Pleno</td></tr>
            <tr><td className="rule-n">2</td><td>{toInput(cfg.trust_supervised_threshold)} – {toInput(cfg.trust_full_threshold)}</td><td className="out">Supervisionado</td></tr>
            <tr><td className="rule-n">3</td><td>&lt; {toInput(cfg.trust_supervised_threshold)}</td><td className="out">Restrito</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
