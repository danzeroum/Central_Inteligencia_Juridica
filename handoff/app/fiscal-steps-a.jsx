/* fiscal-steps-a.jsx — etapas 1–4 do fio-de-ouro: Upload · Processando · Achados · Edição em lote */

const { useState: useStA, useEffect: useEfA, useRef: useRfA } = React;

/* ---------- 1 · Upload SPED ---------- */
function UploadStep({ onSend }) {
  const [file, setFile] = useStA(null);
  const [regime, setRegime] = useStA('lucro_real');
  const [uf, setUf] = useStA('SP');
  const [drag, setDrag] = useStA(false);

  const pick = () => setFile({ name: ESCRITURACAO.arquivo, size: ESCRITURACAO.tamanho });
  const ready = file && regime && uf;

  return (
    <div data-screen-label="Fiscal · Upload SPED">
      <h2 className="step-title">Enviar escrituração SPED</h2>
      <p className="step-sub">Importe o arquivo EFD-ICMS/IPI ou EFD-Contribuições. O processamento roda em segundo plano —
        você pode sair e voltar sem perder o progresso.</p>

      {!file ? (
        <div className={'dropzone' + (drag ? ' drag' : '')} onClick={pick}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(); }}
          role="button" tabIndex={0} aria-label="Selecionar arquivo SPED"
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && pick()}>
          <div className="dz-mark"><Icon name="attach" /></div>
          <h3>Arraste o arquivo .txt ou clique para selecionar</h3>
          <p>EFD-ICMS/IPI · EFD-Contribuições — um arquivo por período</p>
          <div className="dz-hint">FORMATO .TXT · ATÉ 500 MB · VALIDAÇÃO DE LAYOUT AUTOMÁTICA</div>
        </div>
      ) : (
        <div className="file-chip">
          <div className="fc-glyph"><Icon name="doc" /></div>
          <div style={{ flex: 1 }}>
            <div className="fc-name">{file.name}</div>
            <div className="fc-meta">{file.size} · validado · layout EFD-ICMS-IPI v018</div>
          </div>
          <Badge kind="ok" icon="check">tipo e tamanho OK</Badge>
          <button className="icon-btn" aria-label="Remover arquivo" onClick={() => setFile(null)}><Icon name="x" /></button>
        </div>
      )}

      <div className="field-row">
        <div className="field">
          <label htmlFor="f-regime">Regime de tributação</label>
          <select id="f-regime" className="select" value={regime} onChange={(e) => setRegime(e.target.value)}>
            <option value="lucro_real">Lucro Real</option>
            <option value="presumido">Lucro Presumido</option>
            <option value="simples">Simples Nacional</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-uf">UF</label>
          <select id="f-uf" className="select" value={uf} onChange={(e) => setUf(e.target.value)}>
            {['SP', 'RJ', 'MG', 'RS', 'PR', 'SC', 'BA', 'PE', 'GO', 'DF'].map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-per">Período de referência</label>
          <input id="f-per" className="input" type="text" defaultValue="2025-12" placeholder="aaaa-mm" />
        </div>
      </div>

      <div className="step-foot">
        <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
          {ready ? 'Pronto para enviar.' : 'Selecione o arquivo e confirme regime e UF.'}
        </span>
        <div className="spacer"></div>
        <button className="btn-primary btn" disabled={!ready} onClick={onSend}>
          <Icon name="send" />Enviar escrituração
        </button>
      </div>
    </div>
  );
}

/* ---------- 2 · Processando (job assíncrono) ---------- */
function ProcessingStep({ onDone }) {
  const [pct, setPct] = useStA(0);
  const [lines, setLines] = useStA([]);
  const doneRef = useRfA(false);
  const total = JOB_LOG[JOB_LOG.length - 1].t;

  useEfA(() => {
    const timers = [];
    JOB_LOG.forEach((l) => {
      timers.push(setTimeout(() => {
        setLines((prev) => [...prev, l]);
        setPct(Math.round((l.t / total) * 100));
      }, l.t));
    });
    timers.push(setTimeout(() => { doneRef.current = true; setPct(100); }, total + 200));
    // animação suave da barra entre marcos
    const tick = setInterval(() => setPct((p) => (p < 99 && !doneRef.current ? p + 1 : p)), 90);
    return () => { timers.forEach(clearTimeout); clearInterval(tick); };
  }, []);

  const done = pct >= 100;
  return (
    <div data-screen-label="Fiscal · Processando">
      <h2 className="step-title">Processando escrituração</h2>
      <p className="step-sub">Job <span className="mono">{ESCRITURACAO.db_id}</span> em execução. A interface não trava:
        você pode navegar para outras telas — avisaremos quando terminar.</p>

      <div className={'job-card' + (done ? ' done' : '')}>
        <div className="job-head">
          <div className="job-spin">{done && <Icon name="check" />}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              {done ? 'Processamento concluído' : 'Lendo blocos e aplicando regras de validação…'}
            </div>
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--faint)', marginTop: 2 }}>
              {fmtNum(ESCRITURACAO.registros)} registros · blocos {ESCRITURACAO.blocos.join(' ')}
            </div>
          </div>
          <Badge kind={done ? 'ok' : 'navy'} dot>{done ? 'processado' : 'processando'}</Badge>
        </div>

        <div className="job-bar"><div className="job-fill" style={{ width: pct + '%' }}></div></div>
        <div className="job-pct">{pct}%</div>

        <div className="job-log">
          {lines.map((l, i) => (
            <div className="job-line" key={i}>
              <span className="jl-dot"><Icon name="check" /></span>
              <span>{l.msg}</span>
              <span className="jl-t">{(l.t / 1000).toFixed(1)}s</span>
            </div>
          ))}
        </div>
      </div>

      <div className="step-foot">
        <div className="spacer"></div>
        <button className="btn-primary btn" disabled={!done} onClick={onDone}>
          <Icon name="alert" />Ver achados (6)
        </button>
      </div>
    </div>
  );
}

/* ---------- 3 · Achados ---------- */
function AchadosStep({ onCorrigir }) {
  const [sev, setSev] = useStA('todos');
  const list = ACHADOS.filter((a) => sev === 'todos' || a.sev === sev);
  const nErro = ACHADOS.filter((a) => a.sev === 'ERRO').length;
  const nAviso = ACHADOS.filter((a) => a.sev === 'AVISO').length;

  return (
    <div data-screen-label="Fiscal · Achados">
      <h2 className="step-title">Achados da validação</h2>
      <p className="step-sub">Inconsistências detectadas pelo motor de regras. Cada achado traz o registro, o campo e
        uma dica de correção. Erros bloqueiam a apuração; avisos são recomendações.</p>

      <div className="ach-filters">
        <div className="seg" role="tablist" aria-label="Filtro de severidade">
          <button className={sev === 'todos' ? 'on' : ''} onClick={() => setSev('todos')}>Todos · {ACHADOS.length}</button>
          <button className={sev === 'ERRO' ? 'on' : ''} onClick={() => setSev('ERRO')}>Erros · {nErro}</button>
          <button className={sev === 'AVISO' ? 'on' : ''} onClick={() => setSev('AVISO')}>Avisos · {nAviso}</button>
        </div>
      </div>

      {list.map((a) => (
        <div className={'ach-card ' + a.sev.toLowerCase()} key={a.id}>
          <div className="ach-top">
            <Badge kind={a.sev === 'ERRO' ? 'crit' : 'warn'} icon={a.sev === 'ERRO' ? 'alert' : 'info'}>{a.sev}</Badge>
            <Badge kind="mut">{a.regra}</Badge>
            <span className="ach-reg">{a.registro} · linha {fmtNum(a.linha)} · campo {a.campo}</span>
          </div>
          <div className="ach-desc">{a.desc}</div>
          <div className="ach-dica"><Icon name="spark" /><span>{a.dica}</span></div>
        </div>
      ))}

      <div className="step-foot">
        <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
          <b style={{ color: 'var(--crit)' }}>{nErro} erros</b> precisam de correção antes da apuração.
        </span>
        <div className="spacer"></div>
        <button className="btn-primary btn" onClick={onCorrigir}>
          <Icon name="edit" />Corrigir em lote (C170-CST)
        </button>
      </div>
    </div>
  );
}

/* ---------- 4 · Edição em lote (dry-run → aplicar → HITL) ---------- */
function LoteStep({ exigirHITL, onApplied }) {
  // phase: edit | preview | aguardando | aplicado
  const [phase, setPhase] = useStA('edit');
  const total = LOTE_REGISTROS.reduce((s, r) => s + r.vl, 0);

  const aplicar = () => {
    if (exigirHITL) setPhase('aguardando');
    else onApplied();
  };

  return (
    <div data-screen-label="Fiscal · Edição em lote">
      <h2 className="step-title">Edição em lote</h2>
      <p className="step-sub">Correção dos {LOTE_REGISTROS.length} registros C170 com CST 060 indevida. O <b>dry-run</b> simula
        o resultado e revalida antes de qualquer gravação.</p>

      {phase === 'preview' && (
        <div className="dryrun-banner">
          <Icon name="check" />
          <span><b>Dry-run concluído.</b> Revalidação simulada: o achado <span className="mono">E110-SALDO</span> deixa de
            ocorrer e o saldo de ICMS é recalculado para <b>{BRL(44640.43)}</b>. Nenhuma gravação feita ainda.</span>
        </div>
      )}

      {phase === 'aguardando' && (
        <div className="hitl-gate pending" role="status">
          <div className="hg-head"><Icon name="clock" />
            <span><b>Aguardando aprovação humana (HITL).</b> A edição em lote excede a faixa de autonomia e foi enviada
              para revisão de um auditor antes de gravar.</span>
          </div>
          <div className="hitl-steps">
            <div className="hitl-step done"><span className="hs-dot"><Icon name="check" /></span>Solicitado</div>
            <span className="hitl-conn"></span>
            <div className="hitl-step now"><span className="hs-dot"></span>Em revisão</div>
            <span className="hitl-conn"></span>
            <div className="hitl-step idle"><span className="hs-dot"></span>Aplicado</div>
          </div>
          <div className="hg-meta">PROTOCOLO HITL-2026.06.13-0098 · ENVIADO ÀS 14:32</div>
        </div>
      )}

      <div className="tbl-wrap">
        <table className="t2">
          <thead><tr>
            <th>Registro</th><th>Item</th><th>CST ICMS</th><th className="r">Valor</th>
          </tr></thead>
          <tbody>
            {LOTE_REGISTROS.map((r) => (
              <tr key={r.id}>
                <td className="mono">{r.registro} · {fmtNum(r.linha)}</td>
                <td>{r.item}</td>
                <td>
                  <span className="cst-from">{r.cst_atual}</span>
                  <span className="cst-arrow">→</span>
                  <span className="cst-to">{r.cst_novo}</span>
                </td>
                <td className="r num">{BRL(r.vl)}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 600 }}>
              <td colSpan={3}>Total de {LOTE_REGISTROS.length} registros</td>
              <td className="r num">{BRL(total)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="step-foot">
        {phase === 'aguardando' ? (
          <>
            <Badge kind="warn" dot>aguardando_aprovação</Badge>
            <div className="spacer"></div>
            <button className="btn btn-primary" onClick={onApplied}>
              <Icon name="shield" />Simular aprovação do auditor
            </button>
          </>
        ) : (
          <>
            <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
              {phase === 'edit' ? 'Revise as alterações e rode o dry-run.' : 'Resultado simulado acima.'}
              {exigirHITL && <> Esta ação exige aprovação HITL.</>}
            </span>
            <div className="spacer"></div>
            {phase === 'edit'
              ? <button className="btn" onClick={() => setPhase('preview')}><Icon name="compare" />Pré-visualizar (dry-run)</button>
              : <button className="btn" onClick={() => setPhase('edit')}><Icon name="edit" />Revisar</button>}
            <button className="btn btn-primary" disabled={phase !== 'preview'} onClick={aplicar}>
              <Icon name="check" />Aplicar correção
            </button>
          </>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { UploadStep, ProcessingStep, AchadosStep, LoteStep });
