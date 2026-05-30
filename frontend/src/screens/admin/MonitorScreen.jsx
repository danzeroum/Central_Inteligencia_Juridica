import React, { useEffect, useState } from 'react';
import { Badge, Gauge, Stat } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const CB_STATE = {
  closed: ['fechado', 'ok'],
  half_open: ['meio-aberto', 'warn'],
  open: ['aberto', 'crit'],
};

export default function MonitorScreen() {
  const toast = useToast();
  const [health, setHealth] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  const load = async () => {
    try {
      const res = await api.monitoringHealth();
      setHealth(res);
      setUpdatedAt(new Date());
    } catch (e) {
      toast.error(`Falha ao carregar monitoramento: ${e.message}`, { label: 'Tentar de novo', onClick: load });
    }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 15000); // atualização incremental, sem recarregar a tela
    return () => clearInterval(t);
    /* eslint-disable-next-line */
  }, []);

  if (!health) return <div className="screen"><div className="loading">Carregando saúde do sistema…</div></div>;

  const breakers = health.circuit_breakers || [];
  const a2a = health.a2a || {};
  const a2aHealthy = a2a.status === 'healthy' || a2a.status === 'ok' || a2a.healthy === true;

  return (
    <div className="screen">
      <div className="screen-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div className="screen-title">Monitoramento</div>
          <div className="screen-sub">Saúde do sistema, resiliência (circuit breakers) e canal entre agentes (A2A).</div>
        </div>
        {updatedAt && <div className="muted" style={{ fontSize: 12 }}>atualizado às {updatedAt.toLocaleTimeString('pt-BR')}</div>}
      </div>

      <div className="grid4" style={{ marginBottom: 16 }}>
        <Stat label="Circuit breakers" value={breakers.length} />
        <Stat label="Abertos" value={breakers.filter((b) => b.state === 'open').length} />
        <Stat label="Fila HITL" value={health.hitl_queue_depth ?? 0} />
        <Stat label="Canal A2A" value={a2aHealthy ? 'ok' : (a2a.status || '—')} />
      </div>

      <div className="grid2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>Circuit Breakers</div>
          {breakers.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Nenhum circuit breaker ativo ainda.</div>}
          {breakers.map((b) => {
            const [label, kind] = CB_STATE[b.state] || [b.state, 'mut'];
            return (
              <div className="cb-state" key={b.name}>
                <span>{b.name}{b.failure_count ? <span className="faint mono" style={{ fontSize: 11 }}> · {b.failure_count} falhas</span> : null}</span>
                <Badge kind={kind} dot>{label}</Badge>
              </div>
            );
          })}
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>Canal A2A</div>
          <div className="grid2">
            <Gauge value={a2aHealthy ? 100 : 0} label="Entrega" color={a2aHealthy ? 'var(--ok)' : 'var(--crit)'} />
            <Gauge value={Math.min(health.hitl_queue_depth ?? 0, 100)} label="Fila HITL" color="var(--warn)" />
          </div>
          <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, marginTop: 14, overflowX: 'auto' }}>
            {JSON.stringify(a2a, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
