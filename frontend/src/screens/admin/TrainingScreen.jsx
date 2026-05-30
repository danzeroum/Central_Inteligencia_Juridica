import React, { useEffect, useState } from 'react';
import { Icon, Badge, Stat, Spark } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const DEFAULT_AGENTS = [
  { name: 'supervisor_agent', label: 'Supervisor' },
  { name: 'tjsp_agent', label: 'TJSP' },
  { name: 'stf_agent', label: 'STF' },
];

function num(v, d = 0) { return typeof v === 'number' ? v : d; }

export default function TrainingScreen() {
  const toast = useToast();
  const [agents] = useState(DEFAULT_AGENTS);
  const [sel, setSel] = useState(0);
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [active, setActive] = useState(0);
  const [phase, setPhase] = useState('idle'); // idle | running | done
  const [prog, setProg] = useState(0);
  const [updatedAt, setUpdatedAt] = useState(null);
  const agent = agents[sel];

  const loadGlobal = async () => {
    try {
      const [hist, act] = await Promise.all([api.trainingHistory(20), api.trainingActive()]);
      setHistory(hist.sessions || hist.history || []);
      setActive(act.active_count ?? 0);
      setUpdatedAt(new Date());
    } catch (e) { toast.error(`Falha ao carregar treino: ${e.message}`); }
  };
  const loadStats = async (name) => {
    try { const res = await api.trainingStats(name); setStats(res.stats || res); }
    catch { setStats(null); }
  };

  useEffect(() => { loadGlobal(); /* eslint-disable-next-line */ }, []);
  useEffect(() => { setPhase('idle'); setProg(0); loadStats(agent.name); /* eslint-disable-next-line */ }, [sel]);

  // Treino: dispara assíncrono e mostra progresso animado enquanto aguarda,
  // sem travar a UI nem usar alert (resolve H1 da auditoria).
  const train = async () => {
    setPhase('running'); setProg(8);
    const ticker = setInterval(() => setProg((p) => Math.min(p + 7, 92)), 250);
    try {
      const res = await api.trainingTrain(agent.name, true);
      setProg(100); setPhase('done');
      const imp = res.improvements || res.improvement;
      toast.success(`Sessão de treino concluída para ${agent.label}.`);
      await Promise.all([loadGlobal(), loadStats(agent.name)]);
    } catch (e) {
      setPhase('idle');
      toast.error(`Falha no treino: ${e.message}`);
    } finally {
      clearInterval(ticker);
    }
  };

  const agentHistory = history.filter((s) => (s.agent_type || '').includes(agent.name) || agent.name.includes(s.agent_type || '___'));
  const sessions = num(stats?.total_sessions, agentHistory.length);

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Treinamento Contínuo</div>
        <div className="screen-sub">
          Aprendizado dos agentes a partir do feedback das decisões humanas.
          {updatedAt && <> Atualizado às {updatedAt.toLocaleTimeString('pt-BR')}.</>}
        </div>
      </div>
      <div className="grid3" style={{ marginBottom: 18 }}>
        <Stat label="Sessões no histórico" value={history.length} />
        <Stat label="Sessões ativas" value={active} />
        <Stat label="Agentes" value={agents.length} />
      </div>
      <div className="grid2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Agentes</div>
          {agents.map((ag, i) => (
            <button key={ag.name} onClick={() => setSel(i)}
              style={{ width: '100%', textAlign: 'left', border: '1px solid ' + (i === sel ? 'var(--navy)' : 'var(--line-2)'), background: i === sel ? 'var(--navy-tint-2)' : 'var(--surface)', borderRadius: 8, padding: 12, marginTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{ag.label}</div>
              </div>
              <div className="mono faint" style={{ fontSize: 11 }}>{ag.name}</div>
            </button>
          ))}
        </div>
        <div className="card">
          <div className="card-head"><div className="card-title">Performance · {agent.label}</div></div>
          <dl className="kv" style={{ marginBottom: 16, marginTop: 12 }}>
            <dt>Sessões de treino</dt><dd>{sessions}</dd>
            <dt>Feedback acumulado</dt><dd>{num(stats?.total_feedback, '—')}</dd>
            <dt>Última sessão</dt><dd>{agentHistory[0]?.start_time ? new Date(agentHistory[0].start_time).toLocaleString('pt-BR') : '—'}</dd>
          </dl>
          {phase === 'running' && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}><span className="muted">Treinando…</span><span className="mono">{prog}%</span></div>
              <div className="trust-bar"><div className="trust-fill" style={{ width: prog + '%' }} /></div>
            </div>
          )}
          {phase === 'done' && (
            <div className="ap-why" style={{ background: 'var(--ok-bg)', borderColor: '#bfe0cc', color: 'var(--ok)', marginBottom: 12 }}>
              <Icon name="check" />Sessão concluída.
            </div>
          )}
          <button className="btn btn-primary" disabled={phase === 'running'} onClick={train}>
            {phase === 'running' ? <><Icon name="refresh" /> Treinando…</> : <><Icon name="graduate" /> Treinar agora</>}
          </button>
        </div>
      </div>

      <div className="card-head" style={{ marginTop: 24, marginBottom: 12 }}><div className="card-title">Histórico de sessões</div></div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="tbl">
          <thead><tr><th>Sessão</th><th>Agente</th><th>Início</th><th>Status</th></tr></thead>
          <tbody>
            {history.length === 0 ? (
              <tr><td colSpan={4} className="loading">Nenhuma sessão registrada ainda.</td></tr>
            ) : history.map((s, i) => (
              <tr key={s.session_id || i}>
                <td className="mono">{s.session_id || `sessão_${i}`}</td>
                <td>{s.agent_type || '—'}</td>
                <td>{s.start_time ? new Date(s.start_time).toLocaleString('pt-BR') : '—'}</td>
                <td><Badge kind={s.status === 'completed' ? 'ok' : s.status === 'failed' ? 'crit' : 'warn'}>{s.status || '—'}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
