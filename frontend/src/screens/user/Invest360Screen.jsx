import React, { useState, useEffect, useRef } from 'react';
import { Icon, Badge, Drawer } from '../../components/primitives.jsx';
import { api } from '../../api/client.js';

// ── Metadados das fontes ────────────────────────────────────────────────────
const SOURCES_META = {
  datajud:       { name: 'CNJ DataJud',          desc: 'Processos judiciais',           zone: 'pública',  icon: 'scale'    },
  djen:          { name: 'DJEN / Comunica PJe',  desc: 'Publicações oficiais',          zone: 'pública',  icon: 'doc'      },
  receita_cnpj:  { name: 'Receita Federal',       desc: 'Cadastro de empresa · QSA',    zone: 'pública',  icon: 'building' },
  tse:           { name: 'TSE Dados Abertos',     desc: 'Candidaturas eleitorais',      zone: 'pública',  icon: 'law'      },
  crc_protestos: { name: 'CRC Protestos',         desc: 'Protestos em cartório',        zone: 'restrita', icon: 'alert'    },
  cadin:         { name: 'CADIN',                 desc: 'Pendências com órgãos públicos', zone: 'restrita', icon: 'ledger'  },
  onr_imoveis:   { name: 'ONR Imóveis',           desc: 'Registro de imóveis (SREI)',   zone: 'restrita', icon: 'home'     },
};

const SOURCE_ORDER = ['datajud', 'djen', 'receita_cnpj', 'tse', 'crc_protestos', 'cadin', 'onr_imoveis'];

const DIM_LABELS = { juridico: 'Jurídico', fiscal: 'Fiscal', patrimonial: 'Patrimonial', societario: 'Societário' };

const LOADING_STEPS = [
  { source: 'datajud',       t: 600  },
  { source: 'receita_cnpj',  t: 1150 },
  { source: 'tse',           t: 1600 },
  { source: 'crc_protestos', t: 2000 },
  { source: 'cadin',         t: 2350 },
  { source: 'onr_imoveis',   t: 2700 },
  { source: 'djen',          t: 3400 },
];

const SUGGESTS = [
  { q: '11.444.777/0001-61', hint: 'CNPJ · empresa' },
  { q: '123.456.789-09',     hint: 'CPF · pessoa física' },
  { q: '1023456-78.2024.8.26.0100', hint: 'nº CNJ' },
  { q: 'Comercial Aurora Ltda',     hint: 'nome' },
];

// ── Helpers ────────────────────────────────────────────────────────────────
function riskBand(score) {
  if (score >= 70) return { key: 'crit', label: 'Risco alto',   icon: 'alert' };
  if (score >= 40) return { key: 'warn', label: 'Risco médio',  icon: 'info'  };
  return               { key: 'ok',   label: 'Risco baixo',  icon: 'check' };
}

function detectIdentifier(q) {
  const s = q.trim();
  if (!s) return null;
  const digits = s.replace(/\D/g, '');
  const numericish = /^[\d.\-/\s]+$/.test(s);
  if (numericish) {
    if (digits.length === 11) return { type: 'CPF',             label: 'CPF detectado',                       ok: true  };
    if (digits.length === 14) return { type: 'CNPJ',            label: 'CNPJ detectado',                      ok: true  };
    if (digits.length === 20) return { type: 'NUMERO_PROCESSO',  label: 'Nº de processo (CNJ) detectado',     ok: true  };
    return                           { type: null,               label: `identificador incompleto · ${digits.length} dígitos`, ok: false };
  }
  if (s.length >= 5) return { type: 'NOME', label: 'Busca por nome — sujeita a homônimos', ok: true  };
  return                    { type: null,   label: 'continue digitando…',                  ok: false };
}

function detectItemKind(item) {
  if (!item || typeof item !== 'object') return item;
  if (item.kind) return item;
  if (item.numero && item.classe)               return { ...item, kind: 'processo'   };
  // DJEN Publicacao: detecta por campos exclusivos (data_disponibilizacao / destinatario)
  // pois texto pode ser null na API pública
  if ('data_disponibilizacao' in item || item.destinatario != null)
                                                return { ...item, kind: 'publicacao' };
  if (item.texto  && item.tribunal && !item.classe) return { ...item, kind: 'publicacao' };
  if (item.cartorio && (item.cedente || item.credor)) return { ...item, kind: 'protesto'   };
  if (item.orgao  && item.tipo_divida)          return { ...item, kind: 'cadin'      };
  if (item.matricula)                           return { ...item, kind: 'imovel'     };
  if (item.razao_social)                        return { ...item, kind: 'empresa'    };
  return { ...item, kind: 'unknown' };
}

function normalizeGqlReport(raw) {
  const r = raw?.data?.intelligence || raw?.intelligence || raw;
  if (!r) throw new Error('Resposta inesperada da API.');

  const now = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

  const resultsDict = {};
  for (const res of r.results || []) {
    const items = Array.isArray(res.items) ? res.items.map(detectItemKind) : [];
    resultsDict[res.source] = {
      status:          res.status,
      data_mode:       res.dataMode || 'real',
      latency_ms:      res.latencyMs || 0,
      total_available: res.totalAvailable || 0,
      items,
      error:           res.error || null,
      last_attempt:    res.error ? `hoje, ${now}` : null,
      skip_reason:     res.status === 'skipped' ? 'Não aplicável para este tipo de identificador.' : null,
    };
  }
  for (const src of SOURCE_ORDER) {
    if (!resultsDict[src]) {
      resultsDict[src] = {
        status: 'skipped', data_mode: 'real', latency_ms: 0,
        total_available: 0, items: [], error: null, last_attempt: null,
        skip_reason: 'Fonte não consultada.',
      };
    }
  }

  const hitlStatus = r.hitlStatus || 'not_required';
  return {
    query_id:           r.queryId || 'q_unknown',
    ledger_hash:        `sha256:${(r.queryId || 'xxxx').slice(-8)}…`,
    consulted_at:       `hoje, ${now}`,
    identifier_masked:  r.identifierMasked,
    identifier_type:    r.identifierType,
    subject_name:       r.identifierMasked,
    risk_score:         r.riskScore || 0,
    risk_dimensions:    (r.riskDimensions || []).map(d => ({ name: d.name, score: d.score })),
    risk_factors:       (r.riskFactors || []).map(f => ({
      code: f.code, description: f.description, weight: f.weight, source: f.source, dimension: f.dimension,
    })),
    recommendations:    r.recommendations || [],
    summary:            r.summary || '',
    hitl_status:        hitlStatus,
    hitl:               hitlStatus !== 'not_required' ? {
      protocol: `REV-${(r.queryId || 'unknown').slice(-8)}`,
      queued_at: now, eta: '~8 min',
      reviewer: null, decided_at: null, rejection_reason: null,
    } : null,
    results:            resultsDict,
    related_parties:    (r.relatedParties || []).map(p => ({
      nome: p.nome, vinculo: p.vinculo, tipo: p.tipo || 'PF',
      identificador_mascarado: '***.**.***.***', data_entrada: null,
      fonte: p.fonte, total_ocorrencias: p.totalOcorrencias || 0,
      homonimo_possivel: p.homonimoPossivel || false,
      resumo: p.resumo || '', ocorrencias: [],
    })),
  };
}

// ── SVG helpers para o gauge ───────────────────────────────────────────────
function polar(f, r, cx = 100, cy = 100) {
  const a = Math.PI * (1 - f);
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}
function arcPath(f1, f2, r) {
  const [x1, y1] = polar(f1, r);
  const [x2, y2] = polar(f2, r);
  return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
}

// ── Componentes de Score ───────────────────────────────────────────────────
function GaugeRisco({ score }) {
  const band = riskBand(score);
  const [tx, ty]   = polar(0.70, 73);
  const [tx2, ty2] = polar(0.70, 95);
  const ariaLabel = `Score de risco ${score} de 100 — ${band.label}. Faixas: 0 a 39 baixo, 40 a 69 médio, 70 a 100 alto. Revisão humana obrigatória a partir de 70.`;
  return (
    <div className="gauge-risco" role="img" aria-label={ariaLabel}>
      <svg viewBox="0 0 200 118">
        <path d={arcPath(0, 0.39, 82)} fill="none" stroke="var(--ok-bg)"   strokeWidth="13" />
        <path d={arcPath(0.40, 0.69, 82)} fill="none" stroke="var(--warn-bg)" strokeWidth="13" />
        <path d={arcPath(0.70, 1, 82)} fill="none" stroke="var(--crit-bg)" strokeWidth="13" />
        <path d={arcPath(0, Math.max(score / 100, 0.015), 82)} fill="none"
          stroke={`var(--${band.key})`} strokeWidth="13" strokeLinecap="round" />
        <line x1={tx} y1={ty} x2={tx2} y2={ty2}
          stroke="var(--ink-2)" strokeWidth="1.5" strokeDasharray="3 2" />
        <text x="100" y="84" textAnchor="middle" className="g-num"
          fontSize="44" fill="var(--ink)" fontFamily="var(--mono)" fontWeight="600">{score}</text>
        <text x="100" y="103" textAnchor="middle" fontSize="11" fill="var(--faint)" fontFamily="var(--mono)">/ 100</text>
      </svg>
      <div>
        <span className="gauge-band" style={{ background: `var(--${band.key}-bg)`, color: `var(--${band.key})` }}>
          <Icon name={band.icon} /> {band.label}
        </span>
      </div>
      <div className="gauge-scale">
        <span>0</span><span>baixo · 39</span><span>médio · 69</span><span>100</span>
      </div>
      <div className="gauge-hint">Score ≥ 70 exige revisão humana (HITL)</div>
    </div>
  );
}

function DimBars({ dimensions }) {
  return (
    <div className="dim-list" role="list" aria-label="Score por dimensão de risco">
      {dimensions.map((d) => {
        const band = riskBand(d.score);
        return (
          <div className="dim-row" role="listitem" key={d.name}>
            <span className="dim-name">{DIM_LABELS[d.name] || d.name}</span>
            <div className="dim-bar" aria-hidden="true">
              <div className="dim-fill"
                style={{ width: `${Math.max(d.score, 1.5)}%`, background: `var(--${band.key})` }} />
            </div>
            <span className="dim-val"><b>{d.score}</b> /100</span>
          </div>
        );
      })}
    </div>
  );
}

function FactorChips({ factors }) {
  return (
    <div className="factor-chips" aria-label="Fatores de risco identificados">
      {factors.map((f) => {
        const dimBand = f.weight >= 25 ? 'crit' : f.weight >= 15 ? 'warn' : 'ok';
        const src = SOURCES_META[f.source];
        return (
          <span className="factor-chip" key={f.code}
            title={`Fonte: ${src ? src.name : f.source} · dimensão ${DIM_LABELS[f.dimension] || f.dimension}`}>
            {f.description}
            <span className="fw"
              style={{ background: `var(--${dimBand}-bg)`, color: `var(--${dimBand})` }}>
              peso {f.weight}
            </span>
          </span>
        );
      })}
    </div>
  );
}

// ── ItemRow + Drawer de detalhe ────────────────────────────────────────────
function itemTitle(it) {
  switch (it.kind) {
    case 'processo':   return it.numero;
    case 'publicacao': return `${it.tipo || 'Publicação'} · ${it.data_disponibilizacao || it.data || ''}`;
    case 'protesto':   return `${it.valor || ''} · ${it.tipo || 'Protesto'}`;
    case 'cadin':      return `${it.valor || ''} · ${it.tipo_divida || it.tipo || 'CADIN'}`;
    case 'imovel':     return `Matrícula ${it.matricula}`;
    case 'empresa':    return it.razao_social;
    default:           return JSON.stringify(it).slice(0, 60);
  }
}
function itemMeta(it) {
  switch (it.kind) {
    case 'processo':   return `${it.classe || ''} · ${it.tribunal || ''} ${it.grau || ''} · ${it.ultima || ''}`;
    case 'publicacao': return `${it.tribunal || ''} · ${(it.texto || it.destinatario || '').slice(0, 80)}`;
    case 'protesto':   return `${it.credor || it.cedente || ''} · ${it.cartorio || ''}`;
    case 'cadin':      return it.orgao || '';
    case 'imovel':     return `${it.tipo || ''} · ${it.municipio || ''} · ${it.area || ''}`;
    case 'empresa':    return `${it.situacao_cadastral || ''} · ${it.cnae || ''}`;
    default:           return '';
  }
}

function drawerRows(it) {
  switch (it.kind) {
    case 'processo':   return [['Número',      it.numero], ['Tribunal',    `${it.tribunal || ''} · ${it.grau || ''}`], ['Órgão',       it.orgao], ['Classe',      it.classe], ['Ajuizamento', it.data], ['Movimentações', it.movs != null ? String(it.movs) : null], ['Última',      it.ultima]];
    case 'publicacao': return [['Tribunal',    it.tribunal], ['Data',        it.data_disponibilizacao || it.data], ['Tipo',        it.tipo], ['Destinatário', it.destinatario], ['Teor',        it.texto]];
    case 'protesto':   return [['Situação',    it.situacao], ['Valor',       it.valor], ['Título',      it.tipo], ['Credor',      it.credor || it.cedente], ['Cartório',    it.cartorio], ['Data',        it.data]];
    case 'cadin':      return [['Situação',    it.situacao], ['Órgão credor', it.orgao], ['Tipo',        it.tipo_divida || it.tipo], ['Valor',       it.valor], ['Inscrição',   it.data_inscricao || it.data]];
    case 'imovel':     return [['Matrícula',   it.matricula], ['Cartório',    it.cartorio], ['Tipo',        it.tipo], ['Município',   it.municipio], ['Área',        it.area], ['Registro',    it.data]];
    case 'empresa':    return [['Razão social', it.razao_social], ['Situação',    it.situacao_cadastral], ['Abertura',    it.data_abertura], ['Capital',     it.capital_social], ['CNAE',        it.cnae], ['Município',   it.municipio ? `${it.municipio} · ${it.uf || ''}` : null]];
    default:           return Object.entries(it).filter(([k]) => k !== 'kind').map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)]);
  }
}

function ItemDrawer({ item, dataMode, onClose }) {
  const title = item.kind === 'processo' ? (item.classe || 'Processo')
    : item.kind === 'protesto' ? 'Protesto em cartório'
    : item.kind === 'cadin'    ? 'Pendência CADIN'
    : item.kind === 'imovel'   ? item.tipo || 'Imóvel'
    : item.kind === 'empresa'  ? item.razao_social
    : item.kind === 'publicacao' ? `${item.tipo || 'Publicação'} · DJEN / Comunica PJe`
    : 'Detalhe';
  const sub = item.kind === 'processo' ? item.numero
    : item.kind === 'imovel' ? `Matrícula ${item.matricula}`
    : null;
  const rows = drawerRows(item);
  return (
    <Drawer title={title} sub={sub} onClose={onClose}
      footer={<button className="btn" style={{ flex: 1, justifyContent: 'center' }} onClick={onClose}><Icon name="x" /> Fechar</button>}>
      {dataMode === 'mock' && (
        <div className="hitl-gate pending" style={{ marginBottom: 16, padding: '10px 13px' }}>
          <div className="hg-head">
            <Icon name="info" />
            <span><b>Dados simulados.</b> Esta fonte opera em modo de demonstração — não use este item como evidência real.</span>
          </div>
        </div>
      )}
      <dl className="kv">
        {rows.filter(([, v]) => v != null && v !== '').map(([k, v]) => (
          <React.Fragment key={k}><dt>{k}</dt><dd>{v}</dd></React.Fragment>
        ))}
      </dl>
      {item.kind === 'processo' && (
        <button className="btn" style={{ marginTop: 18 }}
          onClick={() => {}}>
          <Icon name="external" /> Abrir na consulta processual
        </button>
      )}
    </Drawer>
  );
}

function ItemRow({ item, onOpen }) {
  return (
    <button className="item-row" onClick={() => onOpen(item)}>
      <div className="ir-main">
        <div className="ir-id">{itemTitle(item)}</div>
        <div className="ir-meta">{itemMeta(item)}</div>
      </div>
      <Icon name="chevron" />
    </button>
  );
}

// ── FonteCard ──────────────────────────────────────────────────────────────
function FonteCard({ srcKey, result, defaultOpen, onOpenItem }) {
  const meta = SOURCES_META[srcKey] || { name: srcKey, desc: '', zone: '', icon: 'doc' };
  const [open, setOpen] = useState(!!defaultOpen);
  const [retrying, setRetrying] = useState(false);
  const [attempt, setAttempt] = useState(result.last_attempt);

  useEffect(() => { setOpen(!!defaultOpen); }, [defaultOpen]);
  useEffect(() => { setAttempt(result.last_attempt); }, [result.last_attempt]);

  const failed  = result.status === 'failed';
  const skipped = result.status === 'skipped';
  const n = result.items.length;

  const retry = () => {
    setRetrying(true);
    setTimeout(() => { setRetrying(false); setAttempt('agora mesmo'); }, 1400);
  };

  return (
    <article className={`fonte-card${failed ? ' failed' : ''}${skipped ? ' skipped' : ''}`}>
      <button className="fonte-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <div className="fonte-glyph"><Icon name={meta.icon} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="fonte-tit">
            {meta.name}
            {result.data_mode === 'mock'
              ? <Badge kind="warn" icon="info" title="Fonte em modo simulado — os itens abaixo não são dados reais."><span className="badge-modo">DADOS SIMULADOS</span></Badge>
              : <Badge kind="mut" title="Fonte consultada em modo real."><span className="badge-modo">REAL</span></Badge>}
            {failed  && <Badge kind="crit" dot><span className="badge-modo">INDISPONÍVEL</span></Badge>}
            {skipped && <Badge kind="mut"><span className="badge-modo">PULADA</span></Badge>}
          </div>
          <div className="fonte-sub">
            <span>{meta.desc}</span>
            {meta.zone && <><span className="sep" /><span>zona {meta.zone}</span></>}
            {!skipped && !failed && result.latency_ms > 0 && (
              <><span className="sep" /><span className="mono">{result.latency_ms} ms</span></>
            )}
          </div>
        </div>
        <div className="fonte-right">
          {!failed && !skipped && (
            <span className="fonte-count">{n === 0 ? 'nenhum item' : `${result.total_available} ${result.total_available === 1 ? 'item' : 'itens'}`}</span>
          )}
          <Icon name="chevron" className={`fonte-chev${open ? ' open' : ''}`} />
        </div>
      </button>

      {open && (
        <div className="fonte-body">
          {failed && (
            <div className="fonte-error" role="alert">
              <Icon name="alert" />
              <div>
                <b>{result.error}</b>
                {attempt && <div className="mono" style={{ fontSize: 11, marginTop: 3, opacity: .8 }}>última tentativa: {attempt}</div>}
              </div>
              <button className="btn btn-sm" onClick={retry} disabled={retrying}>
                <Icon name="refresh" /> {retrying ? 'Tentando…' : 'Tentar novamente'}
              </button>
            </div>
          )}
          {skipped && (
            <div className="fonte-skip">{result.skip_reason || 'Não aplicável para este identificador.'}</div>
          )}
          {!failed && !skipped && n === 0 && (
            <div className="fonte-zero">
              <Icon name="check" /> Nenhuma ocorrência localizada para o identificador consultado.
            </div>
          )}
          {!failed && !skipped && result.items.map((it, i) => (
            <ItemRow key={i} item={it} onOpen={(item) => onOpenItem(item, result.data_mode)} />
          ))}
        </div>
      )}
    </article>
  );
}

// ── HitlGate ───────────────────────────────────────────────────────────────
function HitlSteps({ status }) {
  const steps = [
    { id: 'done',   label: 'Consultado',        icon: 'check',  state: 'done' },
    { id: 'review', label: 'Em revisão humana', icon: 'user',   state: status === 'pending' ? 'now' : 'done' },
    status === 'rejected'
      ? { id: 'end', label: 'Liberação negada', icon: 'x',      state: 'done'  }
      : { id: 'end', label: 'Liberado',         icon: 'unlock', state: status === 'approved' ? 'done' : 'idle' },
  ];
  return (
    <div className="hitl-steps" role="list" aria-label="Etapas da revisão humana">
      {steps.map((s, i) => (
        <React.Fragment key={s.id}>
          {i > 0 && <span className="hitl-conn" aria-hidden="true" />}
          <span className={`hitl-step ${s.state}`} role="listitem">
            <span className="hs-dot">
              {s.state !== 'idle' && <Icon name={s.state === 'now' ? 'clock' : s.icon} />}
            </span>
            {s.label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

function HitlGate({ report }) {
  const st = report.hitl_status;
  if (st === 'not_required' || !report.hitl) return null;
  const h = report.hitl;
  return (
    <div className={`hitl-gate ${st}`} role="status">
      <div className="hg-head">
        <Icon name={st === 'pending' ? 'clock' : st === 'approved' ? 'check' : 'x'} />
        <div>
          {st === 'pending' && (
            <span><b>Análise aguardando revisão humana.</b> O score {report.risk_score} atingiu o limiar de 70. Um operador validará as evidências antes de liberar as recomendações — estimativa {h.eta}. O score e as evidências já estão disponíveis.</span>
          )}
          {st === 'approved' && (
            <span><b>Análise revisada e liberada.</b>{h.reviewer ? ` Evidências validadas por ${h.reviewer}` : ''}{h.decided_at ? ` às ${h.decided_at}` : ''}. As recomendações abaixo estão liberadas.</span>
          )}
          {st === 'rejected' && (
            <span><b>Liberação negada pelo revisor.</b>{h.rejection_reason ? ` ${h.rejection_reason}` : ''}</span>
          )}
        </div>
      </div>
      <HitlSteps status={st} />
      <div className="hg-meta">protocolo {h.protocol} · enviado à fila às {h.queued_at}</div>
    </div>
  );
}

// ── QsaCard ────────────────────────────────────────────────────────────────
function initials(nome) {
  return nome.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

function QsaCard({ report, onOpenItem }) {
  const [openIdx, setOpenIdx] = useState(-1);
  const parties = report.related_parties || [];
  if (!parties.length) return null;
  return (
    <section className="card" aria-label="Quadro societário expandido">
      <div className="card-head">
        <div>
          <div className="card-title">Quadro societário (QSA) · expansão automática</div>
          <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
            Sócios cruzados contra processos e publicações · profundidade 1 · limite 5 sócios
          </div>
        </div>
        <Badge kind="navy">{parties.length} {parties.length === 1 ? 'sócio' : 'sócios'}</Badge>
      </div>
      <div style={{ marginTop: 8 }}>
        {parties.map((s, i) => (
          <div className="qsa-row" key={s.nome + i}>
            <button className="qsa-head" aria-expanded={openIdx === i}
              onClick={() => setOpenIdx(openIdx === i ? -1 : i)}>
              <div className={`qsa-glyph${s.tipo === 'PJ' ? ' pj' : ''}`}>
                {s.tipo === 'PJ' ? <Icon name="building" style={{ width: 16, height: 16 }} /> : initials(s.nome)}
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="qsa-name">
                  {s.nome}
                  <Badge kind="mut">{s.tipo}</Badge>
                  {s.homonimo_possivel && (
                    <Badge kind="warn" icon="alert"
                      title="A busca foi feita por nome — as ocorrências podem pertencer a outra pessoa com o mesmo nome.">
                      possível homônimo
                    </Badge>
                  )}
                </div>
                <div className="qsa-meta">
                  {s.vinculo}
                  {s.identificador_mascarado ? ` · ${s.identificador_mascarado}` : ''}
                  {s.data_entrada ? ` · desde ${s.data_entrada}` : ''}
                </div>
              </div>
              <div className="qsa-occ">
                {s.total_ocorrencias > 0
                  ? <Badge kind="crit" dot>{s.total_ocorrencias} {s.total_ocorrencias === 1 ? 'processo' : 'processos'}</Badge>
                  : <Badge kind="ok" icon="check">sem ocorrências</Badge>}
                <Icon name="chevron" className={`fonte-chev${openIdx === i ? ' open' : ''}`} />
              </div>
            </button>
            {openIdx === i && (
              <div className="qsa-body">
                {s.resumo && <div className="qsa-resumo">{s.resumo}</div>}
                {(s.ocorrencias || []).map((o, j) => (
                  <ItemRow key={j} item={o} onOpen={(item) => onOpenItem(item, 'real')} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Report360 (estado sucesso) ─────────────────────────────────────────────
function Report360({ report, depth, setDepth, onNew }) {
  const [drawer, setDrawer] = useState(null);
  const locked   = report.hitl_status === 'pending';
  const rejected = report.hitl_status === 'rejected';
  const failedSources = SOURCE_ORDER.filter((k) => report.results[k]?.status === 'failed');

  return (
    <React.Fragment>
      <HitlGate report={report} />

      {/* Score + resumo */}
      <section className="card" aria-label="Score de risco">
        <div className="card-head" style={{ marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {report.subject_name}
              <Badge kind="navy">{report.identifier_type}</Badge>
              <span className="mono faint" style={{ fontSize: 12 }}>{report.identifier_masked}</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 3 }}>consultado {report.consulted_at}</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="seg" role="group" aria-label="Profundidade do relatório">
              <button className={depth === 'executiva' ? 'on' : ''} onClick={() => setDepth('executiva')}>Executiva</button>
              <button className={depth === 'analitica' ? 'on' : ''} onClick={() => setDepth('analitica')}>Analítica</button>
            </div>
            <button className="btn btn-sm" onClick={onNew}><Icon name="plus" /> Nova consulta</button>
          </div>
        </div>
        <div className="risk-head">
          <GaugeRisco score={report.risk_score} />
          <div>
            {report.summary && <p className="exec-summary">{report.summary}</p>}
            <DimBars dimensions={report.risk_dimensions} />
            {report.risk_factors.length > 0 && <FactorChips factors={report.risk_factors} />}
          </div>
        </div>
      </section>

      {/* Recomendações */}
      <section className="card" aria-label="Recomendações">
        <div className="card-head">
          <div className="card-title">Recomendações</div>
          {locked   && <Badge kind="warn" icon="lock">aguardando revisão</Badge>}
          {report.hitl_status === 'approved' && <Badge kind="ok" icon="check">revisado</Badge>}
        </div>
        <div style={{ marginTop: 12 }}>
          {locked && (
            <div className="rec-locked">
              <Icon name="lock" />
              <div>As recomendações ficam retidas até a revisão humana — evitamos orientar decisões com base em evidências ainda não validadas. O score e as evidências acima já são definitivos: calculados por regras determinísticas.</div>
            </div>
          )}
          {rejected && (
            <div className="rec-locked" style={{ borderColor: 'var(--crit)', color: 'var(--crit)', background: 'var(--crit-bg)' }}>
              <Icon name="x" />
              <div>
                O revisor negou a liberação deste relatório.{report.hitl?.rejection_reason ? ` ${report.hitl.rejection_reason}` : ''}
                <div style={{ marginTop: 10 }}>
                  <button className="btn btn-sm" onClick={onNew}><Icon name="refresh" /> Refazer consulta</button>
                </div>
              </div>
            </div>
          )}
          {!locked && !rejected && report.recommendations.length > 0 && (
            <ul className="rec-list">
              {report.recommendations.map((r, i) => <li key={i}><Icon name="check" />{r}</li>)}
            </ul>
          )}
          {!locked && !rejected && report.recommendations.length === 0 && (
            <p style={{ color: 'var(--faint)', fontSize: 13 }}>Nenhuma recomendação específica para este perfil de risco.</p>
          )}
        </div>
      </section>

      {/* Evidências por fonte */}
      <div className="card-head" style={{ margin: '20px 2px 10px' }}>
        <div className="card-title" style={{ fontSize: 15 }}>Evidências por fonte</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Badge kind="mut">{SOURCE_ORDER.length} fontes</Badge>
          {failedSources.length > 0 && <Badge kind="crit" dot>{failedSources.length} indisponível</Badge>}
        </div>
      </div>
      <div className="fontes-grid">
        {SOURCE_ORDER.map((k) => (
          <FonteCard
            key={k + depth}
            srcKey={k}
            result={report.results[k]}
            defaultOpen={depth === 'analitica'}
            onOpenItem={(item, mode) => setDrawer({ item, mode })}
          />
        ))}
      </div>

      {/* QSA */}
      <div style={{ marginTop: 14 }}>
        <QsaCard report={report} onOpenItem={(item, mode) => setDrawer({ item, mode })} />
      </div>

      {/* Rodapé de auditoria */}
      <div className="audit-foot" style={{ marginTop: 18 }}>
        <span>{report.query_id}</span>
        <span className="sep" /><span>{report.ledger_hash}</span>
        <span className="sep" /><span>registrado no Decision Ledger</span>
        <span className="sep" /><span>identificadores mascarados · LGPD</span>
      </div>

      {drawer && (
        <ItemDrawer item={drawer.item} dataMode={drawer.mode} onClose={() => setDrawer(null)} />
      )}
    </React.Fragment>
  );
}

// ── Estado: Vazio ──────────────────────────────────────────────────────────
function EmptyState360() {
  return (
    <div className="invest-hero">
      <div className="hero-mark"><Icon name="radar" /></div>
      <h2>Uma busca, sete fontes</h2>
      <p>Informe um identificador acima: a plataforma consolida sete fontes públicas e restritas num relatório com score de risco em quatro dimensões: jurídico, fiscal, patrimonial e societário.</p>
      <div className="fonte-strip" aria-label="Fontes consultadas">
        {SOURCE_ORDER.map((k) => <Badge key={k} kind="mut">{SOURCES_META[k].name}</Badge>)}
      </div>
      <p style={{ fontSize: 12, color: 'var(--faint)', marginTop: 16 }}>
        Identificadores são mascarados e cada consulta é registrada no Decision Ledger (LGPD).
      </p>
    </div>
  );
}

// ── Estado: Carregando ─────────────────────────────────────────────────────
function LoadingState360({ idMasked, onDone: _onDone }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t0 = performance.now();
    const iv = setInterval(() => {
      const e = performance.now() - t0;
      setElapsed(e);
      if (e > 4200) clearInterval(iv);
    }, 120);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="probe-card">
      <div className="card">
        <div className="card-title" style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          <Icon name="radar" style={{ width: 17, height: 17, color: 'var(--navy)' }} />
          Investigando{idMasked ? <> <span className="mono">{idMasked}</span></> : '…'}
        </div>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', margin: '6px 0 10px' }}>
          As sete fontes são consultadas em paralelo. O score é calculado por um motor determinístico — sem IA generativa — e auditável fator a fator.
        </p>
        <div className="probe-list" role="list" aria-label="Progresso da consulta por fonte">
          {LOADING_STEPS.map((st) => {
            const state = elapsed >= st.t ? 'done' : elapsed >= st.t - 520 ? 'active' : 'waiting';
            return (
              <div className={`probe-row ${state}`} role="listitem" key={st.source}>
                <span className="probe-st" aria-hidden="true">
                  {state === 'done' && <Icon name="check" />}
                </span>
                <span>{SOURCES_META[st.source]?.name || st.source}</span>
                {state === 'done'   && <span className="probe-lat">ok</span>}
                {state === 'active' && <span className="probe-lat">consultando…</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Estado: Erro ───────────────────────────────────────────────────────────
function ErrorState360({ errorMsg, onRetry, onMonitor }) {
  return (
    <div className="err-card card" role="alert">
      <div className="err-mark"><Icon name="alert" /></div>
      <h3>Não foi possível concluir a investigação</h3>
      <p>O orquestrador de integrações não respondeu. Nenhuma fonte foi consultada e nada foi registrado — você pode tentar novamente sem duplicar a consulta.</p>
      {errorMsg && <p className="mono-detail">{errorMsg}</p>}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={onRetry}><Icon name="refresh" /> Tentar novamente</button>
        <button className="btn" onClick={onMonitor}><Icon name="pulse" /> Status das integrações</button>
      </div>
    </div>
  );
}

// ── CommandBar360 ──────────────────────────────────────────────────────────
function CommandBar360({ query, setQuery, onSubmit, busy, expandQsa, setExpandQsa, showSuggest }) {
  const det = detectIdentifier(query);
  return (
    <div className="cmdbar">
      <div className="cmdbar-row">
        <Icon name="search" />
        <input
          value={query}
          disabled={busy}
          aria-label="Identificador para investigação 360°"
          placeholder="CPF, CNPJ, nº de processo (CNJ) ou nome completo…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && det?.ok) onSubmit(det); }}
        />
      </div>
      <div className="cmdbar-foot">
        {det
          ? <span className={`detect-chip${det.ok ? '' : ' off'}`} role="status">
              <Icon name={det.ok ? 'check' : 'info'} />{det.label}
            </span>
          : <span className="detect-chip off"><Icon name="info" />o tipo é detectado automaticamente</span>}
        <label className="cmdbar-opt"
          title="Para CNPJ: consulta também os sócios contra processos e publicações (limite 5).">
          <input type="checkbox" checked={expandQsa} onChange={(e) => setExpandQsa(e.target.checked)} disabled={busy} />
          Expandir quadro societário
        </label>
        <button className="btn btn-primary" disabled={!det?.ok || busy} onClick={() => onSubmit(det)}>
          <Icon name="radar" /> Investigar 360°
        </button>
      </div>
      {showSuggest && (
        <div className="cmd-suggest">
          <span className="lab">Experimente:</span>
          {SUGGESTS.map((s) => (
            <button key={s.q} onClick={() => setQuery(s.q)} title={s.hint}>{s.q}</button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tela principal ─────────────────────────────────────────────────────────
export default function Invest360Screen({ go }) {
  const [ui, setUi]             = useState('empty');   // empty | loading | error | success
  const [query, setQuery]       = useState('');
  const [expandQsa, setExpandQsa] = useState(true);
  const [report, setReport]     = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [depth, setDepth]       = useState('executiva');
  const idMaskedRef             = useRef('');

  const submit = async (det) => {
    if (!det?.ok) return;
    idMaskedRef.current = query.trim().replace(/\d(?=.{2})/g, '*').slice(0, 20);
    setUi('loading');
    setErrorMsg('');
    try {
      const raw = await api.intelligence360(query.trim(), expandQsa);
      if (raw?.errors?.length) throw new Error(raw.errors[0]?.message || 'Erro GraphQL');
      const normalized = normalizeGqlReport(raw);
      setReport(normalized);
      setUi('success');
    } catch (err) {
      setErrorMsg(err?.message || 'Erro desconhecido');
      setUi('error');
    }
  };

  const reset = () => { setUi('empty'); setQuery(''); setReport(null); };

  return (
    <div className="screen">
      <div className="screen-head" style={{ marginBottom: 16 }}>
        <div className="screen-title">Investigação 360°</div>
        <div className="screen-sub">Due diligence de pessoas, empresas e processos em sete fontes, com score de risco auditável.</div>
      </div>

      <CommandBar360
        query={query} setQuery={setQuery} onSubmit={submit}
        busy={ui === 'loading'} expandQsa={expandQsa} setExpandQsa={setExpandQsa}
        showSuggest={ui === 'empty'}
      />

      <div style={{ marginTop: 18 }}>
        {ui === 'empty'   && <EmptyState360 />}
        {ui === 'loading' && <LoadingState360 idMasked={idMaskedRef.current} />}
        {ui === 'error'   && (
          <ErrorState360
            errorMsg={errorMsg}
            onRetry={submit.bind(null, detectIdentifier(query))}
            onMonitor={() => go && go('monitor')}
          />
        )}
        {ui === 'success' && report && (
          <Report360
            report={report} depth={depth} setDepth={setDepth} onNew={reset}
          />
        )}
      </div>
    </div>
  );
}
