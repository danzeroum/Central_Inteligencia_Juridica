import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const ITENS_POR_PAGINA = 15;

export default function LegisScreen() {
  const toast = useToast();
  const [tema, setTema] = useState('inteligência artificial');
  const [bills, setBills] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [temaMais, setTemaMais] = useState('');
  const [hasMore, setHasMore] = useState(false);

  const consultar = async () => {
    if (!tema.trim()) return;
    setLoading(true);
    setBills(null);
    setAnalysis(null);
    setPagina(1);
    setTemaMais(tema.trim());
    try {
      const [b, a] = await Promise.allSettled([
        api.legislativeBills(tema.trim(), { pagina: 1, itens: ITENS_POR_PAGINA }),
        api.legislativeAnalysis(tema.trim()),
      ]);
      if (b.status === 'fulfilled') {
        setBills(b.value);
        const dados = b.value?.dados || [];
        // Câmara retorna 'links' com rel='next' quando há mais páginas
        const links = b.value?.links || [];
        setHasMore(links.some((l) => l.rel === 'next') || dados.length === ITENS_POR_PAGINA);
      } else {
        toast.error(`Falha ao buscar proposições: ${b.reason.message}`);
      }
      if (a.status === 'fulfilled') setAnalysis(a.value);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const carregarMais = async () => {
    const proxPag = pagina + 1;
    setLoadingMore(true);
    try {
      const res = await api.legislativeBills(temaMais, {
        pagina: proxPag,
        itens: ITENS_POR_PAGINA,
      });
      const novosDados = res?.dados || [];
      setBills((prev) => ({
        ...prev,
        dados: [...(prev?.dados || []), ...novosDados],
        links: res?.links || [],
      }));
      setPagina(proxPag);
      const links = res?.links || [];
      setHasMore(
        links.some((l) => l.rel === 'next') || novosDados.length === ITENS_POR_PAGINA
      );
    } catch (e) {
      toast.error(`Falha ao carregar mais: ${e.message}`);
    } finally {
      setLoadingMore(false);
    }
  };

  const billList = Array.isArray(bills) ? bills : bills?.dados || bills?.bills || [];
  const analysisText =
    analysis?.analise_ia ||
    analysis?.analysis ||
    (typeof analysis === 'string' ? analysis : null);
  const analysisUnavailable =
    analysisText &&
    (analysisText.includes('indisponível') || analysisText.includes('indisponivel'));

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Cenário Legislativo</div>
        <div className="screen-sub">
          Projetos de lei da Câmara dos Deputados com análise de cenário assistida por IA.
        </div>
      </div>
      <div className="card">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Tema legislativo</label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              className="input"
              value={tema}
              onChange={(e) => setTema(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && consultar()}
            />
            <button className="btn btn-primary" onClick={consultar} disabled={loading}>
              <Icon name="search" /> Consultar Câmara
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div className="loading">Consultando a Câmara e gerando análise…</div>
        </div>
      )}

      {(bills || analysis) && (
        <div className="grid2" style={{ marginTop: 16, alignItems: 'start' }}>
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                Proposições{' '}
                <span className="mono">{billList.length}</span>
              </div>
            </div>
            {billList.length === 0 && (
              <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
                Nenhuma proposição encontrada.
              </div>
            )}
            {billList.map((p, i) => (
              <div
                key={p.id || i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 0',
                  borderBottom:
                    i < billList.length - 1 ? '1px solid var(--line-2)' : 'none',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {p.siglaTipo
                      ? `${p.siglaTipo} ${p.numero}/${p.ano}`
                      : p.id || p.titulo || `Proposição ${i + 1}`}
                  </div>
                  <div className="muted" style={{ fontSize: 12.5 }}>
                    {p.ementa || p.titulo || p.t || ''}
                  </div>
                </div>
              </div>
            ))}
            {hasMore && (
              <div style={{ paddingTop: 12, textAlign: 'center' }}>
                <button
                  className="btn"
                  onClick={carregarMais}
                  disabled={loadingMore}
                  style={{ width: '100%' }}
                >
                  {loadingMore ? 'Carregando…' : `Carregar mais (página ${pagina + 1})`}
                </button>
              </div>
            )}
          </div>

          <div className="card" style={{ background: 'var(--navy-tint-2)' }}>
            <div className="card-head">
              <div className="card-title">
                <Icon
                  name="spark"
                  style={{ width: 14, height: 14, verticalAlign: '-2px', marginRight: 6 }}
                />
                Análise de cenário · IA
              </div>
              <Badge kind="navy">beta</Badge>
            </div>
            {analysisText && !analysisUnavailable ? (
              <p
                style={{
                  fontSize: 13,
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  marginBottom: 0,
                }}
              >
                {analysisText}
              </p>
            ) : (
              <div style={{ fontSize: 13 }}>
                <div className="muted" style={{ marginBottom: 8 }}>
                  Análise de IA não disponível no momento.
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Para habilitar, configure{' '}
                  <code style={{ fontFamily: 'var(--mono)' }}>OPENAI_API_KEY</code> no
                  arquivo <code style={{ fontFamily: 'var(--mono)' }}>.env</code> ou inicie
                  o serviço Ollama.
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
