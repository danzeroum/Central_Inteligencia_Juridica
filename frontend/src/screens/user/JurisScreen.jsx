import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const TRIBUNAIS = ['STF', 'STJ', 'TJSP', 'TJMG', 'TJRS', 'TJRJ', 'TST'];

function ProcessoCard({ p }) {
  const assuntos = (p.assuntos || []).map((a) => a.nome || a).filter(Boolean);
  const ultimaMov = p.dataHoraUltimaAtualizacao
    ? new Date(p.dataHoraUltimaAtualizacao).toLocaleDateString('pt-BR')
    : null;
  return (
    <div style={{ padding: '8px 0', borderBottom: '1px solid var(--navy-tint-2)' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)', marginBottom: 3 }}>
        {p.numeroProcesso}
      </div>
      {p.classe?.nome && (
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{p.classe.nome}</div>
      )}
      {assuntos.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 2 }}>
          {assuntos.slice(0, 3).join(' · ')}
        </div>
      )}
      <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'var(--text-3)', flexWrap: 'wrap' }}>
        {p.grau && <span>Grau: {p.grau}</span>}
        {p.orgaoJulgador?.nome && <span>{p.orgaoJulgador.nome}</span>}
        {ultimaMov && <span>Últ. mov.: {ultimaMov}</span>}
      </div>
    </div>
  );
}

function TribunalResult({ tribunal, data }) {
  const isError = !!data?.error;
  const isMock = data?.source === 'simulated' || data?.fallback;
  const processos = data?.processos || [];
  const total = data?.total ?? 0;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>{tribunal}</span>
        {isError ? (
          <Badge kind="red">erro</Badge>
        ) : isMock ? (
          <Badge kind="yellow">simulado</Badge>
        ) : (
          <Badge kind="green">real · {total} encontrado{total !== 1 ? 's' : ''}</Badge>
        )}
      </div>
      {isError && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>{data.error}</div>
      )}
      {!isError && processos.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
          {isMock ? 'Sem chave DataJud configurada.' : 'Nenhum processo encontrado para este tema neste tribunal.'}
        </div>
      )}
      {processos.map((p, i) => (
        <ProcessoCard key={p.numeroProcesso || i} p={p} />
      ))}
    </div>
  );
}

export default function JurisScreen() {
  const toast = useToast();
  const [tema, setTema] = useState('dano moral por vazamento de dados (LGPD)');
  const [sel, setSel] = useState(['STF', 'TJSP']);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const _toggle = (t) => setSel((s) => (s.includes(t) ? s.filter((x) => x !== x) : s.includes(t) ? s.filter((x) => x !== t) : [...s, t]));

  const buscar = async () => {
    if (!tema.trim() || sel.length === 0) {
      toast.error('Informe um tema e ao menos um tribunal.');
      return;
    }
    setLoading(true);
    setResults(null);
    try {
      const pairs = await Promise.all(
        sel.map((t) =>
          api
            .jurisprudencia({ tribunal: t.toLowerCase(), tema: tema.trim(), size: 5 })
            .then((r) => [t, r])
            .catch((e) => [t, { error: e.message, processos: [], total: 0 }])
        )
      );
      setResults(Object.fromEntries(pairs));
    } catch (e) {
      toast.error(`Falha na busca: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const realCount = results
    ? Object.values(results).filter((r) => !r?.error && r?.source !== 'simulated').length
    : 0;

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Jurisprudência</div>
        <div className="screen-sub">
          Busque decisões e compare o entendimento entre tribunais lado a lado.
        </div>
      </div>
      <div className="card">
        <div className="field">
          <label>Tema ou palavra-chave</label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              className="input"
              value={tema}
              onChange={(e) => setTema(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && buscar()}
            />
            <button className="btn btn-primary" onClick={buscar} disabled={loading}>
              <Icon name="search" /> Buscar
            </button>
          </div>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Comparar tribunais</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {TRIBUNAIS.map((t) => (
              <button
                key={t}
                className={sel.includes(t) ? 'chip' : 'chip chip-out'}
                onClick={() =>
                  setSel((s) =>
                    s.includes(t) ? s.filter((x) => x !== t) : [...s, t]
                  )
                }
              >
                {sel.includes(t) && (
                  <Icon name="check" style={{ width: 13, height: 13 }} />
                )}
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div className="loading">Consultando DataJud para {sel.join(', ')}…</div>
        </div>
      )}

      {results && (
        <div className="card">
          <div className="card-head" style={{ marginBottom: 16 }}>
            <div className="card-title">
              <Icon
                name="compare"
                style={{ width: 15, height: 15, verticalAlign: '-2px', marginRight: 6 }}
              />
              Resultado da comparação
            </div>
            <Badge kind="navy">
              {sel.length} tribunal{sel.length !== 1 ? 'is' : ''} · {realCount} com dados reais
            </Badge>
          </div>
          {sel.map((t) => (
            <TribunalResult key={t} tribunal={t} data={results[t]} />
          ))}
        </div>
      )}
    </div>
  );
}
