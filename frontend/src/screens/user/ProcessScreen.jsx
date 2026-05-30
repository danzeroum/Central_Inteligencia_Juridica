import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

export default function ProcessScreen() {
  const toast = useToast();
  const [numero, setNumero] = useState('1234567-89.2024.8.26.1234');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const consultar = async () => {
    if (!numero.trim()) return;
    setLoading(true); setResult(null);
    try {
      const res = await api.submitTask(`Últimas movimentações do processo ${numero.trim()}`);
      setResult(res);
    } catch (e) { toast.error(`Falha na consulta: ${e.message}`); }
    finally { setLoading(false); }
  };

  const sr = result?.supervisor_result || result || {};
  const movements = sr.movements || sr.movimentacoes || sr.result?.movements || [];

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Consulta de Processo</div>
        <div className="screen-sub">Acompanhe a tramitação. O número é validado e o tribunal inferido automaticamente pelo classificador.</div>
      </div>
      <div className="card">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Número único do processo (CNJ)</label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input className="input" value={numero} onChange={(e) => setNumero(e.target.value)} />
            <button className="btn btn-primary" onClick={consultar} disabled={loading}><Icon name="search" /> Consultar</button>
          </div>
        </div>
      </div>

      {loading && <div className="card"><div className="loading">Consultando tribunal…</div></div>}

      {result && (
        <div className="card">
          <div className="ap-head" style={{ padding: 0, border: 'none', marginBottom: 16 }}>
            <div className="ap-agent">
              <div className="ap-icon">{(result.tribunals_used?.[0] || 'SP').slice(0, 2)}</div>
              <div><div className="ap-title">Processo {numero}</div><div className="ap-sub">{(result.tribunals_used || []).join(', ') || 'Tribunal inferido'}</div></div>
            </div>
            <Badge kind="ok" dot>Consultado</Badge>
          </div>
          {movements.length > 0 ? (
            <>
              <div className="card-title" style={{ marginBottom: 14 }}>Movimentações</div>
              <div className="timeline">
                {movements.map((m, i) => (
                  <div className={`tl done`} key={i}>
                    <div className="tl-date">{m.date || m.data || ''}</div>
                    <div className="tl-title">{m.title || m.titulo || m.descricao || 'Movimentação'}</div>
                    <div className="tl-desc">{m.description || m.desc || ''}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, overflowX: 'auto', maxHeight: 320 }}>
              {JSON.stringify(sr, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
