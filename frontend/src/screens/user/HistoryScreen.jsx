import React, { useEffect, useState } from 'react';
import { Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const STATUS = {
  concluida: ['Concluída', 'ok'],
  em_revisao_humana: ['Em revisão humana', 'warn'],
};

export default function HistoryScreen({ go }) {
  const toast = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { const res = await api.history(30); setRows(res.history || []); }
    catch (e) { toast.error(`Falha ao carregar histórico: ${e.message}`, { label: 'Tentar de novo', onClick: load }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Minhas Consultas</div>
        <div className="screen-sub">Histórico das suas interações. Consultas que geraram ações sensíveis aparecem como "em revisão humana".</div>
      </div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="tbl">
          <thead><tr><th style={{ width: 150 }}>Quando</th><th>Consulta</th><th style={{ width: 150 }}>Operação</th><th style={{ width: 170 }}>Status</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="loading">Carregando…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={4} className="loading">Nenhuma consulta registrada ainda.</td></tr>
            ) : rows.map((r, i) => {
              const [label, kind] = STATUS[r.status] || [r.status, 'mut'];
              const review = r.status === 'em_revisao_humana';
              return (
                <tr key={i} className={review ? 'rowbtn' : ''} onClick={() => review && go && go('hitl')}>
                  <td className="mono">{r.timestamp ? new Date(r.timestamp).toLocaleString('pt-BR') : '—'}</td>
                  <td><b>{r.task}</b></td>
                  <td className="mono">{r.operation}</td>
                  <td><Badge kind={kind} dot={review}>{label}</Badge></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
