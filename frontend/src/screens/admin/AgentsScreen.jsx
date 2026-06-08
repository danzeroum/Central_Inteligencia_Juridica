import React, { useEffect, useState } from 'react';
import { Icon, Badge, Modal } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const LEVEL_LABEL = { full: 'Pleno', supervised: 'Supervisionado', restricted: 'Restrito' };
const toInput = (n) => (n != null ? n.toString().replace('.', ',') : '');
const toFloat = (s) => parseFloat(String(s).replace(',', '.'));

function glyph(agent) {
  const s = agent.specialization || agent.name || agent.agent_id || '?';
  return s.replace(/[^a-zA-Z]/g, '').slice(0, 2).toUpperCase() || 'Ag';
}

function AgentDetailModal({ agent, onClose, onTrustUpdated }) {
  const toast = useToast();
  const [trustDraft, setTrustDraft] = useState(toInput(agent.trust_score));
  const [saving, setSaving] = useState(false);
  const trust = Math.round((agent.trust_score ?? 0) * 100);
  const level = LEVEL_LABEL[agent.autonomy_level] || agent.autonomy_level || '—';

  const saveTrust = async () => {
    const val = toFloat(trustDraft);
    if (isNaN(val) || val < 0 || val > 1) {
      toast.error('Trust score deve ser um número entre 0 e 1.');
      return;
    }
    setSaving(true);
    try {
      const res = await api.updateAgentTrust(agent.agent_id, val);
      toast.success(`Trust score atualizado para ${Math.round(val * 100)}% (${LEVEL_LABEL[res.autonomy_level] || res.autonomy_level}).`);
      onTrustUpdated(agent.agent_id, res.trust_score, res.autonomy_level);
    } catch (e) {
      toast.error(`Falha ao atualizar trust score: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const metaKeys = agent.metadata ? Object.keys(agent.metadata) : [];

  return (
    <Modal title={agent.name} onClose={onClose}
      actions={<button className="btn" onClick={onClose}>Fechar</button>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Identificação */}
        <section>
          <div className="card-title" style={{ marginBottom: 8 }}>Identificação</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 12 }}>
            <div><span className="muted">ID</span><br /><span className="mono">{agent.agent_id}</span></div>
            <div><span className="muted">Tipo</span><br /><span className="mono">{agent.type}</span></div>
            <div><span className="muted">Versão</span><br /><span className="mono">{agent.version || '—'}</span></div>
            <div><span className="muted">Status</span><br />
              <Badge kind={agent.status === 'active' ? 'ok' : 'warn'} dot>{agent.status}</Badge>
            </div>
            <div style={{ gridColumn: '1 / -1' }}><span className="muted">Endpoint</span><br /><span className="mono faint" style={{ wordBreak: 'break-all' }}>{agent.endpoint || '—'}</span></div>
            {agent.specialization && (
              <div><span className="muted">Especialização</span><br />{agent.specialization}</div>
            )}
            {agent.created_at && (
              <div><span className="muted">Criado em</span><br /><span className="mono faint">{new Date(agent.created_at).toLocaleString('pt-BR')}</span></div>
            )}
          </div>
        </section>

        {/* Descrição */}
        {agent.description && (
          <section>
            <div className="card-title" style={{ marginBottom: 6 }}>Descrição</div>
            <p style={{ fontSize: 13, lineHeight: 1.5, margin: 0 }}>{agent.description}</p>
          </section>
        )}

        {/* Capacidades */}
        <section>
          <div className="card-title" style={{ marginBottom: 6 }}>Capacidades</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(agent.capabilities || []).length > 0
              ? (agent.capabilities || []).map((c) => <span key={c} className="badge b-ok">{c}</span>)
              : <span className="muted" style={{ fontSize: 12 }}>Nenhuma capacidade registrada</span>}
          </div>
        </section>

        {/* Ferramentas */}
        <section>
          <div className="card-title" style={{ marginBottom: 6 }}>Ferramentas</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(agent.tools || []).length > 0
              ? (agent.tools || []).map((t) => <span key={t} className="badge b-mut">{t}</span>)
              : <span className="muted" style={{ fontSize: 12 }}>Sem ferramentas registradas</span>}
          </div>
        </section>

        {/* Trust Score */}
        <section>
          <div className="card-title" style={{ marginBottom: 8 }}>Trust Score &amp; Autonomia</div>
          <div style={{ fontSize: 11.5, marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
            <span className="muted">Nível atual: <strong>{level}</strong></span>
            <span className="mono">{trust}%</span>
          </div>
          <div className="trust-bar" style={{ marginBottom: 10 }}>
            <div className="trust-fill" style={{ width: trust + '%', background: trust < 60 ? 'var(--warn)' : 'var(--navy)' }} />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <div className="field" style={{ flex: 1, marginBottom: 0 }}>
              <label>Novo trust score (0–1)</label>
              <input
                className="input"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={trustDraft}
                onChange={(e) => setTrustDraft(e.target.value)}
              />
            </div>
            <button className="btn btn-primary btn-sm" disabled={saving} onClick={saveTrust} style={{ marginBottom: 0 }}>
              <Icon name="check" /> Salvar
            </button>
          </div>
        </section>

        {/* Metadata */}
        {metaKeys.length > 0 && (
          <section>
            <div className="card-title" style={{ marginBottom: 6 }}>Metadata</div>
            <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 10, borderRadius: 6, overflowX: 'auto', maxHeight: 180, margin: 0 }}>
              {JSON.stringify(agent.metadata, null, 2)}
            </pre>
          </section>
        )}
      </div>
    </Modal>
  );
}

export default function AgentsScreen() {
  const toast = useToast();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [capFilter, setCapFilter] = useState('');
  const [detail, setDetail] = useState(null);
  const [invoke, setInvoke] = useState(null);
  const [task, setTask] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async (cap) => {
    setLoading(true);
    try {
      const res = await api.agents(cap || undefined);
      setAgents(res.agents || []);
    } catch (e) {
      toast.error(`Falha ao carregar agentes: ${e.message}`, { label: 'Tentar de novo', onClick: () => load(cap) });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const applyFilter = () => load(capFilter.trim());

  const handleTrustUpdated = (agentId, newTrust, newLevel) => {
    setAgents((prev) =>
      prev.map((a) =>
        a.agent_id === agentId ? { ...a, trust_score: newTrust, autonomy_level: newLevel } : a
      )
    );
    if (detail && detail.agent_id === agentId) {
      setDetail((d) => ({ ...d, trust_score: newTrust, autonomy_level: newLevel }));
    }
  };

  const runInvoke = async () => {
    if (!task.trim()) return;
    setBusy(true); setResult(null);
    try {
      const res = await api.agentInvoke(invoke.agent_id, task.trim());
      setResult(res);
    } catch (e) {
      toast.error(`Falha ao invocar: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="screen"><div className="loading">Carregando agentes…</div></div>;

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Agentes</div>
        <div className="screen-sub">Registro de capacidades (MCP). Cada agente tem um nível de autonomia derivado do seu trust score.</div>
      </div>

      {/* Filtro de capacidade */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, maxWidth: 420 }}>
        <input
          className="input"
          placeholder="Filtrar por capacidade (ex: task_routing)"
          value={capFilter}
          onChange={(e) => setCapFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyFilter()}
          style={{ flex: 1 }}
        />
        <button className="btn btn-sm" onClick={applyFilter}><Icon name="search" /> Filtrar</button>
        {capFilter && (
          <button className="btn btn-sm" onClick={() => { setCapFilter(''); load(); }}>
            <Icon name="x" /> Limpar
          </button>
        )}
      </div>

      {agents.length === 0 && (
        <div className="muted" style={{ textAlign: 'center', padding: '32px 0' }}>
          Nenhum agente encontrado{capFilter ? ` com a capacidade "${capFilter}"` : ''}.
        </div>
      )}

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
                  {a.version && <div className="faint" style={{ fontSize: 10 }}>v{a.version}</div>}
                </div>
                <Badge kind={a.status === 'active' ? 'ok' : 'warn'} dot>{a.status}</Badge>
              </div>

              {a.description && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                  {a.description}
                </div>
              )}

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 5 }}>
                  <span className="muted">Trust · {level}</span><span className="mono">{trust}%</span>
                </div>
                <div className="trust-bar"><div className="trust-fill" style={{ width: trust + '%', background: trust < 60 ? 'var(--warn)' : 'var(--navy)' }} /></div>
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(a.capabilities || []).map((c) => <span key={c} className="badge b-mut">{c}</span>)}
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn btn-sm" onClick={() => { setDetail(a); }}>
                  <Icon name="doc" style={{ width: 13, height: 13 }} /> Detalhes
                </button>
                <button className="btn btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => { setInvoke(a); setTask(''); setResult(null); }}>
                  <Icon name="send" style={{ width: 13, height: 13 }} /> Invocar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {detail && (
        <AgentDetailModal
          agent={detail}
          onClose={() => setDetail(null)}
          onTrustUpdated={handleTrustUpdated}
        />
      )}

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
