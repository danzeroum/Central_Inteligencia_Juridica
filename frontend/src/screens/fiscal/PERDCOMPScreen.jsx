import React, { useState, useEffect } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { api } from '../../api/client.js';

const BRL = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

const TIPOS_FALLBACK = [
  { id: 'per',              nome: 'PER',              desc: 'Pedido de Ressarcimento — solicita a restituição do crédito em dinheiro' },
  { id: 'dcomp',            nome: 'DCOMP',            desc: 'Declaração de Compensação — compensa o crédito com débitos tributários' },
  { id: 'ressarcimento_ipi',nome: 'Ressarcimento IPI',desc: 'Ressarcimento de créditos de IPI acumulados na cadeia produtiva' },
];

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

export default function PERDCOMPScreen() {
  const [inputId, setInputId] = useState('');
  const [eid,     setEid]     = useState('');
  const [tipos,   setTipos]   = useState(null);
  const [tipo,    setTipo]    = useState('dcomp');
  const [ficha,   setFicha]   = useState(null);
  const [busy,    setBusy]    = useState(false);
  const [err,     setErr]     = useState('');

  useEffect(() => {
    api.perDcompTipos()
      .then((d) => setTipos(d.tipos || (Array.isArray(d) ? d : TIPOS_FALLBACK)))
      .catch(() => setTipos(TIPOS_FALLBACK));
  }, []);

  const gerarFicha = async (e) => {
    e.preventDefault();
    const id = inputId.trim() || eid;
    if (!id) { setErr('Informe o ID da escrituração.'); return; }
    setEid(id);
    setBusy(true);
    setErr('');
    setFicha(null);
    try {
      const res = await api.perDcompGerar({ escrituracao_id: id, tipo });
      setFicha(res);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao gerar ficha PER/DCOMP.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px 80px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>PER/DCOMP</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Geração e validação de Pedido de Ressarcimento e Declaração de Compensação
        </div>
      </div>

      <ErrAlert msg={err} />

      <form onSubmit={gerarFicha}>
        <div className="field" style={{ marginBottom: 16 }}>
          <label htmlFor="pd-eid">ID da escrituração</label>
          <input id="pd-eid" className="input" placeholder="UUID da escrituração apurada"
            value={inputId} onChange={(e) => setInputId(e.target.value)}
            style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
        </div>

        <div style={{ marginBottom: 18 }}>
          <label style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 10, display: 'block', fontWeight: 600 }}>
            Tipo de documento
          </label>
          <div className="type-grid">
            {(tipos || TIPOS_FALLBACK).map((tp) => (
              <button type="button" key={tp.id}
                className={'type-opt' + (tipo === tp.id ? ' sel' : '')}
                onClick={() => { setTipo(tp.id); setFicha(null); }}>
                <span className="type-radio" />
                <span>
                  <span className="to-nm">{tp.nome}</span>
                  <span className="to-desc">{tp.desc}</span>
                </span>
              </button>
            ))}
          </div>
        </div>

        {!ficha && (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              <Icon name="doc" />{busy ? 'Gerando…' : 'Gerar de apuração'}
            </button>
          </div>
        )}
      </form>

      {ficha && (
        <>
          <div className="ficha">
            <div className="ficha-head">
              <div className="fc-glyph-sm"><Icon name="doc" /></div>
              <div className="ft">{ficha.tipo || tipo.toUpperCase()}</div>
              <Badge kind="ok" icon="check">layout válido</Badge>
              <div style={{ marginLeft: 'auto' }}>
                <button className="btn btn-sm" onClick={() => { setFicha(null); setErr(''); }}>
                  <Icon name="refresh" style={{ width: 13, height: 13 }} /> Nova geração
                </button>
              </div>
            </div>
            <div className="ficha-body">
              <dl className="kv">
                <dt>Número</dt>
                <dd className="mono">{ficha.numero || ficha.id || '—'}</dd>
                <dt>Período</dt>
                <dd className="mono">{ficha.periodo || ficha.periodo_competencia || '—'}</dd>
                <dt>Origem do crédito</dt>
                <dd>{ficha.origem || ficha.tipo_credito || '—'}</dd>
                <dt>Crédito original</dt>
                <dd className="mono">{BRL(ficha.credito || ficha.valor_credito || 0)}</dd>
                {ficha.selic != null && (
                  <>
                    <dt>Selic acumulada</dt>
                    <dd className="mono">{BRL(ficha.selic)}</dd>
                  </>
                )}
                {ficha.debito_compensado && (
                  <>
                    <dt>Débito a compensar</dt>
                    <dd>{ficha.debito_compensado}</dd>
                  </>
                )}
                <dt>Situação</dt>
                <dd><Badge kind="mut">{ficha.situacao || 'em_elaboracao'}</Badge></dd>
              </dl>
              {(ficha.total || ficha.valor_total) && (
                <div className="ficha-total">
                  <span className="tl">Crédito total atualizado</span>
                  <span className="tv">{BRL(ficha.total || ficha.valor_total)}</span>
                </div>
              )}
            </div>
          </div>

          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button className="btn" onClick={async () => {
              try { await api.perDcompValidar({ numero: ficha.numero, escrituracao_id: eid }); }
              catch { /* ignore, already validated */ }
            }}>
              <Icon name="check" />Revalidar layout
            </button>
          </div>
          <div style={{ marginTop: 10, padding: '10px 14px', background: 'var(--navy-tint)', borderRadius: 8,
            fontSize: 12.5, color: 'var(--navy)' }}>
            <Icon name="info" style={{ width: 14, height: 14, marginRight: 6, verticalAlign: 'middle' }} />
            Ficha gerada com sucesso. Para transmitir, acesse <b>Transmissão e-CAC</b> na barra lateral.
          </div>
        </>
      )}
    </div>
  );
}
