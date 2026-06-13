/* fiscal-flow.jsx — shell do fio-de-ouro fiscal: sidebar + stepper + máquina de estados + Tweaks */

const { useState: useStF, useEffect: useEfF } = React;

const STEPS = [
  { id: 'upload', label: 'Upload', icon: 'attach' },
  { id: 'proc', label: 'Processando', icon: 'refresh' },
  { id: 'achados', label: 'Achados', icon: 'alert' },
  { id: 'lote', label: 'Edição em lote', icon: 'edit' },
  { id: 'apuracao', label: 'Apuração', icon: 'scale' },
  { id: 'retificacao', label: 'Retificação', icon: 'compare' },
  { id: 'perdcomp', label: 'PER/DCOMP', icon: 'doc' },
  { id: 'transmissao', label: 'Transmissão', icon: 'send' },
];

const TWEAK_DEFAULTS_FISCAL = /*EDITMODE-BEGIN*/{
  "density": "confortável",
  "cbSafe": false,
  "exigirHITL": true,
  "ambiente": "homologação",
  "circuitOpen": false
}/*EDITMODE-END*/;

function FiscalStepper({ step, maxStep, go }) {
  return (
    <div className="fstepper" role="list" aria-label="Etapas da escrituração">
      {STEPS.map((s, i) => {
        const cls = i < step ? 'done' : i === step ? 'now' : (i <= maxStep ? '' : 'locked');
        return (
          <button key={s.id} className={'fstep ' + cls} role="listitem"
            onClick={() => i <= maxStep && go(i)} disabled={i > maxStep}
            aria-current={i === step ? 'step' : undefined}>
            <span className="fs-conn"></span>
            <span className="fs-dot">{i < step ? <Icon name="check" /> : i + 1}</span>
            <span className="fs-lab">{s.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function EscBar() {
  const e = ESCRITURACAO;
  return (
    <div className="esc-bar">
      <div className="esc-glyph"><Icon name="doc" /></div>
      <div className="esc-meta">
        <div className="nm">{e.empresa}</div>
        <div className="sub">{e.cnpj_masked} · {e.uf} · {e.periodo} · {e.regime.replace('_', ' ')}</div>
      </div>
      <div className="esc-right">
        <Badge kind="mut">{e.db_id}</Badge>
        <Badge kind="navy" icon="lock">PII mascarada</Badge>
      </div>
    </div>
  );
}

function AppFiscal() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS_FISCAL);
  const [step, setStep] = useStF(() => Number(localStorage.getItem('fiscalStep') || 0));
  const [maxStep, setMaxStep] = useStF(() => Number(localStorage.getItem('fiscalMax') || 0));

  useEfF(() => {
    document.documentElement.setAttribute('data-density', t.density === 'compacto' ? 'compacto' : 'confortavel');
    document.documentElement.setAttribute('data-cb', t.cbSafe ? '1' : '0');
  }, [t.density, t.cbSafe]);

  useEfF(() => { localStorage.setItem('fiscalStep', step); localStorage.setItem('fiscalMax', maxStep); }, [step, maxStep]);

  const go = (i) => { setStep(i); setMaxStep((m) => Math.max(m, i)); document.getElementById('main')?.scrollTo(0, 0); };
  const next = () => go(step + 1);
  const reset = () => { setStep(0); setMaxStep(0); };

  const ambiente = t.ambiente === 'produção' ? 'producao' : 'homologacao';

  const content = (() => {
    switch (step) {
      case 0: return <UploadStep onSend={next} />;
      case 1: return <ProcessingStep onDone={next} />;
      case 2: return <AchadosStep onCorrigir={next} />;
      case 3: return <LoteStep exigirHITL={t.exigirHITL} onApplied={next} />;
      case 4: return <ApuracaoStep onNext={next} />;
      case 5: return <RetificacaoStep onNext={next} />;
      case 6: return <PerDcompStep onNext={next} />;
      case 7: return <TransmissaoStep circuitOpen={t.circuitOpen} ambiente={ambiente} />;
      default: return null;
    }
  })();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="scale" /></div>
          <div><div className="brand-name">Central Jurídica</div><div className="brand-sub">Engenharia Tributária</div></div>
        </div>
        <nav className="nav" aria-label="Navegação principal">
          <div className="nav-group">
            <div className="nav-group-label">Fiscal · fio-de-ouro</div>
            {STEPS.map((s, i) => (
              <button key={s.id} className={'nav-item' + (step === i ? ' active' : '')}
                onClick={() => i <= maxStep && go(i)} disabled={i > maxStep}
                style={i > maxStep ? { opacity: .45 } : null}>
                <Icon name={s.icon} className="nav-icon" />{s.label}
                {i < step && <Icon name="check" className="nav-icon" style={{ marginLeft: 'auto', color: 'var(--ok)' }} />}
                {i > maxStep && <Icon name="lock" className="nav-icon" style={{ marginLeft: 'auto' }} />}
              </button>
            ))}
          </div>
          <div className="nav-group" style={{ borderTop: '1px dashed var(--line)', paddingTop: 10 }}>
            <div className="nav-group-label">Fiscal · outras</div>
            <button className="nav-item" disabled style={{ opacity: .5 }}><Icon name="building" className="nav-icon" />Due Diligência</button>
            <button className="nav-item" disabled style={{ opacity: .5 }}><Icon name="spark" className="nav-icon" />Consultoria</button>
            <button className="nav-item" disabled style={{ opacity: .5 }}><Icon name="graph" className="nav-icon" />Analytics</button>
          </div>
        </nav>
        <div className="sidebar-foot">
          <button className="user-chip">
            <div className="avatar">CT</div>
            <div style={{ flex: 1 }}><div className="user-name">Carlos Tavares</div><div className="user-role">Contador · OPERATOR</div></div>
          </button>
        </div>
      </aside>

      <div className="content">
        <div className="topbar">
          <div className="crumb">
            <span>Fiscal</span><span className="sep">/</span>
            <span>Escrituração</span><span className="sep">/</span>
            <b>{STEPS[step].label}</b>
          </div>
          <div className="topbar-spacer"></div>
          <Badge kind={ambiente === 'producao' ? 'crit' : 'navy'} dot>{ambiente === 'producao' ? 'produção' : 'homologação'}</Badge>
          <button className="icon-btn" aria-label="Reiniciar fluxo" title="Reiniciar fluxo" onClick={reset}><Icon name="refresh" /></button>
          <button className="icon-btn" aria-label="Notificações"><Icon name="bell" /></button>
        </div>
        <div className="scroll" id="main">
          <div className="fiscal-screen">
            <FiscalStepper step={step} maxStep={maxStep} go={go} />
            {step >= 1 && <EscBar />}
            {content}
          </div>
        </div>
      </div>

      <TweaksPanel>
        <TweakSection label="Fluxo" />
        <TweakToggle label="Edição em lote exige HITL" value={t.exigirHITL} onChange={(v) => setTweak('exigirHITL', v)} />
        <TweakRadio label="Ambiente e-CAC" value={t.ambiente} options={['homologação', 'produção']} onChange={(v) => setTweak('ambiente', v)} />
        <TweakToggle label="Circuit breaker aberto" value={t.circuitOpen} onChange={(v) => setTweak('circuitOpen', v)} />
        <TweakSection label="Leitura" />
        <TweakRadio label="Densidade" value={t.density} options={['confortável', 'compacto']} onChange={(v) => setTweak('density', v)} />
        <TweakToggle label="Semáforo colorblind-safe" value={t.cbSafe} onChange={(v) => setTweak('cbSafe', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<AppFiscal />);
