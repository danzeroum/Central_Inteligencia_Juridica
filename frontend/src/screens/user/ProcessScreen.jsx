import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

function fmtDate(raw) {
  if (!raw) return '—';
  // "20241009141210" → Date
  if (/^\d{14}$/.test(raw)) {
    const s = raw;
    return `${s.slice(6,8)}/${s.slice(4,6)}/${s.slice(0,4)} ${s.slice(8,10)}:${s.slice(10,12)}`;
  }
  try {
    const d = new Date(raw);
    if (isNaN(d)) return raw;
    return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
  } catch { return raw; }
}

function InfoRow({ label, value }) {
  if (!value || value === 'Não informado') return null;
  return (
    <div style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--line-2)' }}>
      <span className="muted" style={{ fontSize: 12, minWidth: 160, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

export default function ProcessScreen() {
  const toast = useToast();
  const [numero, setNumero] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const consultar = async () => {
    const n = numero.trim();
    if (!n) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.submitTask(`Últimas movimentações do processo ${n}`);
      setResult(res);
    } catch (e) {
      toast.error(`Falha na consulta: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Normaliza a estrutura de resposta
  const sr = result?.supervisor_result || result || {};
  const data = sr.data || {};
  const meta = sr.metadata || {};
  const tribunal = sr.tribunal || data.tribunal || meta.tribunal || '?';
  const isReal = meta.source === 'datajud' || meta.source === 'real_api';
  const isSimulated = meta.source === 'simulated' || meta.fallback;

  // Movimentos: podem estar em diferentes caminhos
  const rawMovimentos =
    data.movimentos ||
    sr.movimentos ||
    sr.movements ||
    sr.result?.movements ||
    [];
  const movimentos = Array.isArray(rawMovimentos) ? rawMovimentos : [];

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Consulta de Processo</div>
        <div className="screen-sub">
          Acompanhe a tramitação. O número é validado e o tribunal inferido automaticamente pelo classificador.
        </div>
      </div>

      <div className="card">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Número único do processo (CNJ)</label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              className="input"
              value={numero}
              placeholder="0000000-00.0000.0.00.0000"
              onChange={(e) => setNumero(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && consultar()}
            />
            <button className="btn btn-primary" onClick={consultar} disabled={loading}>
              <Icon name="search" /> Consultar
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div className="loading">Consultando tribunal…</div>
        </div>
      )}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Cabeçalho do processo */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                <div className="ap-icon" style={{ fontSize: 13, fontWeight: 700 }}>
                  {tribunal.replace('TJ', '').slice(0, 2)}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15, fontFamily: 'var(--mono)' }}>
                    {sr.process_number || numero}
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                    {tribunal} · {data.orgao_julgador || 'Órgão não informado'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {isReal && <Badge kind="ok">DataJud · real</Badge>}
                {isSimulated && <Badge kind="warn">simulado</Badge>}
                {data.grau && <Badge kind="navy">{data.grau}</Badge>}
              </div>
            </div>

            {/* Assunto destaque */}
            {data.assunto && data.assunto !== 'Não informado' && (
              <div style={{
                marginTop: 16,
                padding: '10px 14px',
                background: 'var(--navy-tint-2)',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
              }}>
                <span className="muted" style={{ fontWeight: 400, marginRight: 8 }}>Assunto:</span>
                {data.assunto}
              </div>
            )}
          </div>

          {/* Dados do processo */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 4 }}>Dados processuais</div>
            <InfoRow label="Classe processual" value={data.classe_processual} />
            <InfoRow label="Órgão julgador" value={data.orgao_julgador} />
            <InfoRow label="Grau" value={data.grau} />
            <InfoRow label="Situação" value={data.situacao} />
            <InfoRow label="Data de ajuizamento" value={fmtDate(data.data_ajuizamento)} />
            <InfoRow label="Última movimentação" value={fmtDate(data.ultima_movimentacao)} />
            <InfoRow label="Valor da causa" value={data.valor_causa} />
          </div>

          {/* Timeline de movimentos */}
          {movimentos.length > 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 16 }}>
                Movimentações <span className="mono muted" style={{ fontSize: 12 }}>{movimentos.length}</span>
              </div>
              <div className="timeline">
                {movimentos.map((m, i) => (
                  <div className="tl done" key={i}>
                    <div className="tl-date">{fmtDate(m.dataHora || m.date || m.data)}</div>
                    <div className="tl-title">{m.nome || m.title || m.titulo || m.descricao || 'Movimentação'}</div>
                    {m.complementosTabelados?.length > 0 && (
                      <div className="tl-desc">
                        {m.complementosTabelados.map((c) => c.nome).join(' · ')}
                      </div>
                    )}
                    {(m.description || m.desc) && (
                      <div className="tl-desc">{m.description || m.desc}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sem movimentos */}
          {movimentos.length === 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 8 }}>Movimentações</div>
              <div className="muted" style={{ fontSize: 13 }}>
                Nenhuma movimentação disponível nesta consulta.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
