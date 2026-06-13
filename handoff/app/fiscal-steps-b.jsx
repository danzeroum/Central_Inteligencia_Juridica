/* fiscal-steps-b.jsx — etapas 5–8: Apuração · Retificação · PER/DCOMP · Transmissão e-CAC */

const { useState: useStB } = React;

const SIT = { devedor: ['crit', 'devedor'], credor: ['ok', 'credor'], equilibrado: ['mut', 'equilibrado'] };

/* ---------- 5 · Apuração ---------- */
function ApuracaoStep({ onNext }) {
  const totalDev = APURACAO.filter((a) => a.sit === 'devedor').reduce((s, a) => s + a.saldo, 0);
  return (
    <div data-screen-label="Fiscal · Apuração">
      <h2 className="step-title">Apuração por tributo</h2>
      <p className="step-sub">Débitos, créditos, ajustes e saldo de cada tributo, com a situação resultante. Divergências
        entre o valor computado e o declarado na escrituração ficam em destaque.</p>

      <div className="apur-grid">
        {APURACAO.map((a) => {
          const [kind, label] = SIT[a.sit];
          const diverg = a.computado !== a.declarado;
          return (
            <div className="apur-card" key={a.trib}>
              <div className="apur-head">
                <span className="apur-trib">{a.trib}</span>
                <span className="apur-reg">{a.reg}</span>
                <div className="apur-saldo">
                  <div className="l">saldo</div>
                  <div className="v" style={{ color: kind === 'crit' ? 'var(--crit)' : kind === 'ok' ? 'var(--ok)' : 'var(--ink)' }}>{BRL(a.saldo)}</div>
                </div>
                <Badge kind={kind} dot>{label}</Badge>
              </div>
              <div className="apur-body">
                <div className="apur-cell"><div className="cl">Débitos</div><div className="cv">{BRL(a.deb)}</div></div>
                <div className="apur-cell"><div className="cl">Créditos</div><div className="cv">{BRL(a.cred)}</div></div>
                <div className="apur-cell"><div className="cl">Ajustes</div><div className="cv">{a.ajuste ? BRL(a.ajuste) : '—'}</div></div>
              </div>
              {diverg && (
                <div className="apur-diverg">
                  <Icon name="alert" />
                  <span>Divergência computado × declarado: <span className="mono">{BRL(a.computado)}</span> vs
                    <span className="mono"> {BRL(a.declarado)}</span> — revisar antes de retificar.</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="step-foot">
        <span className="step-sub" style={{ margin: 0, fontSize: 12.5 }}>
          Saldo devedor consolidado: <b className="mono">{BRL(totalDev)}</b> · crédito de IPI: <b className="mono">{BRL(2810.50)}</b>
        </span>
        <div className="spacer"></div>
        <button className="btn-primary btn" onClick={onNext}><Icon name="compare" />Gerar retificação</button>
      </div>
    </div>
  );
}

/* ---------- 6 · Retificação ---------- */
function RetificacaoStep({ onNext }) {
  const [validated, setValidated] = useStB(false);
  const [confirm, setConfirm] = useStB(false);
  const [generated, setGenerated] = useStB(false);
  const [downloaded, setDownloaded] = useStB(false);

  return (
    <div data-screen-label="Fiscal · Retificação">
      <h2 className="step-title">Retificação da escrituração</h2>
      <p className="step-sub">Comparação do arquivo original com a versão corrigida. Gerar a retificadora é um <b>ato formal</b> —
        confirme antes de prosseguir.</p>

      <div className="diff-view">
        {DIFF.map((d, i) => (
          <div className="diff-grp" key={i}>
            <div className="diff-grp-h">{d.reg}</div>
            <div className="diff-line del"><span className="sign">−</span><span>{d.orig}</span></div>
            <div className="diff-line add"><span className="sign">+</span><span>{d.ret}</span></div>
          </div>
        ))}
      </div>

      {validated && (
        <div className="validate-ok"><Icon name="check" />
          <span>Layout validado · 4 alterações · estrutura EFD íntegra · pronto para gerar a retificadora.</span>
        </div>
      )}

      {generated && (
        <div className="card" style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div className="fc-glyph" style={{ width: 38, height: 38, borderRadius: 9, background: 'var(--navy-tint)', color: 'var(--navy)', display: 'grid', placeItems: 'center' }}><Icon name="doc" /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>SPED_122025_retificadora.txt</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--faint)' }}>84,2 MB · nota de correção registrada</div>
            </div>
            <button className={'btn' + (downloaded ? '' : ' btn-primary')} onClick={() => setDownloaded(true)}>
              <Icon name={downloaded ? 'check' : 'copy'} />{downloaded ? 'Baixado' : 'Baixar TXT'}
            </button>
          </div>
        </div>
      )}

      <div className="step-foot">
        <div className="spacer"></div>
        {!validated
          ? <button className="btn" onClick={() => setValidated(true)}><Icon name="check" />Validar layout</button>
          : !generated
            ? <button className="btn-danger btn" onClick={() => setConfirm(true)}><Icon name="alert" />Gerar retificadora</button>
            : <button className="btn-primary btn" onClick={onNext}><Icon name="chevron" />Avançar para PER/DCOMP</button>}
      </div>

      {confirm && (
        <Modal title="Gerar escrituração retificadora?"
          onClose={() => setConfirm(false)}
          actions={<>
            <button className="btn" onClick={() => setConfirm(false)}>Cancelar</button>
            <button className="btn-danger btn" onClick={() => { setGenerated(true); setConfirm(false); }}>
              <Icon name="check" />Confirmar e gerar
            </button>
          </>}>
          <p style={{ marginTop: 0 }}>A retificadora substitui a escrituração entregue para o período <b>{ESCRITURACAO.periodo}</b>.
            Será registrada uma nota de correção e o saldo de ICMS passará a <b>{BRL(44640.43)}</b>.</p>
          <div className="ach-dica" style={{ marginTop: 4 }}><Icon name="info" />
            <span>Esta ação fica registrada no Decision Ledger com o identificador da escrituração mascarado.</span>
          </div>
        </Modal>
      )}
    </div>
  );
}

/* ---------- 7 · PER/DCOMP ---------- */
function PerDcompStep({ onNext }) {
  const [tipo, setTipo] = useStB('dcomp');
  const [generated, setGenerated] = useStB(false);
  const f = PERDCOMP_FICHA;

  return (
    <div data-screen-label="Fiscal · PER/DCOMP">
      <h2 className="step-title">PER/DCOMP</h2>
      <p className="step-sub">Aproveite o crédito apurado de IPI ({BRL(2810.50)}). Escolha o tipo, gere a partir da apuração
        e valide o layout antes de transmitir.</p>

      <div className="type-grid">
        {PERDCOMP_TIPOS.map((tp) => (
          <button key={tp.id} className={'type-opt' + (tipo === tp.id ? ' sel' : '')} onClick={() => { setTipo(tp.id); setGenerated(false); }}>
            <span className="type-radio"></span>
            <span><span className="to-nm">{tp.nome}</span><span className="to-desc">{tp.desc}</span></span>
          </button>
        ))}
      </div>

      {!generated ? (
        <div className="step-foot">
          <div className="spacer"></div>
          <button className="btn-primary btn" onClick={() => setGenerated(true)}><Icon name="doc" />Gerar de apuração</button>
        </div>
      ) : (
        <>
          <div className="ficha">
            <div className="ficha-head">
              <div className="fc-glyph" style={{ width: 34, height: 34, borderRadius: 8, background: 'var(--navy-tint)', color: 'var(--navy)', display: 'grid', placeItems: 'center' }}><Icon name="doc" /></div>
              <div className="ft">{f.tipo}</div>
              <Badge kind="ok" icon="check" >layout válido</Badge>
            </div>
            <div className="ficha-body">
              <dl className="kv">
                <dt>Número</dt><dd className="mono">{f.numero}</dd>
                <dt>Período</dt><dd className="mono">{f.periodo}</dd>
                <dt>Origem do crédito</dt><dd>{f.origem}</dd>
                <dt>Crédito original</dt><dd className="mono">{BRL(f.credito)}</dd>
                <dt>Selic acumulada</dt><dd className="mono">{BRL(f.selic)}</dd>
                <dt>Débito a compensar</dt><dd>{f.debito_compensado}</dd>
                <dt>Situação</dt><dd><Badge kind="mut">{f.situacao}</Badge></dd>
              </dl>
              <div className="ficha-total">
                <span className="tl">Crédito total atualizado</span>
                <span className="tv">{BRL(f.total)}</span>
              </div>
            </div>
          </div>
          <div className="step-foot">
            <div className="spacer"></div>
            <button className="btn-primary btn" onClick={onNext}><Icon name="send" />Transmitir ao e-CAC</button>
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- 8 · Transmissão e-CAC ---------- */
function TransmissaoStep({ circuitOpen, ambiente }) {
  const [confirm, setConfirm] = useStB(false);
  const [checked, setChecked] = useStB(false);
  const [status, setStatus] = useStB('idle'); // idle | sending | done
  const isProd = ambiente === 'producao';
  const f = PERDCOMP_FICHA;

  const transmitir = () => {
    setConfirm(false);
    setStatus('sending');
    setTimeout(() => setStatus('done'), 2600);
  };

  if (status === 'done') {
    return (
      <div data-screen-label="Fiscal · Transmissão concluída" style={{ textAlign: 'center', maxWidth: 520, margin: '20px auto' }}>
        <div className="success-mark"><Icon name="check" /></div>
        <h2 className="step-title" style={{ marginBottom: 6 }}>Transmitido ao e-CAC</h2>
        <p className="step-sub" style={{ margin: '0 auto 18px' }}>
          {isProd ? 'Declaração transmitida em produção à Receita Federal.' : 'Transmissão em ambiente de homologação concluída.'}
        </p>
        <div style={{ display: 'grid', gap: 10, textAlign: 'left' }}>
          <CopyLine value={isProd ? '2026.06.13.PRD.0093124' : TRANSMISSAO.protocolo} label="protocolo" />
          <CopyLine value="RECIBO 41028.92831.130626.1.3.04-9920" label="recibo" />
        </div>
        <div className="audit-foot" style={{ justifyContent: 'center', marginTop: 18 }}>
          <span>query_id 7c1a..f93</span><span className="sep"></span>
          <span>registrado no Decision Ledger</span><span className="sep"></span>
          <span>{ESCRITURACAO.cnpj_masked}</span>
        </div>
      </div>
    );
  }

  return (
    <div data-screen-label="Fiscal · Transmissão e-CAC">
      <h2 className="step-title">Transmissão ao e-CAC</h2>
      <p className="step-sub">Ação <b>irreversível</b> e federal. Confira o resumo, o ambiente e o estado do canal antes de transmitir.</p>

      <div className={'amb-banner ' + (isProd ? 'prod' : 'homolog')}>
        <Icon name={isProd ? 'alert' : 'shield'} />
        <span><b>Ambiente: {isProd ? 'PRODUÇÃO' : 'HOMOLOGAÇÃO'}.</b>{' '}
          {isProd ? 'A declaração terá efeitos legais reais junto à Receita.' : 'Nenhum efeito legal — ideal para validar o fluxo.'}</span>
      </div>

      <div className="transmit-summary">
        <div className="confirm-sum">
          <div className="cs-row"><span className="cs-l">Documento</span><span className="cs-v">{f.tipo.split('—')[0].trim()}</span></div>
          <div className="cs-row"><span className="cs-l">Número</span><span className="cs-v">{f.numero}</span></div>
          <div className="cs-row"><span className="cs-l">Período</span><span className="cs-v">{f.periodo}</span></div>
          <div className="cs-row"><span className="cs-l">Crédito total</span><span className="cs-v">{BRL(f.total)}</span></div>
          <div className="cs-row"><span className="cs-l">Contribuinte</span><span className="cs-v">{ESCRITURACAO.cnpj_masked}</span></div>
        </div>
      </div>

      {circuitOpen ? (
        <div className="circuit open">
          <Icon name="alert" />
          <span><b>e-CAC indisponível.</b> O circuit breaker está <b>aberto</b> após falhas consecutivas no canal da Receita.
            A transmissão fica bloqueada temporariamente — tente novamente em alguns minutos. Nada foi enviado.</span>
        </div>
      ) : (
        <div className="circuit closed">
          <Icon name="check" />
          <span>Canal e-CAC operacional · circuit breaker <b>fechado</b> · latência média 480&nbsp;ms.</span>
        </div>
      )}

      <div className="step-foot">
        <div className="spacer"></div>
        {status === 'sending'
          ? <button className="btn-primary btn" disabled><span className="job-spin" style={{ width: 16, height: 16, borderWidth: 2, marginRight: 6 }}></span>Transmitindo…</button>
          : <button className={'btn ' + (isProd ? 'btn-danger' : 'btn-primary')} disabled={circuitOpen} onClick={() => { setChecked(false); setConfirm(true); }}>
              <Icon name="send" />Transmitir{isProd ? ' em produção' : ''}
            </button>}
      </div>

      {confirm && (
        <Modal title={isProd ? 'Confirmar transmissão em PRODUÇÃO' : 'Confirmar transmissão'}
          onClose={() => setConfirm(false)}
          actions={<>
            <button className="btn" onClick={() => setConfirm(false)}>Cancelar</button>
            <button className={'btn ' + (isProd ? 'btn-danger' : 'btn-primary')} disabled={!checked} onClick={transmitir}>
              <Icon name="send" />Transmitir agora
            </button>
          </>}>
          <p style={{ marginTop: 0 }}>Você está prestes a transmitir o documento <b>{f.numero}</b> ao e-CAC
            ({isProd ? 'produção' : 'homologação'}). Esta ação <b>não pode ser desfeita</b>.</p>
          <div className="confirm-sum">
            <div className="cs-row"><span className="cs-l">Crédito total</span><span className="cs-v">{BRL(f.total)}</span></div>
            <div className="cs-row"><span className="cs-l">Período</span><span className="cs-v">{f.periodo}</span></div>
          </div>
          <label className="confirm-check">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            <span>Confirmo que revisei a declaração e estou ciente de que a transmissão ao e-CAC é irreversível.</span>
          </label>
        </Modal>
      )}
    </div>
  );
}

Object.assign(window, { ApuracaoStep, RetificacaoStep, PerDcompStep, TransmissaoStep });
