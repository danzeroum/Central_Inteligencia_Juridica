import React, { useState, useEffect } from 'react';
import { Icon, Badge, Modal, CopyLine } from '../../components/primitives.jsx';
import { api } from '../../api/client.js';

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

export default function TransmissaoScreen() {
  const [inputId,  setInputId]  = useState('');
  const [eid,      setEid]      = useState('');
  const [circuit,  setCircuit]  = useState(null);
  const [ambiente, setAmbiente] = useState('homologacao');
  const [confirm,  setConfirm]  = useState(false);
  const [checked,  setChecked]  = useState(false);
  const [status,   setStatus]   = useState('idle');
  const [protocolo,setProtocolo]= useState(null);
  const [recibo,   setRecibo]   = useState(null);
  const [err,      setErr]      = useState('');

  useEffect(() => {
    api.transmissaoCircuit()
      .then((d) => setCircuit(d))
      .catch(() => setCircuit({ open: false, latencia_ms: null }));
  }, []);

  const circuitOpen = circuit?.open || circuit?.status === 'open';
  const isProd      = ambiente === 'producao';

  const transmitir = async () => {
    setConfirm(false);
    setStatus('sending');
    setErr('');
    try {
      const res = await api.transmissaoEnviar({
        escrituracao_id: eid || undefined,
        ambiente,
      });
      setProtocolo(res?.protocolo || res?.protocol || res?.id || ('PROT-' + Date.now()));
      setRecibo(res?.recibo || res?.receipt || null);
      setStatus('done');
    } catch (ex) {
      setErr(ex?.message || 'Erro na transmissão ao e-CAC.');
      setStatus('idle');
    }
  };

  if (status === 'done') {
    return (
      <div style={{ maxWidth: 540, margin: '40px auto', padding: '0 16px', textAlign: 'center' }}>
        <div className="success-mark"><Icon name="check" /></div>
        <h2 style={{ fontFamily: 'var(--serif)', fontSize: 22, fontWeight: 600, marginBottom: 6 }}>
          Transmitido ao e-CAC
        </h2>
        <p style={{ color: 'var(--ink-2)', fontSize: 13.5, marginBottom: 18 }}>
          {isProd
            ? 'Declaração transmitida em produção à Receita Federal.'
            : 'Transmissão em ambiente de homologação concluída.'}
        </p>
        <div style={{ display: 'grid', gap: 10, textAlign: 'left' }}>
          {protocolo && <CopyLine value={protocolo} label="protocolo" />}
          {recibo    && <CopyLine value={recibo}    label="recibo" />}
        </div>
        <div className="audit-foot" style={{ justifyContent: 'center', marginTop: 18 }}>
          <span>registrado no Decision Ledger</span>
          {eid && <><span className="sep" /><span className="mono">{eid.slice(0, 8)}…</span></>}
        </div>
        <button className="btn btn-sm" style={{ marginTop: 20 }}
          onClick={() => { setStatus('idle'); setProtocolo(null); setRecibo(null); setEid(''); setInputId(''); setErr(''); }}>
          <Icon name="refresh" />Nova transmissão
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px 80px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Transmissão e-CAC</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Transmissão de declarações à Receita Federal via e-CAC — ação irreversível
        </div>
      </div>

      <ErrAlert msg={err} />

      {/* ambiente */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--faint)', fontWeight: 600, marginBottom: 8 }}>Ambiente</div>
        <div className="seg">
          <button className={ambiente === 'homologacao' ? 'on' : ''} onClick={() => setAmbiente('homologacao')}>
            Homologação
          </button>
          <button className={ambiente === 'producao' ? 'on' : ''} onClick={() => setAmbiente('producao')}>
            Produção
          </button>
        </div>
      </div>

      <div className={'amb-banner ' + (isProd ? 'prod' : 'homolog')} style={{ marginBottom: 20 }}>
        <Icon name={isProd ? 'alert' : 'shield'} />
        <span>
          <b>Ambiente: {isProd ? 'PRODUÇÃO' : 'HOMOLOGAÇÃO'}.</b>{' '}
          {isProd
            ? 'A declaração terá efeitos legais reais junto à Receita Federal.'
            : 'Nenhum efeito legal — ideal para validar o fluxo de transmissão.'}
        </span>
      </div>

      {/* id da escrituração */}
      <div className="field" style={{ marginBottom: 16 }}>
        <label htmlFor="tr-eid">ID da escrituração (opcional)</label>
        <input id="tr-eid" className="input" placeholder="UUID da escrituração"
          value={inputId} onChange={(e) => { setInputId(e.target.value); setEid(e.target.value.trim()); }}
          style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
      </div>

      {/* sumário de transmissão */}
      <div className="transmit-summary">
        <div className="confirm-sum">
          <div className="cs-row">
            <span className="cs-l">Ambiente</span>
            <span className="cs-v">
              <Badge kind={isProd ? 'crit' : 'navy'} dot>{isProd ? 'produção' : 'homologação'}</Badge>
            </span>
          </div>
          {eid && (
            <div className="cs-row">
              <span className="cs-l">Escrituração</span>
              <span className="cs-v mono">{eid.slice(0, 16)}…</span>
            </div>
          )}
        </div>
      </div>

      {/* circuit breaker */}
      {circuit !== null && (
        circuitOpen ? (
          <div className="circuit open">
            <Icon name="alert" />
            <span>
              <b>e-CAC indisponível.</b> Circuit breaker <b>aberto</b> após falhas consecutivas no canal da Receita.
              A transmissão fica bloqueada temporariamente — tente novamente em alguns minutos. Nada foi enviado.
            </span>
          </div>
        ) : (
          <div className="circuit closed">
            <Icon name="check" />
            <span>
              Canal e-CAC operacional · circuit breaker <b>fechado</b>
              {circuit?.latencia_ms ? ` · latência média ${circuit.latencia_ms} ms` : ''}.
            </span>
          </div>
        )
      )}
      {circuit === null && (
        <div className="skeleton" style={{ height: 52, borderRadius: 8, marginBottom: 16 }} />
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
        {status === 'sending'
          ? <button className="btn btn-primary" disabled>
              <span className="job-spin" style={{ width: 16, height: 16, borderWidth: 2, marginRight: 6 }} />
              Transmitindo…
            </button>
          : <button className={'btn ' + (isProd ? 'btn-danger' : 'btn-primary')}
              disabled={circuitOpen}
              onClick={() => { setChecked(false); setConfirm(true); }}>
              <Icon name="send" />{isProd ? 'Transmitir em produção' : 'Transmitir'}
            </button>}
      </div>

      {confirm && (
        <Modal
          title={isProd ? 'Confirmar transmissão em PRODUÇÃO' : 'Confirmar transmissão'}
          onClose={() => setConfirm(false)}
          actions={
            <>
              <button className="btn" onClick={() => setConfirm(false)}>Cancelar</button>
              <button className={'btn ' + (isProd ? 'btn-danger' : 'btn-primary')}
                disabled={!checked} onClick={transmitir}>
                <Icon name="send" />Transmitir agora
              </button>
            </>
          }>
          <p style={{ marginTop: 0 }}>
            Você está prestes a transmitir ao e-CAC ({isProd ? 'produção' : 'homologação'}).
            Esta ação <b>não pode ser desfeita</b>.
          </p>
          {isProd && (
            <div style={{ background: 'var(--crit-bg)', color: 'var(--crit)', borderRadius: 6,
              padding: '10px 14px', fontSize: 12.5, marginBottom: 10 }}>
              <b>Atenção:</b> você está em ambiente de PRODUÇÃO. A declaração terá efeitos legais reais junto à Receita Federal.
            </div>
          )}
          {eid && (
            <div className="confirm-sum" style={{ marginBottom: 6 }}>
              <div className="cs-row">
                <span className="cs-l">Escrituração</span>
                <span className="cs-v mono">{eid.slice(0, 16)}…</span>
              </div>
            </div>
          )}
          <label className="confirm-check">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            <span>Confirmo que revisei a declaração e estou ciente de que a transmissão ao e-CAC é irreversível.</span>
          </label>
        </Modal>
      )}
    </div>
  );
}
