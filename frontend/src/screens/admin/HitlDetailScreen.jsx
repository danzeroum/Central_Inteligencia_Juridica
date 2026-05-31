import React, { useState } from 'react';
import { Icon } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';
import { store, humanizeAction, fmt } from '../../state.js';
import { operatorId } from '../../api/auth.js';

// CRÍTICO-10: operador derivado da sessão autenticada (não mais hardcoded).

// Editor estruturado que pré-preenche a ação proposta e envia `modifications`
// (encerra o alert "em desenvolvimento" — contrato já suportado pela API).
export default function HitlDetailScreen({ go }) {
  const toast = useToast();
  const req = store.selectedRequest;

  if (!req) {
    return (
      <div className="screen">
        <div className="empty"><Icon name="alert" /><div>Nenhuma solicitação selecionada.</div>
          <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={() => go('hitl')}>Voltar à fila</button>
        </div>
      </div>
    );
  }

  const h = humanizeAction(req);
  const action = req.action || {};
  const [form, setForm] = useState({
    type: action.type || 'peticionar',
    processo: action.processo || action.numero_processo || '',
    tribunal: action.tribunal || h.tribunal || '',
    deadline: action.deadline || '',
  });
  const [justify, setJustify] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (approved) => {
    if (!justify.trim()) { toast.error('A justificativa da modificação é obrigatória.'); return; }
    setBusy(true);
    try {
      await api.hitlDecision({
        request_id: req.request_id,
        approved,
        modifications: approved ? { ...action, ...form } : null,
        feedback: justify.trim(),
        operator_id: operatorId(),
      });
      toast.success(approved ? 'Ação modificada e aprovada.' : 'Solicitação rejeitada.');
      store.selectedRequest = null;
      go('hitl');
    } catch (e) {
      toast.error(`Falha ao registrar decisão: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <div className="screen-head">
        <button className="btn btn-ghost btn-sm" style={{ marginBottom: 12, paddingLeft: 0 }} onClick={() => go('hitl')}>
          <Icon name="chevron" style={{ width: 14, height: 14, transform: 'rotate(180deg)' }} /> Voltar à fila
        </button>
        <div className="screen-title">Modificar ação · #{req.request_id.slice(0, 8)}</div>
        <div className="screen-sub">Edite os parâmetros propostos pelo agente. Ao salvar, a ação modificada é enviada para execução com registro na trilha.</div>
      </div>
      <div className="grid2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Parâmetros da ação</div>
          <div className="field"><label>Tipo de ação</label>
            <select className="select" value={form.type} onChange={set('type')}>
              <option value="peticionar">Protocolar petição</option>
              <option value="process_query">Consultar processo</option>
              <option value="notificar">Notificar parte</option>
            </select>
          </div>
          <div className="field"><label>Processo</label><input className="input" value={form.processo} onChange={set('processo')} /></div>
          <div className="field"><label>Tribunal</label><input className="input" value={form.tribunal} onChange={set('tribunal')} /></div>
          <div className="field"><label>Prazo</label><input className="input" type="date" value={form.deadline} onChange={set('deadline')} /></div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Justificativa da modificação <span className="faint">(obrigatória)</span></label>
            <textarea className="textarea" rows="3" value={justify} onChange={(e) => setJustify(e.target.value)}
              placeholder="Descreva o que alterou e por quê — registrado na auditoria." />
          </div>
        </div>
        <div>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>Contexto do agente</div>
            <dl className="kv">
              <dt>Agente</dt><dd>{h.agentName}</dd>
              <dt>Confiança</dt><dd>{h.consensus != null ? fmt(h.consensus) : '—'}</dd>
              <dt>Autonomia</dt><dd>{h.autonomy || '—'}</dd>
            </dl>
            <div className="ap-why" style={{ marginTop: 16 }}><Icon name="alert" />{h.why}</div>
          </div>
          <div className="card">
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }} disabled={busy} onClick={() => submit(true)}>
                <Icon name="check" /> Salvar e aprovar
              </button>
              <button className="btn btn-danger" style={{ flex: 1, justifyContent: 'center' }} disabled={busy} onClick={() => submit(false)}>
                <Icon name="x" /> Rejeitar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
