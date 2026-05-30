import React, { useEffect, useState } from 'react';
import { Icon, Badge, Modal } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const LEVEL_LABEL = { full: 'Pleno', supervised: 'Supervisionado', restricted: 'Restrito' };

function glyph(agent) {
  const s = agent.specialization || agent.name || agent.agent_id || '?';
  return s.replace(/[^a-zA-Z]/g, '').slice(0, 2).toUpperCase() || 'Ag';
}

export default function AgentsScreen() {
  const toast = useToast();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [invoke, setInvoke] = useState(null); // agent
  const [task, setTask] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const res = await api.agents(); setAgents(res.agents || []); }
    catch (e) { toast.error(`Falha ao carregar agentes: ${e.message}`, { label: 'Tentar de novo', onClick: load }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const runInvoke = async () => {
    if (!task.trim()) return;
    setBusy(true); setResult(null);
    try { const res = await api.agentInvoke(invoke.agent_id, task.trim()); setResult(res); }
    catch (e) { toast.error(`Falha ao invocar: ${e.message}`); }
    finally { setBusy(false); }
  };

  if (loading) return <div className="screen"><div className="loading">Carregando agentes…</div></div>;

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Agentes</div>
        <div className="screen-sub">Registro de capacidades (MCP). Cada agente tem um nível de autonomia derivado do seu trust score.</div>
      </div>
      <div className="grid3">
        {agents.map((a) => {
          const trust = Math.round((a.trust_score ?? 0) * 100);
          const level = LEVEL_LABEL[a.autonomy_level] || a.autonomy_level || '—';
          return (
            <div className="agent-card" key={a.agent_id}>
              <div className="agent-top">
                <div className="agent-glyph">{glyph(a)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{a.name}</div>
                  <div className="mono faint" style={{ fontSize: 11 }}>{a.type}</div>
                </div>
                <Badge kind={a.status === 'active' ? 'ok' : 'warn'} dot>{a.status}</Badge>
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 5 }}>
                  <span className="muted">Trust · {level}</span><span className="mono">{trust}%</span>
                </div>
                <div className="trust-bar"><div className="trust-fill" style={{ width: trust + '%', background: trust < 60 ? 'var(--warn)' : 'var(--navy)' }} /></div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(a.capabilities || []).map((c) => <span key={c} className="badge b-mut">{c}</span>)}
              </div>
              <button className="btn btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => { setInvoke(a); setTask(''); setResult(null); }}>
                <Icon name="send" style={{ width: 13, height: 13 }} /> Invocar diretamente
              </button>
            </div>
          );
        })}
      </div>

      {invoke && (
        <Modal title={`Invocar ${invoke.name}`} onClose={() => setInvoke(null)}
          actions={<>
            <button className="btn" onClick={() => setInvoke(null)}>Fechar</button>
            <button className="btn btn-primary" disabled={busy || !task.trim()} onClick={runInvoke}><Icon name="send" /> Invocar</button>
          </>}>
          <div className="field"><label>Descrição da tarefa</label>
            <textarea className="textarea" rows="3" value={task} onChange={(e) => setTask(e.target.value)} placeholder="Ex.: status do TJSP" autoFocus /></div>
          {result && (
            <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, overflowX: 'auto', maxHeight: 240 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </Modal>
      )}
    </div>
  );
}
