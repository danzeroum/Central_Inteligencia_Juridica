import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const TRIBUNAIS = ['STF', 'STJ', 'TJSP', 'TJMG', 'TJRS', 'TJRJ', 'TST'];

export default function JurisScreen() {
  const toast = useToast();
  const [tema, setTema] = useState('dano moral por vazamento de dados (LGPD)');
  const [sel, setSel] = useState(['STF', 'TJSP']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const toggle = (t) => setSel((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]));

  const buscar = async () => {
    if (!tema.trim() || sel.length === 0) { toast.error('Informe um tema e ao menos um tribunal.'); return; }
    setLoading(true); setResult(null);
    try {
      const res = await api.submitTask(`Comparar jurisprudência sobre ${tema.trim()} em ${sel.join(', ')}`);
      setResult(res);
    } catch (e) { toast.error(`Falha na busca: ${e.message}`); }
    finally { setLoading(false); }
  };

  const sr = result?.supervisor_result || result || {};

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Jurisprudência</div>
        <div className="screen-sub">Busque decisões e compare o entendimento entre tribunais lado a lado.</div>
      </div>
      <div className="card">
        <div className="field">
          <label>Tema ou palavra-chave</label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input className="input" value={tema} onChange={(e) => setTema(e.target.value)} />
            <button className="btn btn-primary" onClick={buscar} disabled={loading}><Icon name="search" /> Buscar</button>
          </div>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Comparar tribunais</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {TRIBUNAIS.map((t) => (
              <button key={t} className={sel.includes(t) ? 'chip' : 'chip chip-out'} onClick={() => toggle(t)}>
                {sel.includes(t) && <Icon name="check" style={{ width: 13, height: 13 }} />}{t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && <div className="card"><div className="loading">Consultando agentes dos tribunais…</div></div>}

      {result && (
        <div className="card">
          <div className="card-head" style={{ marginBottom: 12 }}>
            <div className="card-title"><Icon name="compare" style={{ width: 15, height: 15, verticalAlign: '-2px', marginRight: 6 }} />Resultado da comparação</div>
            <Badge kind="navy">{(result.tribunals_used || sel).length} tribunais</Badge>
          </div>
          <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, overflowX: 'auto', maxHeight: 360 }}>
            {JSON.stringify(sr, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
