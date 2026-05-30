import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Icon, Badge, Stat, Modal } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';
import { connectHitl } from '../../api/hitlSocket.js';
import { store, humanizeAction, fmt } from '../../state.js';

const OPERATOR_ID = 'm.ribeiro';
const UNDO_MS = 6000;

function ApprovalCard({ req, focused, onApprove, onReject, onModify, cardRef }) {
  const h = humanizeAction(req);
  const [armed, setArmed] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  return (
    <article
      ref={cardRef}
      tabIndex={0}
      className={`approval ${h.critical ? 'crit' : ''}`}
      role="region"
      aria-label={`Solicitação de aprovação ${req.request_id.slice(0, 8)}`}
      style={focused ? { boxShadow: '0 0 0 2px var(--navy)' } : undefined}
    >
      <div className="ap-head">
        <div className="ap-agent">
          <div className="ap-icon">{(h.tribunal || h.agentName || '?').slice(0, 2).toUpperCase()}</div>
          <div>
            <div className="ap-title">{h.agentName}{h.tribunal ? ` · ${h.tribunal}` : ''}</div>
            <div className="ap-sub">#{req.request_id.slice(0, 8)} · {h.consensus != null ? `confiança ${fmt(h.consensus)}` : 'pendente'}</div>
          </div>
        </div>
        <div className="ap-badges">
          {h.critical ? <Badge kind="crit" dot>Crítico · irreversível</Badge> : <Badge kind="warn" dot>Atenção</Badge>}
          <Badge kind="mut">Pendente</Badge>
        </div>
      </div>
      <div className="ap-body">
        <dl className="kv">
          <dt>Ação</dt><dd><b>{h.label}</b></dd>
          <dt>Alvo</dt><dd>{h.target}</dd>
          {h.autonomy && (<><dt>Autonomia</dt><dd>{h.autonomy}</dd></>)}
        </dl>
        <div className="ap-why"><Icon name="alert" />{h.why}</div>
        <div className="ap-raw" role="button" tabIndex={0} onClick={() => setShowRaw((v) => !v)}
          onKeyDown={(e) => e.key === 'Enter' && setShowRaw((v) => !v)}>
          <Icon name="chevron" style={{ width: 13, height: 13, transform: showRaw ? 'rotate(90deg)' : 'none' }} />
          {showRaw ? 'Ocultar' : 'Ver'} payload técnico (JSON)
        </div>
        {showRaw && (
          <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, marginTop: 8, overflowX: 'auto' }}>
            {JSON.stringify(req.action, null, 2)}
          </pre>
        )}
        {h.critical && (
          <label style={{ display: 'flex', gap: 9, alignItems: 'center', marginTop: 14, fontSize: 12.5, color: 'var(--crit)', fontWeight: 600 }}>
            <input type="checkbox" checked={armed} onChange={(e) => setArmed(e.target.checked)} />
            Revisei o conteúdo anexo e confirmo que esta ação tem efeito processual.
          </label>
        )}
      </div>
      <div className="ap-actions">
        <button className="btn btn-primary" disabled={h.critical && !armed} onClick={() => onApprove(req, h)}>
          <Icon name="check" /> {h.critical ? 'Revisei — Aprovar' : 'Aprovar'} <span className="kbd">A</span>
        </button>
        <button className="btn" onClick={() => onModify(req)}><Icon name="edit" /> Modificar <span className="kbd">M</span></button>
        <button className="btn btn-danger" onClick={() => onReject(req, h)}><Icon name="x" /> Rejeitar <span className="kbd">R</span></button>
      </div>
    </article>
  );
}

export default function HitlScreen({ go, onPendingChange }) {
  const toast = useToast();
  const [list, setList] = useState([]);
  const [stats, setStats] = useState({ pending: 0, approved_today: 0, rejected_today: 0 });
  const [filter, setFilter] = useState('todas');
  const [wsStatus, setWsStatus] = useState('connecting');
  const [focusIdx, setFocusIdx] = useState(0);
  const [reject, setReject] = useState(null); // {req, h}
  const [rejectText, setRejectText] = useState('');
  const cardRefs = useRef({});
  const pendingUndo = useRef({}); // request_id -> timeout

  const refresh = useCallback(async () => {
    try {
      const [pend, st] = await Promise.all([api.hitlPending(), api.hitlStats()]);
      setList(pend.requests || []);
      setStats(st);
    } catch (e) {
      toast.error(`Não foi possível carregar a fila: ${e.message}`, { label: 'Tentar de novo', onClick: refresh });
    }
  }, [toast]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    const disconnect = connectHitl({
      onStatus: setWsStatus,
      onEvent: (evt) => {
        if (evt.event === 'new_request' || evt.event === 'pending_request') {
          setList((l) => (l.some((r) => r.request_id === evt.data.request_id) ? l : [...l, evt.data]));
        } else if (evt.event === 'decision_made') {
          setList((l) => l.filter((r) => r.request_id !== evt.data.request_id));
        }
      },
    });
    return disconnect;
  }, []);

  useEffect(() => { onPendingChange?.(list.length); }, [list.length, onPendingChange]);

  const shown = filter === 'criticas' ? list.filter((r) => humanizeAction(r).critical) : list;

  const sendDecision = useCallback(async (req, { approved, feedback }) => {
    try {
      await api.hitlDecision({ request_id: req.request_id, approved, feedback, operator_id: OPERATOR_ID });
      setList((l) => l.filter((r) => r.request_id !== req.request_id));
      setStats((s) => approved ? { ...s, approved_today: s.approved_today + 1 } : { ...s, rejected_today: s.rejected_today + 1 });
    } catch (e) {
      toast.error(`Falha ao registrar decisão: ${e.message}`);
      refresh();
    }
  }, [toast, refresh]);

  // Aprovação: crítica exige checkbox (já feito) + sem desfazer; comum ganha janela de desfazer.
  const onApprove = useCallback((req, h) => {
    if (h.critical) { sendDecision(req, { approved: true }); return; }
    setList((l) => l.filter((r) => r.request_id !== req.request_id)); // remove otimista
    const id = toast.push({
      kind: 'info',
      message: `Aprovação de "${h.label}" em ${UNDO_MS / 1000}s…`,
      action: { label: 'Desfazer', onClick: () => { clearTimeout(pendingUndo.current[req.request_id]); delete pendingUndo.current[req.request_id]; setList((l) => [...l, req]); } },
    });
    pendingUndo.current[req.request_id] = setTimeout(() => {
      delete pendingUndo.current[req.request_id];
      sendDecision(req, { approved: true });
    }, UNDO_MS);
  }, [sendDecision, toast]);

  const onReject = useCallback((req, h) => { setReject({ req, h }); setRejectText(''); }, []);
  const confirmReject = () => {
    if (reject.h.critical && !rejectText.trim()) return;
    sendDecision(reject.req, { approved: false, feedback: rejectText.trim() || null });
    setReject(null);
  };

  const onModify = useCallback((req) => { store.selectedRequest = req; go('hitl-detail'); }, [go]);

  // Atalhos de teclado A/R/M no card em foco; J/K navegam.
  useEffect(() => {
    const handler = (e) => {
      if (reject) return;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
      const req = shown[focusIdx];
      if (e.key === 'j' || e.key === 'ArrowDown') { setFocusIdx((i) => Math.min(i + 1, shown.length - 1)); e.preventDefault(); }
      else if (e.key === 'k' || e.key === 'ArrowUp') { setFocusIdx((i) => Math.max(i - 1, 0)); e.preventDefault(); }
      else if (req && (e.key === 'a' || e.key === 'A')) onApprove(req, humanizeAction(req));
      else if (req && (e.key === 'r' || e.key === 'R')) onReject(req, humanizeAction(req));
      else if (req && (e.key === 'm' || e.key === 'M')) onModify(req);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shown, focusIdx, reject, onApprove, onReject, onModify]);

  useEffect(() => { cardRefs.current[focusIdx]?.focus?.(); }, [focusIdx, shown.length]);

  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Aprovações · Human-in-the-Loop</div>
        <div className="screen-sub">Fila em tempo real. Ações sensíveis dos agentes aguardam sua decisão antes de serem executadas.</div>
      </div>
      <div className="q-stats">
        <Stat label="Pendentes" value={list.length} />
        <Stat label="Aprovadas (hoje)" value={stats.approved_today} />
        <Stat label="Rejeitadas (hoje)" value={stats.rejected_today} />
        <Stat label="Conexão" value={wsStatus === 'connected' ? 'ao vivo' : 'reconectando'} />
      </div>
      <div className="card-head" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {['todas', 'criticas'].map((f) => (
            <button key={f} className={filter === f ? 'chip' : 'chip chip-out'} onClick={() => setFilter(f)}>
              {f === 'todas' ? 'Todas' : 'Apenas críticas'}
            </button>
          ))}
        </div>
        <div className="muted" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="dot" style={{ width: 7, height: 7, borderRadius: '50%', background: wsStatus === 'connected' ? 'var(--ok)' : 'var(--warn)', display: 'inline-block' }} />
          {wsStatus === 'connected' ? 'WebSocket conectado · anúncio por leitor de tela ativo' : 'Reconectando ao servidor…'}
        </div>
      </div>
      <div role="log" aria-live="assertive" aria-label="Fila de aprovações pendentes">
        {shown.length ? shown.map((r, i) => (
          <ApprovalCard key={r.request_id} req={r} focused={i === focusIdx}
            cardRef={(el) => (cardRefs.current[i] = el)}
            onApprove={onApprove} onReject={onReject} onModify={onModify} />
        )) : (
          <div className="empty"><Icon name="check" /><div>Nenhuma aprovação pendente. Tudo em dia.</div></div>
        )}
      </div>

      {reject && (
        <Modal
          title="Rejeitar solicitação"
          onClose={() => setReject(null)}
          actions={<>
            <button className="btn" onClick={() => setReject(null)}>Cancelar</button>
            <button className="btn btn-danger" disabled={reject.h.critical && !rejectText.trim()} onClick={confirmReject}>
              <Icon name="x" /> Confirmar rejeição
            </button>
          </>}
        >
          <p style={{ marginTop: 0 }}>Você está rejeitando <b>{reject.h.label}</b>.</p>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Justificativa {reject.h.critical ? '(obrigatória)' : '(opcional)'}</label>
            <textarea className="textarea" rows="3" value={rejectText} onChange={(e) => setRejectText(e.target.value)}
              placeholder="Registrada na trilha de auditoria." autoFocus />
          </div>
        </Modal>
      )}
    </div>
  );
}
