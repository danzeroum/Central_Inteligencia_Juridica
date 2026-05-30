import React, { useState } from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';
import { useToast } from '../../components/toast.jsx';
import { api } from '../../api/client.js';

const SUGGESTIONS = [
  { op: 'status_check', txt: 'O TJSP está disponível para consultas agora?' },
  { op: 'process_movements', txt: 'Últimas movimentações do processo 1234567-89.2024.8.26.1234' },
  { op: 'jurisprudence_comparison', txt: 'Comparar jurisprudência sobre LGPD no STF e no TJSP' },
  { op: 'jurisprudence_search', txt: 'Decisões recentes do STJ sobre dano moral em relações de consumo' },
];

function MsgUser({ text }) {
  return (
    <div className="msg msg-user">
      <div className="msg-av">VC</div>
      <div className="msg-body"><div className="msg-who">Você</div><div className="msg-text">{text}</div></div>
    </div>
  );
}

function extract(result) {
  // O backend devolve supervisor_result aninhado; busca campos de intenção/resultado
  // de forma defensiva, pois o shape exato varia por operação.
  const sr = result?.supervisor_result || result || {};
  const intent = sr.intent || sr.intencao || result?.intent || {};
  const tribunals = result?.tribunals_used || sr.tribunals || intent.tribunais || [];
  const confidence = intent.confidence ?? sr.consensus_strength ?? null;
  const text =
    sr.response || sr.resposta || sr.summary || sr.result?.summary ||
    (typeof sr.result === 'string' ? sr.result : null) ||
    'Consulta processada. Veja os detalhes técnicos abaixo.';
  return { intent, tribunals, confidence, text, raw: result };
}

function MsgAI({ data, error }) {
  const [showRaw, setShowRaw] = useState(false);
  if (error) {
    return (
      <div className="msg msg-ai">
        <div className="msg-av"><Icon name="spark" style={{ width: 16, height: 16 }} /></div>
        <div className="msg-body">
          <div className="msg-who">Assistente Jurídico</div>
          <div className="ai-card"><div className="ai-main" style={{ color: 'var(--crit)' }}><Icon name="alert" style={{ width: 15, height: 15, verticalAlign: '-2px' }} /> {error}</div></div>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="msg msg-ai">
        <div className="msg-av"><Icon name="spark" style={{ width: 16, height: 16 }} /></div>
        <div className="msg-body"><div className="msg-who">Assistente Jurídico</div>
          <div className="ai-card"><div className="ai-main"><span className="skeleton" style={{ display: 'inline-block', width: 220, height: 14 }} /></div></div></div>
      </div>
    );
  }
  const { intent, tribunals, confidence, text, raw } = data;
  return (
    <div className="msg msg-ai">
      <div className="msg-av"><Icon name="spark" style={{ width: 16, height: 16 }} /></div>
      <div className="msg-body">
        <div className="msg-who">Assistente Jurídico <Badge kind="navy">Agente Supervisor</Badge></div>
        <div className="ai-card">
          <div className="intent">
            <span className="lab">Intenção detectada</span>
            {intent.operacao && <Badge kind="navy">{intent.operacao}</Badge>}
            {tribunals.map((t) => <span key={t} className="chip chip-out" style={{ padding: '3px 9px' }}>{t}</span>)}
            {confidence != null && <span style={{ marginLeft: 'auto' }} className="mono faint">confiança {Math.round(confidence * 100)}%</span>}
          </div>
          <div className="ai-main">
            <p style={{ marginTop: 0 }}>{text}</p>
            {showRaw && (
              <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--navy-tint-2)', padding: 12, borderRadius: 6, marginTop: 12, overflowX: 'auto', maxHeight: 280 }}>
                {JSON.stringify(raw, null, 2)}
              </pre>
            )}
            <div className="ap-raw" role="button" tabIndex={0} onClick={() => setShowRaw((v) => !v)} onKeyDown={(e) => e.key === 'Enter' && setShowRaw((v) => !v)}>
              <Icon name="chevron" style={{ width: 13, height: 13, transform: showRaw ? 'rotate(90deg)' : 'none' }} />
              {showRaw ? 'Ocultar' : 'Ver'} payload técnico
            </div>
          </div>
          {tribunals.length > 0 && (
            <div className="trace"><Icon name="flow" />Roteamento: <b>Supervisor</b> → {tribunals.map((t) => <b key={t}>{t} </b>)}</div>
          )}
          <div className="hitl-banner">
            <Icon name="shield" />
            <div>A síntese acima é informativa. Qualquer <b>ação processual</b> derivada entrará na fila de <b>revisão humana</b> antes de ser executada.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AssistantScreen() {
  const toast = useToast();
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);

  const send = async (text) => {
    const t = (text ?? draft).trim();
    if (!t || sending) return;
    setDraft('');
    const aiIndex = messages.length + 1;
    setMessages((m) => [...m, { role: 'user', text: t }, { role: 'ai', data: null }]);
    setSending(true);
    try {
      const res = await api.submitTask(t);
      setMessages((m) => m.map((msg, i) => (i === aiIndex ? { role: 'ai', data: extract(res) } : msg)));
    } catch (e) {
      setMessages((m) => m.map((msg, i) => (i === aiIndex ? { role: 'ai', error: e.message } : msg)));
      toast.error(`Falha na consulta: ${e.message}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-hero-mark"><Icon name="spark" /></div>
            <h2>Como posso ajudar no seu caso?</h2>
            <p>Pergunte sobre tribunais, processos, jurisprudência ou legislação. O assistente roteia sua dúvida ao agente especializado.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="suggest" onClick={() => send(s.txt)}>
                  <div className="s-op">{s.op}</div>
                  <div className="s-txt">{s.txt}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-inner">
            {messages.map((m, i) => m.role === 'user'
              ? <MsgUser key={i} text={m.text} />
              : <MsgAI key={i} data={m.data} error={m.error} />)}
          </div>
        )}
      </div>
      <div className="composer-wrap">
        <div className="composer">
          <textarea rows="1" placeholder="Descreva sua consulta jurídica…" value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
          <div className="composer-bar">
            <div className="left">
              <button className="mini-btn"><Icon name="law" /> Tribunais</button>
              <button className="mini-btn"><Icon name="attach" /> Anexar</button>
            </div>
            <button className="send" onClick={() => send()} aria-label="Enviar" disabled={sending}><Icon name="send" /></button>
          </div>
        </div>
        <div className="composer-hint"><Icon name="shield" style={{ width: 12, height: 12 }} /> Respostas geradas por IA e podem exigir revisão humana · não substituem aconselhamento jurídico</div>
      </div>
    </div>
  );
}
