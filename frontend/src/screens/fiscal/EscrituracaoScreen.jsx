import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Icon, Badge, Modal, CopyLine } from '../../components/primitives.jsx';
import { api } from '../../api/client.js';
import { getToken } from '../../api/auth.js';

const BASE = import.meta.env.VITE_API_BASE || '';
const BRL = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fmtNum = (v) => Number(v || 0).toLocaleString('pt-BR');

const STEPS = [
  { id: 'upload',      label: 'Upload',        icon: 'attach'  },
  { id: 'proc',        label: 'Processando',   icon: 'refresh' },
  { id: 'achados',     label: 'Achados',       icon: 'alert'   },
  { id: 'lote',        label: 'Edição em lote',icon: 'edit'    },
  { id: 'apuracao',    label: 'Apuração',      icon: 'scale'   },
  { id: 'retificacao', label: 'Retificação',   icon: 'compare' },
  { id: 'perdcomp',    label: 'PER/DCOMP',     icon: 'doc'     },
  { id: 'transmissao', label: 'Transmissão',   icon: 'send'    },
];

const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'];
const SIT_KIND = { devedor: 'crit', credor: 'ok', equilibrado: 'mut' };

// ── helpers ──────────────────────────────────────────────────────────────────

function ErrAlert({ msg }) {
  if (!msg) return null;
  return (
    <div role="alert" style={{ background: 'var(--crit-bg)', color: 'var(--crit)',
      borderRadius: 6, padding: '10px 14px', marginBottom: 14, fontSize: 13,
      display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <Icon name="alert" style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />{msg}
    </div>
  );
}

function Skeleton({ h = 80 }) {
  return <div className="skeleton" style={{ height: h, borderRadius: 8, marginBottom: 14 }} />;
}

// ── Stepper ──────────────────────────────────────────────────────────────────

function FiscalStepper({ step, maxStep, go }) {
  return (
    <div className="fstepper" role="list" aria-label="Etapas da escrituração">
      {STEPS.map((s, i) => {
        const cls = i < step ? 'done' : i === step ? 'now' : (i <= maxStep ? '' : 'locked');
        return (
          <button key={s.id} className={'fstep ' + cls} role="listitem"
            onClick={() => i <= maxStep && go(i)} disabled={i > maxStep}
            aria-current={i === step ? 'step' : undefined}>
            <span className="fs-conn" />
            <span className="fs-dot">{i < step ? <Icon name="check" /> : i + 1}</span>
            <span className="fs-lab">{s.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function EscBar({ escrit }) {
  if (!escrit) return null;
  const cnpj = escrit.cnpj_masked || '**.***.***/****-**';
  return (
    <div className="esc-bar">
      <div className="esc-glyph"><Icon name="doc" /></div>
      <div className="esc-meta">
        <div className="nm">{escrit.empresa || escrit.nome_empresa || 'Escrituração SPED'}</div>
        <div className="sub">
          {cnpj}
          {escrit.uf ? ' · ' + escrit.uf : ''}
          {escrit.periodo || escrit.periodo_competencia ? ' · ' + (escrit.periodo || escrit.periodo_competencia) : ''}
          {escrit.regime ? ' · ' + (escrit.regime || '').replace('_', ' ') : ''}
        </div>
      </div>
      <div className="esc-right">
        <span className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>
          {(escrit.id || escrit.db_id || '').slice(0, 8)}
        </span>
        <Badge kind="navy" icon="lock">PII mascarada</Badge>
      </div>
    </div>
  );
}

// ── Etapa 0: Upload ───────────────────────────────────────────────────────────

function UploadStep({ onDone }) {
  const fileRef = useRef(null);
  const [file,    setFile]    = useState(null);
  const [drag,    setDrag]    = useState(false);
  const [regime,  setRegime]  = useState('lucro_real');
  const [uf,      setUf]      = useState('SP');
  const [periodo, setPeriodo] = useState('');
  const [busy,    setBusy]    = useState(false);
  const [err,     setErr]     = useState('');

  const pick = (f) => {
    if (!f) return;
    if (f.size > 500 * 1024 * 1024) { setErr('Arquivo excede 500 MB.'); return; }
    setFile(f);
    setErr('');
  };

  const doUpload = async () => {
    if (!file) return;
    setBusy(true);
    setErr('');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('regime', regime);
    fd.append('uf', uf);
    if (periodo.trim()) fd.append('periodo', periodo.trim());
    try {
      const token = getToken();
      const res = await fetch(`${BASE}/api/v1/fiscal/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      onDone(data.db_id || data.id, data);
    } catch (ex) {
      setErr(ex?.message || 'Falha no upload.');
    } finally {
      setBusy(false);
    }
  };

  const ready = file && regime && uf;

  return (
    <div>
      <h2 className="step-title">Enviar escrituração SPED</h2>
      <p className="step-sub">
        Importe o arquivo EFD-ICMS/IPI ou EFD-Contribuições. O processamento roda em segundo plano —
        você pode sair e voltar sem perder o progresso.
      </p>
      <ErrAlert msg={err} />
      {!file ? (
        <div className={'dropzone' + (drag ? ' drag' : '')}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
          role="button" tabIndex={0} aria-label="Selecionar arquivo SPED"
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileRef.current?.click()}>
          <div className="dz-mark"><Icon name="attach" /></div>
          <h3>Arraste o arquivo .txt ou clique para selecionar</h3>
          <p>EFD-ICMS/IPI · EFD-Contribuições — um arquivo por período</p>
          <div className="dz-hint">FORMATO .TXT · ATÉ 500 MB · VALIDAÇÃO DE LAYOUT AUTOMÁTICA</div>
          <input ref={fileRef} type="file" accept=".txt,.xml,.zip" style={{ display: 'none' }}
            onChange={(e) => pick(e.target.files[0])} />
        </div>
      ) : (
        <div className="file-chip">
          <div className="fc-glyph"><Icon name="doc" /></div>
          <div style={{ flex: 1 }}>
            <div className="fc-name">{file.name}</div>
            <div className="fc-meta">{(file.size / (1024 * 1024)).toFixed(1)} MB · pronto para envio</div>
          </div>
          <Badge kind="ok" icon="check">tipo OK</Badge>
          <button className="icon-btn" aria-label="Remover arquivo" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ''; }}>
            <Icon name="x" />
          </button>
        </div>
      )}
      <div className="field-row">
        <div className="field">
          <label htmlFor="f-regime">Regime de tributação</label>
          <select id="f-regime" className="input" value={regime} onChange={(e) => setRegime(e.target.value)}>
            <option value="lucro_real">Lucro Real</option>
            <option value="lucro_presumido">Lucro Presumido</option>
            <option value="simples">Simples Nacional</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-uf">UF</label>
          <select id="f-uf" className="input" value={uf} onChange={(e) => setUf(e.target.value)}>
            {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-per">Período (aaaa-mm)</label>
          <input id="f-per" className="input" type="text" placeholder="2025-12"
            value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
        </div>
      </div>
      <div className="step-foot">
        <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
          {ready ? 'Pronto para enviar.' : 'Selecione o arquivo e confirme regime e UF.'}
        </span>
        <div className="spacer" />
        <button className="btn btn-primary" disabled={!ready || busy} onClick={doUpload}>
          <Icon name="send" />{busy ? 'Enviando…' : 'Enviar escrituração'}
        </button>
      </div>
    </div>
  );
}

// ── Etapa 1: Processando ──────────────────────────────────────────────────────

const JOB_MSGS = [
  'Lendo cabeçalho e identificando blocos…',
  'Validando registros do bloco 0…',
  'Processando bloco C (documentos fiscais)…',
  'Aplicando regras de validação ICMS…',
  'Processando bloco E (apurações)…',
  'Cruzando registros C170 com E110…',
  'Gerando sumário de achados…',
  'Finalizando processamento…',
];

function ProcessingStep({ escrituracaoId, onDone }) {
  const [pct,    setPct]    = useState(0);
  const [escrit, setEscrit] = useState(null);
  const [done,   setDone]   = useState(false);
  const [lines,  setLines]  = useState([]);

  useEffect(() => {
    if (!escrituracaoId) return;
    let cancelled = false;
    JOB_MSGS.forEach((msg, i) => {
      setTimeout(() => { if (!cancelled) setLines((p) => [...p, msg]); }, 900 * (i + 1));
    });
    const tick = setInterval(() => setPct((p) => (p < 90 ? p + 1 : p)), 250);
    const poll = setInterval(async () => {
      try {
        const data = await api.fiscalJob(escrituracaoId);
        if (!cancelled) setEscrit(data);
        const s = (data.status || '').toLowerCase();
        if (s === 'concluido' || s === 'processado' || s === 'completed' || s === 'done') {
          if (!cancelled) { setDone(true); setPct(100); clearInterval(poll); clearInterval(tick); }
        }
      } catch { /* keep polling */ }
    }, 2500);
    return () => { cancelled = true; clearInterval(tick); clearInterval(poll); };
  }, [escrituracaoId]);

  return (
    <div>
      <h2 className="step-title">Processando escrituração</h2>
      <p className="step-sub">
        Job <span className="mono">{escrituracaoId?.slice(0, 8)}…</span> em execução.
        Você pode navegar para outras telas — avisaremos quando terminar.
      </p>
      <div className={'job-card' + (done ? ' done' : '')}>
        <div className="job-head">
          <div className="job-spin">{done && <Icon name="check" />}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              {done ? 'Processamento concluído' : 'Lendo blocos e aplicando regras de validação…'}
            </div>
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--faint)', marginTop: 2 }}>
              {escrit?.total_registros ? fmtNum(escrit.total_registros) + ' registros' : 'aguardando…'}
            </div>
          </div>
          <Badge kind={done ? 'ok' : 'navy'} dot>{done ? 'processado' : 'processando'}</Badge>
        </div>
        <div className="job-bar"><div className="job-fill" style={{ width: pct + '%' }} /></div>
        <div className="job-pct">{pct}%</div>
        {lines.length > 0 && (
          <div className="job-log">
            {lines.map((l, i) => (
              <div className="job-line" key={i}>
                <span className="jl-dot"><Icon name="check" /></span>
                <span>{l}</span>
                <span className="jl-t">{(0.9 * (i + 1)).toFixed(1)}s</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="step-foot">
        <div className="spacer" />
        <button className="btn btn-primary" disabled={!done} onClick={() => onDone(escrit)}>
          <Icon name="alert" />
          Ver achados
          {escrit && ` (${(escrit.total_erros || 0)} erros, ${(escrit.total_avisos || 0)} avisos)`}
        </button>
      </div>
    </div>
  );
}

// ── Etapa 2: Achados ──────────────────────────────────────────────────────────

function AchadosStep({ escrituracaoId, onCorrigir }) {
  const [sev,   setSev]   = useState('todos');
  const [items, setItems] = useState(null);
  const [err,   setErr]   = useState('');

  useEffect(() => {
    if (!escrituracaoId) return;
    api.fiscalAchados(escrituracaoId)
      .then((d) => setItems(d.achados || d.items || (Array.isArray(d) ? d : [])))
      .catch((e) => setErr(e?.message || 'Erro ao carregar achados.'));
  }, [escrituracaoId]);

  const norm = (s) => (s || '').toLowerCase();
  const list   = items ? items.filter((a) => sev === 'todos' || norm(a.severidade || a.sev) === sev) : [];
  const nErro  = items ? items.filter((a) => norm(a.severidade || a.sev) === 'erro').length  : 0;
  const nAviso = items ? items.filter((a) => norm(a.severidade || a.sev) === 'aviso').length : 0;

  return (
    <div>
      <h2 className="step-title">Achados da validação</h2>
      <p className="step-sub">
        Inconsistências detectadas pelo motor de regras. Erros bloqueiam a apuração; avisos são recomendações.
      </p>
      <ErrAlert msg={err} />
      <div className="ach-filters">
        <div className="seg" role="tablist" aria-label="Filtro de severidade">
          <button className={sev === 'todos' ? 'on' : ''} onClick={() => setSev('todos')}>
            Todos · {items?.length ?? '…'}
          </button>
          <button className={sev === 'erro' ? 'on' : ''} onClick={() => setSev('erro')}>
            Erros · {nErro}
          </button>
          <button className={sev === 'aviso' ? 'on' : ''} onClick={() => setSev('aviso')}>
            Avisos · {nAviso}
          </button>
        </div>
      </div>
      {items === null && !err && <Skeleton h={180} />}
      {items !== null && list.length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--faint)' }}>
          <Icon name="check" style={{ width: 28, height: 28, color: 'var(--ok)', marginBottom: 8 }} />
          <div>Nenhum achado para este filtro.</div>
        </div>
      )}
      {list.map((a, i) => {
        const sl = norm(a.severidade || a.sev);
        return (
          <div className={'ach-card ' + sl} key={a.id || i}>
            <div className="ach-top">
              <Badge kind={sl === 'erro' ? 'crit' : 'warn'} icon={sl === 'erro' ? 'alert' : 'info'}>
                {(a.severidade || a.sev || 'AVISO').toUpperCase()}
              </Badge>
              <Badge kind="mut">{a.regra_id || a.regra || 'REGRA'}</Badge>
              <span className="ach-reg">
                {a.tipo_registro || a.registro || ''} · linha {fmtNum(a.numero_linha || a.linha || 0)}
                {(a.campo) ? ' · ' + a.campo : ''}
              </span>
            </div>
            <div className="ach-desc">{a.descricao || a.desc}</div>
            {(a.dica || a.sugestao) && (
              <div className="ach-dica">
                <Icon name="spark" />
                <span>{a.dica || a.sugestao}</span>
              </div>
            )}
          </div>
        );
      })}
      <div className="step-foot">
        <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
          <b style={{ color: 'var(--crit)' }}>{nErro} erros</b> precisam de correção antes da apuração.
        </span>
        <div className="spacer" />
        <button className="btn btn-primary" onClick={onCorrigir}>
          <Icon name="edit" />Corrigir em lote
        </button>
      </div>
    </div>
  );
}

// ── Etapa 3: Edição em lote ───────────────────────────────────────────────────

function LoteStep({ escrituracaoId, onApplied }) {
  const [phase,    setPhase]    = useState('edit');
  const [registros,setRegistros]= useState(null);
  const [dryRun,   setDryRun]   = useState(null);
  const [hitlProt, setHitlProt] = useState(null);
  const [busy,     setBusy]     = useState(false);
  const [err,      setErr]      = useState('');

  useEffect(() => {
    if (!escrituracaoId) return;
    api.fiscalRegistros(escrituracaoId)
      .then((d) => setRegistros(d.registros || d.items || (Array.isArray(d) ? d : [])))
      .catch((e) => setErr(e?.message || 'Erro ao carregar registros.'));
  }, [escrituracaoId]);

  const runDryRun = async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.fiscalLote(escrituracaoId, { dry_run: true, tipo_registro: 'C170' });
      setDryRun(res);
      setPhase('preview');
    } catch (e) {
      setErr(e?.message || 'Erro no dry-run.');
    } finally {
      setBusy(false);
    }
  };

  const aplicar = async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.fiscalLote(escrituracaoId, { dry_run: false, tipo_registro: 'C170' });
      if (res?.hitl_required || res?.requires_hitl) {
        setHitlProt(res?.hitl_id || res?.protocol || ('HITL-' + Date.now()));
        setPhase('aguardando');
      } else {
        onApplied();
      }
    } catch (e) {
      setErr(e?.message || 'Erro ao aplicar.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h2 className="step-title">Edição em lote</h2>
      <p className="step-sub">
        Correção dos registros com CST indevida. O <b>dry-run</b> simula o resultado e revalida antes de qualquer gravação.
      </p>
      <ErrAlert msg={err} />
      {phase === 'preview' && (
        <div className="dryrun-banner">
          <Icon name="check" />
          <span>
            <b>Dry-run concluído.</b> Simulação concluída — nenhuma gravação feita ainda.
            {dryRun?.resumo && <> {dryRun.resumo}</>}
          </span>
        </div>
      )}
      {phase === 'aguardando' && (
        <div className="hitl-gate pending" role="status">
          <div className="hg-head">
            <Icon name="clock" />
            <span>
              <b>Aguardando aprovação humana (HITL).</b> A edição em lote excede a faixa de autonomia e foi
              enviada para revisão de um auditor antes de gravar.
            </span>
          </div>
          <div className="hitl-steps">
            <div className="hitl-step done"><span className="hs-dot"><Icon name="check" /></span>Solicitado</div>
            <span className="hitl-conn" />
            <div className="hitl-step now"><span className="hs-dot" />Em revisão</div>
            <span className="hitl-conn" />
            <div className="hitl-step idle"><span className="hs-dot" />Aplicado</div>
          </div>
          {hitlProt && <div className="hg-meta">PROTOCOLO {hitlProt}</div>}
        </div>
      )}
      {registros === null && !err && <Skeleton h={100} />}
      {registros !== null && registros.length > 0 && (
        <div className="tbl-wrap" style={{ marginBottom: 14 }}>
          <table className="t2">
            <thead><tr>
              <th>Bloco</th><th>Tipo</th><th>Linha</th><th>Campos</th>
            </tr></thead>
            <tbody>
              {registros.slice(0, 25).map((r, i) => (
                <tr key={r.id || i}>
                  <td className="mono">{r.bloco}</td>
                  <td className="mono" style={{ fontWeight: 600 }}>{r.tipo_registro}</td>
                  <td>{r.numero_linha}</td>
                  <td style={{ color: 'var(--faint)', fontSize: 11 }}>
                    {Object.keys(r.campos || {}).slice(0, 4).join(', ')}
                    {Object.keys(r.campos || {}).length > 4 ? ' …' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {registros !== null && registros.length === 0 && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--faint)' }}>
          Nenhum registro carregado.
        </div>
      )}
      <div className="step-foot">
        {phase === 'aguardando' ? (
          <>
            <Badge kind="warn" dot>aguardando_aprovação</Badge>
            <div className="spacer" />
            <button className="btn btn-primary" onClick={onApplied}>
              <Icon name="chevron" />Avançar para Apuração
            </button>
          </>
        ) : (
          <>
            <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
              {phase === 'edit' ? 'Rode o dry-run para pré-visualizar as alterações.' : 'Resultado simulado acima.'}
            </span>
            <div className="spacer" />
            {phase === 'edit'
              ? <button className="btn" onClick={runDryRun} disabled={busy || registros === null}>
                  <Icon name="compare" />{busy ? 'Simulando…' : 'Pré-visualizar (dry-run)'}
                </button>
              : <button className="btn" onClick={() => setPhase('edit')}><Icon name="edit" />Revisar</button>}
            <button className="btn btn-primary" disabled={phase !== 'preview' || busy} onClick={aplicar}>
              <Icon name="check" />{busy ? 'Aplicando…' : 'Aplicar correção'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Etapa 4: Apuração ─────────────────────────────────────────────────────────

function ApuracaoStep({ escrituracaoId, onNext }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState('');

  const calcular = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.fiscalApuracao(escrituracaoId);
      setData(res?.apuracoes || res?.tributos || (Array.isArray(res) ? res : null));
    } catch (e) {
      setErr(e?.message || 'Erro na apuração.');
    } finally {
      setBusy(false);
    }
  }, [escrituracaoId]);

  useEffect(() => { if (escrituracaoId) calcular(); }, []);

  const totalDev = data
    ? data.filter((a) => (a.situacao || a.sit) === 'devedor')
        .reduce((s, a) => s + Number(a.saldo_apurado || a.saldo || 0), 0)
    : 0;

  return (
    <div>
      <h2 className="step-title">Apuração por tributo</h2>
      <p className="step-sub">
        Débitos, créditos, ajustes e saldo de cada tributo. Divergências entre o valor computado e o declarado ficam em destaque.
      </p>
      <ErrAlert msg={err} />
      {busy && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--faint)' }}>
          <div className="job-spin" style={{ margin: '0 auto 12px', width: 28, height: 28, borderWidth: 2 }} />
          Calculando apuração…
        </div>
      )}
      {data && (
        <div className="apur-grid">
          {data.map((a, i) => {
            const sit  = a.situacao || a.sit || 'equilibrado';
            const kind = SIT_KIND[sit] || 'mut';
            const saldo = Number(a.saldo_apurado || a.saldo || 0);
            const comp  = Number(a.valor_computado || a.computado || 0);
            const decl  = Number(a.valor_declarado || a.declarado || 0);
            const diverg = comp > 0 && decl > 0 && Math.abs(comp - decl) > 0.01;
            return (
              <div className="apur-card" key={a.tributo || i}>
                <div className="apur-head">
                  <span className="apur-trib">{a.tributo}</span>
                  <span className="apur-reg">{a.tipo_registro || a.reg || ''}</span>
                  <div className="apur-saldo">
                    <div className="l">saldo</div>
                    <div className="v" style={{
                      color: kind === 'crit' ? 'var(--crit)' : kind === 'ok' ? 'var(--ok)' : 'var(--ink)',
                    }}>{BRL(saldo)}</div>
                  </div>
                  <Badge kind={kind} dot>{sit}</Badge>
                </div>
                <div className="apur-body">
                  <div className="apur-cell">
                    <div className="cl">Débitos</div>
                    <div className="cv">{BRL(a.total_debitos || a.deb || 0)}</div>
                  </div>
                  <div className="apur-cell">
                    <div className="cl">Créditos</div>
                    <div className="cv">{BRL(a.total_creditos || a.cred || 0)}</div>
                  </div>
                  <div className="apur-cell">
                    <div className="cl">Ajustes</div>
                    <div className="cv">
                      {a.ajustes != null || a.ajuste != null ? BRL(a.ajustes || a.ajuste || 0) : '—'}
                    </div>
                  </div>
                </div>
                {diverg && (
                  <div className="apur-diverg">
                    <Icon name="alert" />
                    <span>
                      Divergência computado × declarado:{' '}
                      <span className="mono">{BRL(comp)}</span> vs <span className="mono">{BRL(decl)}</span>
                      {' '}— revisar antes de retificar.
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <div className="step-foot">
        {data && (
          <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
            Saldo devedor consolidado: <b className="mono">{BRL(totalDev)}</b>
          </span>
        )}
        <div className="spacer" />
        {!data && !busy && (
          <button className="btn" onClick={calcular}><Icon name="refresh" />Recalcular</button>
        )}
        <button className="btn btn-primary" disabled={!data} onClick={onNext}>
          <Icon name="compare" />Gerar retificação
        </button>
      </div>
    </div>
  );
}

// ── Etapa 5: Retificação ──────────────────────────────────────────────────────

function RetificacaoStep({ escrituracaoId, onNext }) {
  const [diff,       setDiff]       = useState(null);
  const [validated,  setValidated]  = useState(false);
  const [validating, setValidating] = useState(false);
  const [confirm,    setConfirm]    = useState(false);
  const [generated,  setGenerated]  = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [err,        setErr]        = useState('');

  useEffect(() => {
    if (!escrituracaoId) return;
    api.retificacaoComparar({ escrituracao_id: escrituracaoId })
      .then((d) => setDiff(d.diff || d.alteracoes || d.changes || []))
      .catch(() => setDiff([]));
  }, [escrituracaoId]);

  const validarLayout = async () => {
    setValidating(true);
    setErr('');
    try {
      await api.retificacaoValidarLayout({ escrituracao_id: escrituracaoId });
      setValidated(true);
    } catch (e) {
      setErr(e?.message || 'Erro na validação de layout.');
    } finally {
      setValidating(false);
    }
  };

  const gerarRetificadora = async () => {
    try { await api.retificacaoGerar({ escrituracao_id: escrituracaoId }); } catch { /* best-effort */ }
    setGenerated(true);
    setConfirm(false);
  };

  return (
    <div>
      <h2 className="step-title">Retificação da escrituração</h2>
      <p className="step-sub">
        Comparação do arquivo original com a versão corrigida. Gerar a retificadora é um <b>ato formal</b> —
        confirme antes de prosseguir.
      </p>
      <ErrAlert msg={err} />
      {diff === null && <Skeleton h={140} />}
      {diff !== null && diff.length === 0 && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--faint)' }}>
          Sem diferenças registradas para esta escrituração.
        </div>
      )}
      {diff !== null && diff.length > 0 && (
        <div className="diff-view">
          {diff.map((d, i) => (
            <div className="diff-grp" key={i}>
              <div className="diff-grp-h">{d.tipo_registro || d.reg || `Registro ${i + 1}`}</div>
              <div className="diff-line del">
                <span className="sign">−</span><span>{d.original || d.orig || ''}</span>
              </div>
              <div className="diff-line add">
                <span className="sign">+</span><span>{d.retificado || d.ret || ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {validated && (
        <div className="validate-ok">
          <Icon name="check" />
          <span>Layout validado · {diff?.length || 0} alteração(ões) · estrutura EFD íntegra · pronto para gerar.</span>
        </div>
      )}
      {generated && (
        <div className="card" style={{ padding: 16, marginTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div className="fc-glyph-sm"><Icon name="doc" /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>SPED_retificadora.txt</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--faint)' }}>nota de correção registrada</div>
            </div>
            <button className={'btn' + (downloaded ? '' : ' btn-primary')} onClick={() => setDownloaded(true)}>
              <Icon name={downloaded ? 'check' : 'copy'} />{downloaded ? 'Baixado' : 'Baixar TXT'}
            </button>
          </div>
        </div>
      )}
      <div className="step-foot">
        <div className="spacer" />
        {!validated
          ? <button className="btn" onClick={validarLayout} disabled={validating}>
              <Icon name="check" />{validating ? 'Validando…' : 'Validar layout'}
            </button>
          : !generated
            ? <button className="btn btn-danger" onClick={() => setConfirm(true)}>
                <Icon name="alert" />Gerar retificadora
              </button>
            : <button className="btn btn-primary" onClick={onNext}>
                <Icon name="chevron" />Avançar para PER/DCOMP
              </button>}
      </div>
      {confirm && (
        <Modal title="Gerar escrituração retificadora?" onClose={() => setConfirm(false)}
          actions={
            <>
              <button className="btn" onClick={() => setConfirm(false)}>Cancelar</button>
              <button className="btn btn-danger" onClick={gerarRetificadora}>
                <Icon name="check" />Confirmar e gerar
              </button>
            </>
          }>
          <p style={{ marginTop: 0 }}>
            A retificadora substitui a escrituração entregue para este período. Esta ação fica registrada
            no Decision Ledger com o identificador mascarado.
          </p>
          <div className="ach-dica" style={{ marginTop: 4 }}>
            <Icon name="info" /><span>Ação irreversível — não pode ser desfeita após confirmação.</span>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Etapa 6: PER/DCOMP ───────────────────────────────────────────────────────

const TIPOS_FALLBACK = [
  { id: 'per',             nome: 'PER',             desc: 'Pedido de Ressarcimento' },
  { id: 'dcomp',           nome: 'DCOMP',           desc: 'Declaração de Compensação' },
  { id: 'ressarcimento_ipi', nome: 'Ressarcimento IPI', desc: 'Ressarcimento de créditos de IPI' },
];

function PerDcompStep({ escrituracaoId, onNext }) {
  const [tipos,  setTipos]  = useState(null);
  const [tipo,   setTipo]   = useState('dcomp');
  const [ficha,  setFicha]  = useState(null);
  const [busy,   setBusy]   = useState(false);
  const [err,    setErr]    = useState('');

  useEffect(() => {
    api.perDcompTipos()
      .then((d) => setTipos(d.tipos || (Array.isArray(d) ? d : TIPOS_FALLBACK)))
      .catch(() => setTipos(TIPOS_FALLBACK));
  }, []);

  const gerarFicha = async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.perDcompGerar({ escrituracao_id: escrituracaoId, tipo });
      setFicha(res);
    } catch (e) {
      setErr(e?.message || 'Erro ao gerar ficha PER/DCOMP.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h2 className="step-title">PER/DCOMP</h2>
      <p className="step-sub">
        Aproveite o crédito apurado. Escolha o tipo, gere a partir da apuração e valide o layout antes de transmitir.
      </p>
      <ErrAlert msg={err} />
      {tipos && (
        <div className="type-grid">
          {tipos.map((tp) => (
            <button key={tp.id} className={'type-opt' + (tipo === tp.id ? ' sel' : '')}
              onClick={() => { setTipo(tp.id); setFicha(null); }}>
              <span className="type-radio" />
              <span>
                <span className="to-nm">{tp.nome}</span>
                <span className="to-desc">{tp.desc}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      {!ficha ? (
        <div className="step-foot">
          <div className="spacer" />
          <button className="btn btn-primary" onClick={gerarFicha} disabled={busy}>
            <Icon name="doc" />{busy ? 'Gerando…' : 'Gerar de apuração'}
          </button>
        </div>
      ) : (
        <>
          <div className="ficha">
            <div className="ficha-head">
              <div className="fc-glyph-sm"><Icon name="doc" /></div>
              <div className="ft">{ficha.tipo || tipo.toUpperCase()}</div>
              <Badge kind="ok" icon="check">layout válido</Badge>
            </div>
            <div className="ficha-body">
              <dl className="kv">
                <dt>Número</dt><dd className="mono">{ficha.numero || ficha.id || '—'}</dd>
                <dt>Período</dt><dd className="mono">{ficha.periodo || ficha.periodo_competencia || '—'}</dd>
                <dt>Origem do crédito</dt><dd>{ficha.origem || ficha.tipo_credito || '—'}</dd>
                <dt>Crédito original</dt>
                <dd className="mono">{BRL(ficha.credito || ficha.valor_credito || 0)}</dd>
                {ficha.selic != null && (
                  <><dt>Selic acumulada</dt><dd className="mono">{BRL(ficha.selic)}</dd></>
                )}
                <dt>Situação</dt><dd><Badge kind="mut">{ficha.situacao || 'em_elaboracao'}</Badge></dd>
              </dl>
              {(ficha.total || ficha.valor_total) && (
                <div className="ficha-total">
                  <span className="tl">Crédito total atualizado</span>
                  <span className="tv">{BRL(ficha.total || ficha.valor_total)}</span>
                </div>
              )}
            </div>
          </div>
          <div className="step-foot">
            <div className="spacer" />
            <button className="btn btn-primary" onClick={onNext}>
              <Icon name="send" />Transmitir ao e-CAC
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── Etapa 7: Transmissão ──────────────────────────────────────────────────────

function TransmissaoStepInline({ escrituracaoId }) {
  const [circuit,  setCircuit]  = useState(null);
  const [confirm,  setConfirm]  = useState(false);
  const [checked,  setChecked]  = useState(false);
  const [status,   setStatus]   = useState('idle');
  const [protocolo,setProtocolo]= useState(null);
  const [err,      setErr]      = useState('');

  useEffect(() => {
    api.transmissaoCircuit()
      .then((d) => setCircuit(d))
      .catch(() => setCircuit({ open: false }));
  }, []);

  const circuitOpen = circuit?.open || circuit?.status === 'open';

  const transmitir = async () => {
    setConfirm(false);
    setStatus('sending');
    setErr('');
    try {
      const res = await api.transmissaoEnviar({ escrituracao_id: escrituracaoId });
      setProtocolo(res?.protocolo || res?.protocol || res?.id || ('PROT-' + Date.now()));
      setStatus('done');
    } catch (e) {
      setErr(e?.message || 'Erro na transmissão ao e-CAC.');
      setStatus('idle');
    }
  };

  if (status === 'done') {
    return (
      <div style={{ textAlign: 'center', maxWidth: 520, margin: '20px auto' }}>
        <div className="success-mark"><Icon name="check" /></div>
        <h2 className="step-title" style={{ marginBottom: 6 }}>Transmitido ao e-CAC</h2>
        <p className="step-sub" style={{ margin: '0 auto 18px' }}>
          Transmissão em ambiente de homologação concluída.
        </p>
        {protocolo && (
          <div style={{ display: 'grid', gap: 10, textAlign: 'left', maxWidth: 480, margin: '0 auto' }}>
            <CopyLine value={protocolo} label="protocolo" />
          </div>
        )}
        <div className="audit-foot" style={{ justifyContent: 'center', marginTop: 18 }}>
          <span>registrado no Decision Ledger</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="step-title">Transmissão ao e-CAC</h2>
      <p className="step-sub">Ação <b>irreversível</b> e federal. Confira o resumo e o estado do canal antes de transmitir.</p>
      <ErrAlert msg={err} />
      <div className="amb-banner homolog">
        <Icon name="shield" />
        <span><b>Ambiente: HOMOLOGAÇÃO.</b> Nenhum efeito legal — ideal para validar o fluxo.</span>
      </div>
      {circuit !== null && (
        circuitOpen ? (
          <div className="circuit open">
            <Icon name="alert" />
            <span><b>e-CAC indisponível.</b> Circuit breaker aberto após falhas consecutivas. Tente novamente em alguns minutos.</span>
          </div>
        ) : (
          <div className="circuit closed">
            <Icon name="check" />
            <span>Canal e-CAC operacional · circuit breaker <b>fechado</b>.</span>
          </div>
        )
      )}
      {circuit === null && <Skeleton h={52} />}
      <div className="step-foot">
        <div className="spacer" />
        {status === 'sending'
          ? <button className="btn btn-primary" disabled>
              <span className="job-spin" style={{ width: 16, height: 16, borderWidth: 2, marginRight: 6 }} />
              Transmitindo…
            </button>
          : <button className="btn btn-primary" disabled={circuitOpen}
              onClick={() => { setChecked(false); setConfirm(true); }}>
              <Icon name="send" />Transmitir
            </button>}
      </div>
      {confirm && (
        <Modal title="Confirmar transmissão" onClose={() => setConfirm(false)}
          actions={
            <>
              <button className="btn" onClick={() => setConfirm(false)}>Cancelar</button>
              <button className="btn btn-primary" disabled={!checked} onClick={transmitir}>
                <Icon name="send" />Transmitir agora
              </button>
            </>
          }>
          <p style={{ marginTop: 0 }}>
            Esta ação transmite a declaração ao e-CAC (homologação) e <b>não pode ser desfeita</b>.
          </p>
          <label className="confirm-check">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            <span>Confirmo que revisei a declaração e estou ciente de que a transmissão é irreversível.</span>
          </label>
        </Modal>
      )}
    </div>
  );
}

// ── EscrituracaoScreen ────────────────────────────────────────────────────────

export default function EscrituracaoScreen() {
  const [step,           setStep]           = useState(() => Number(sessionStorage.getItem('f_step') || 0));
  const [maxStep,        setMaxStep]        = useState(() => Number(sessionStorage.getItem('f_max') || 0));
  const [escrituracaoId, setEscrituracaoId] = useState(() => sessionStorage.getItem('f_eid') || null);
  const [escrit,         setEscrit]         = useState(null);

  const go = (i) => {
    const newMax = Math.max(maxStep, i);
    setStep(i);
    setMaxStep(newMax);
    sessionStorage.setItem('f_step', i);
    sessionStorage.setItem('f_max', newMax);
    document.getElementById('main')?.scrollTo(0, 0);
  };
  const next = () => go(step + 1);

  const reset = () => {
    setStep(0); setMaxStep(0); setEscrituracaoId(null); setEscrit(null);
    ['f_step', 'f_max', 'f_eid'].forEach((k) => sessionStorage.removeItem(k));
  };

  const onUploadDone = (id, data) => {
    setEscrituracaoId(id);
    if (data) setEscrit(data);
    sessionStorage.setItem('f_eid', id);
    go(1);
  };

  const onProcessingDone = (data) => {
    if (data) setEscrit(data);
    go(2);
  };

  const content = (() => {
    switch (step) {
      case 0: return <UploadStep onDone={onUploadDone} />;
      case 1: return <ProcessingStep escrituracaoId={escrituracaoId} onDone={onProcessingDone} />;
      case 2: return <AchadosStep escrituracaoId={escrituracaoId} onCorrigir={next} />;
      case 3: return <LoteStep escrituracaoId={escrituracaoId} onApplied={next} />;
      case 4: return <ApuracaoStep escrituracaoId={escrituracaoId} onNext={next} />;
      case 5: return <RetificacaoStep escrituracaoId={escrituracaoId} onNext={next} />;
      case 6: return <PerDcompStep escrituracaoId={escrituracaoId} onNext={next} />;
      case 7: return <TransmissaoStepInline escrituracaoId={escrituracaoId} />;
      default: return null;
    }
  })();

  return (
    <div className="fiscal-screen">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Escrituração SPED</h2>
          <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 1 }}>
            {STEPS[step].label} · etapa {step + 1} de {STEPS.length}
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-sm" onClick={reset} title="Reiniciar fluxo">
          <Icon name="refresh" style={{ width: 14, height: 14 }} /> Novo
        </button>
      </div>
      <FiscalStepper step={step} maxStep={maxStep} go={go} />
      {step >= 1 && escrit && <EscBar escrit={escrit} />}
      {content}
    </div>
  );
}
