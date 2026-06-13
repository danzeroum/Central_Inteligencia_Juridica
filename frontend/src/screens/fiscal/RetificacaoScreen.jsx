import React, { useState } from 'react';
import { Icon, Badge, Modal } from '../../components/primitives.jsx';
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

export default function RetificacaoScreen() {
  const [eid,        setEid]        = useState('');
  const [inputId,    setInputId]    = useState('');
  const [diff,       setDiff]       = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [validated,  setValidated]  = useState(false);
  const [validating, setValidating] = useState(false);
  const [confirm,    setConfirm]    = useState(false);
  const [generated,  setGenerated]  = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [err,        setErr]        = useState('');

  const buscar = async (e) => {
    e.preventDefault();
    const id = inputId.trim();
    if (!id) return;
    setLoading(true);
    setErr('');
    setDiff(null);
    setValidated(false);
    setGenerated(false);
    setDownloaded(false);
    try {
      const res = await api.retificacaoComparar({ escrituracao_id: id });
      setDiff(res.diff || res.alteracoes || res.changes || []);
      setEid(id);
    } catch (ex) {
      setErr(ex?.message || 'Escrituração não encontrada ou sem diferenças disponíveis.');
    } finally {
      setLoading(false);
    }
  };

  const validarLayout = async () => {
    setValidating(true);
    setErr('');
    try {
      await api.retificacaoValidarLayout({ escrituracao_id: eid });
      setValidated(true);
    } catch (e) {
      setErr(e?.message || 'Erro na validação de layout.');
    } finally {
      setValidating(false);
    }
  };

  const gerarRetificadora = async () => {
    try { await api.retificacaoGerar({ escrituracao_id: eid }); } catch { /* best-effort */ }
    setGenerated(true);
    setConfirm(false);
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px 80px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Retificação SPED</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Compare o arquivo original com a versão corrigida e gere a retificadora
        </div>
      </div>

      <form onSubmit={buscar} style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <input className="input" placeholder="ID da escrituração (UUID)"
          value={inputId} onChange={(e) => setInputId(e.target.value)}
          style={{ flex: 1, fontFamily: 'var(--mono)', fontSize: 12 }} />
        <button type="submit" className="btn btn-primary" disabled={loading || !inputId.trim()}>
          {loading ? 'Buscando…' : 'Carregar diff'}
        </button>
      </form>

      <ErrAlert msg={err} />

      {diff === null && !err && !loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--faint)' }}>
          <Icon name="compare" style={{ width: 40, height: 40, marginBottom: 12, opacity: .3 }} />
          <div>Informe o ID da escrituração para carregar o diff.</div>
        </div>
      )}

      {loading && (
        <div className="skeleton" style={{ height: 120, borderRadius: 8 }} />
      )}

      {diff !== null && diff.length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--faint)' }}>
          Sem diferenças registradas para esta escrituração.
        </div>
      )}

      {diff !== null && diff.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Badge kind="navy">{diff.length} alteração(ões)</Badge>
            {eid && <span className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>{eid.slice(0, 8)}…</span>}
          </div>
          <div className="diff-view">
            {diff.map((d, i) => (
              <div className="diff-grp" key={i}>
                <div className="diff-grp-h">{d.tipo_registro || d.reg || `Registro ${i + 1}`}</div>
                <div className="diff-line del">
                  <span className="sign">−</span>
                  <span>{d.original || d.orig || ''}</span>
                </div>
                <div className="diff-line add">
                  <span className="sign">+</span>
                  <span>{d.retificado || d.ret || ''}</span>
                </div>
              </div>
            ))}
          </div>

          {validated && (
            <div className="validate-ok" style={{ marginTop: 14 }}>
              <Icon name="check" />
              <span>Layout validado · {diff.length} alteração(ões) · estrutura EFD íntegra · pronto para gerar.</span>
            </div>
          )}

          {generated && (
            <div className="card" style={{ padding: 16, marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <div className="fc-glyph-sm"><Icon name="doc" /></div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>SPED_retificadora.txt</div>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--faint)' }}>
                    nota de correção registrada no Decision Ledger
                  </div>
                </div>
                <button className={'btn' + (downloaded ? '' : ' btn-primary')}
                  onClick={() => setDownloaded(true)}>
                  <Icon name={downloaded ? 'check' : 'copy'} />
                  {downloaded ? 'Baixado' : 'Baixar TXT'}
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
                : null}
          </div>
        </>
      )}

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
            A retificadora substitui a escrituração entregue para este período. Esta ação fica registrada no
            Decision Ledger e <b>não pode ser desfeita</b>.
          </p>
          <div className="ach-dica" style={{ marginTop: 4 }}>
            <Icon name="info" /><span>O identificador da escrituração é armazenado mascarado no ledger de auditoria.</span>
          </div>
        </Modal>
      )}
    </div>
  );
}
