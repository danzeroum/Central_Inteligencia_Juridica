import React, { useEffect, useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const DECISION_KIND = { HITL_DECISION: 'navy', TASK_COMPLETED: 'ok' };

function decisionLabel(entry) {
  const meta = entry.metadata || {};
  if (entry.decision_type === 'HITL_DECISION') {
    if (meta.modifications) return ['Modificada', 'navy'];
    return meta.approved ? ['Aprovada', 'ok'] : ['Rejeitada', 'crit'];
  }
  return [entry.decision_type, DECISION_KIND[entry.decision_type] || 'mut'];
}

export default function LedgerScreen() {
  const toast = useToast();
  const [data, setData] = useState({ entries: [], count: 0 });
  const [agentFilter, setAgentFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.ledger(agentFilter ? { agent_type: agentFilter } : {});
      setData(res);
    } catch (e) {
      toast.error(`Não foi possível carregar a trilha: ${e.message}`, { label: 'Tentar de novo', onClick: load });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [agentFilter]);

  return (
    <div className="screen">
      <div className="screen-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div className="screen-title">Trilha de Auditoria</div>
          <div className="screen-sub">Decision Ledger imutável — quem decidiu o quê, quando e sob qual regra. Base para conformidade LGPD.</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select className="select" style={{ width: 'auto' }} value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
            <option value="">Todos os agentes</option>
            <option value="HumanOperator">Operador humano</option>
            <option value="SupervisorAgent">Supervisor</option>
          </select>
          <a className="btn btn-sm" href={api.ledgerExportUrl(agentFilter ? { agent_type: agentFilter } : {})} target="_blank" rel="noreferrer">
            <Icon name="external" /> Exportar CSV
          </a>
        </div>
      </div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="tbl">
          <thead><tr><th>Timestamp</th><th>Operador</th><th>Agente</th><th>Ação</th><th>Decisão</th><th>Regra</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="loading">Carregando trilha…</td></tr>
            ) : data.entries.length === 0 ? (
              <tr><td colSpan={6} className="loading">Nenhuma decisão registrada ainda.</td></tr>
            ) : data.entries.map((e) => {
              const meta = e.metadata || {};
              const [label, kind] = decisionLabel(e);
              const action = meta.action || {};
              return (
                <tr key={e.id}>
                  <td className="mono">{e.timestamp_readable || e.timestamp}</td>
                  <td><b>{meta.operator_id || (e.agent_type === 'HumanOperator' ? '—' : 'sistema')}</b></td>
                  <td>{meta.agent || e.agent_type}</td>
                  <td>{action.label || action.type || e.decision_type}</td>
                  <td><Badge kind={kind} dot={kind === 'ok' || kind === 'crit'}>{label}</Badge></td>
                  <td className="mono faint">{meta.rule || '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
