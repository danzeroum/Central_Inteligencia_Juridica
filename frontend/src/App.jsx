import React, { useState } from 'react';
import { Icon } from './components/primitives.jsx';
import { ToastProvider } from './components/toast.jsx';

import AssistantScreen from './screens/user/AssistantScreen.jsx';
import ProcessScreen from './screens/user/ProcessScreen.jsx';
import JurisScreen from './screens/user/JurisScreen.jsx';
import LegisScreen from './screens/user/LegisScreen.jsx';
import HistoryScreen from './screens/user/HistoryScreen.jsx';

import HitlScreen from './screens/admin/HitlScreen.jsx';
import HitlDetailScreen from './screens/admin/HitlDetailScreen.jsx';
import TrainingScreen from './screens/admin/TrainingScreen.jsx';
import AgentsScreen from './screens/admin/AgentsScreen.jsx';
import LedgerScreen from './screens/admin/LedgerScreen.jsx';
import DmnScreen from './screens/admin/DmnScreen.jsx';
import MonitorScreen from './screens/admin/MonitorScreen.jsx';

const NAV = {
  user: [
    { id: 'assistant', label: 'Assistente', icon: 'spark' },
    { id: 'process', label: 'Processos', icon: 'process' },
    { id: 'juris', label: 'Jurisprudência', icon: 'scale' },
    { id: 'legis', label: 'Legislativo', icon: 'law' },
    { id: 'history', label: 'Minhas consultas', icon: 'clock' },
  ],
  admin: [
    { id: 'hitl', label: 'Aprovações', icon: 'shield' },
    { id: 'training', label: 'Treinamento', icon: 'graduate' },
    { id: 'agents', label: 'Agentes', icon: 'robot' },
    { id: 'ledger', label: 'Auditoria', icon: 'ledger' },
    { id: 'dmn', label: 'Autonomia', icon: 'flow' },
    { id: 'monitor', label: 'Monitoramento', icon: 'pulse' },
  ],
};

const TITLES = {
  assistant: ['Espaço de Trabalho', 'Assistente'],
  process: ['Espaço de Trabalho', 'Processos'],
  juris: ['Espaço de Trabalho', 'Jurisprudência'],
  legis: ['Espaço de Trabalho', 'Legislativo'],
  history: ['Espaço de Trabalho', 'Minhas consultas'],
  hitl: ['Administração', 'Aprovações'],
  'hitl-detail': ['Administração', 'Aprovações', 'Modificar'],
  training: ['Administração', 'Treinamento'],
  agents: ['Administração', 'Agentes'],
  ledger: ['Administração', 'Auditoria'],
  dmn: ['Administração', 'Autonomia'],
  monitor: ['Administração', 'Monitoramento'],
};

function BrandMark({ className }) {
  return <div className={'brand-mark ' + (className || '')}><Icon name="scale" /></div>;
}

function Login({ onEnter }) {
  return (
    <div className="login-wrap">
      <div className="login">
        <BrandMark />
        <h1>Central de Inteligência Jurídica</h1>
        <div className="sub">Plataforma de agentes jurídicos</div>
        <div className="field"><label>E-mail corporativo</label><input className="input" defaultValue="m.ribeiro@escritorio.adv.br" /></div>
        <div className="field"><label>Senha</label><input className="input" type="password" defaultValue="········" /></div>
        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} onClick={() => onEnter('user')}>
          <Icon name="lock" /> Entrar
        </button>
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="btn btn-sm" style={{ flex: 1, justifyContent: 'center' }} onClick={() => onEnter('user')}>Entrar como Usuário</button>
          <button className="btn btn-sm" style={{ flex: 1, justifyContent: 'center' }} onClick={() => onEnter('admin')}>Entrar como Admin</button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [mode, setMode] = useState('user');
  const [route, setRoute] = useState('assistant');
  const [pendingCount, setPendingCount] = useState(0);

  const enter = (m) => { const mm = m === 'admin' ? 'admin' : 'user'; setMode(mm); setRoute(mm === 'admin' ? 'hitl' : 'assistant'); setAuthed(true); };
  const switchMode = (m) => { setMode(m); setRoute(m === 'admin' ? 'hitl' : 'assistant'); };
  const go = (r) => setRoute(r);

  if (!authed) return <ToastProvider><Login onEnter={enter} /></ToastProvider>;

  const screens = {
    assistant: <AssistantScreen />,
    process: <ProcessScreen />,
    juris: <JurisScreen />,
    legis: <LegisScreen />,
    history: <HistoryScreen go={go} />,
    hitl: <HitlScreen go={go} onPendingChange={setPendingCount} />,
    'hitl-detail': <HitlDetailScreen go={go} />,
    training: <TrainingScreen />,
    agents: <AgentsScreen />,
    ledger: <LedgerScreen />,
    dmn: <DmnScreen />,
    monitor: <MonitorScreen />,
  };
  const crumb = TITLES[route] || ['', ''];
  const isChat = route === 'assistant';

  return (
    <ToastProvider>
      <div className="app">
        <a href="#main" className="btn btn-sm" style={{ position: 'absolute', left: -9999, top: 8 }}
          onFocus={(e) => (e.target.style.left = '8px')} onBlur={(e) => (e.target.style.left = '-9999px')}>
          Pular para o conteúdo
        </a>
        <aside className="sidebar">
          <div className="brand">
            <BrandMark />
            <div><div className="brand-name">Central Jurídica</div><div className="brand-sub">Inteligência · Agentes</div></div>
          </div>
          <nav className="nav" aria-label="Navegação principal">
            <div className="nav-group">
              <div className="nav-group-label">Espaço de Trabalho</div>
              {NAV.user.map((it) => (
                <button key={it.id} className={'nav-item' + (route === it.id ? ' active' : '')}
                  onClick={() => { setMode('user'); setRoute(it.id); }}>
                  <Icon name={it.icon} className="nav-icon" />{it.label}
                </button>
              ))}
            </div>
            <div className="nav-group">
              <div className="nav-group-label">Administração</div>
              {NAV.admin.map((it) => (
                <button key={it.id} className={'nav-item' + (route === it.id || (it.id === 'hitl' && route === 'hitl-detail') ? ' active' : '')}
                  onClick={() => { setMode('admin'); setRoute(it.id); }}>
                  <Icon name={it.icon} className="nav-icon" />{it.label}
                  {it.id === 'hitl' && pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
                </button>
              ))}
            </div>
          </nav>
          <div className="sidebar-foot">
            <button className="user-chip">
              <div className="avatar">MR</div>
              <div style={{ flex: 1 }}><div className="user-name">Mariana Ribeiro</div><div className="user-role">{mode === 'admin' ? 'Operadora HITL' : 'Advogada'}</div></div>
              <Icon name="cog" style={{ width: 15, height: 15, color: 'var(--faint)' }} />
            </button>
          </div>
        </aside>

        <div className="content">
          <div className="topbar">
            <div className="crumb">
              {crumb.map((c, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span className="sep">/</span>}
                  {i === crumb.length - 1 ? <b>{c}</b> : <span>{c}</span>}
                </React.Fragment>
              ))}
            </div>
            <div className="topbar-spacer" />
            <div className="seg">
              <button className={mode === 'user' ? 'on' : ''} onClick={() => switchMode('user')}>Usuário</button>
              <button className={mode === 'admin' ? 'on' : ''} onClick={() => switchMode('admin')}>Admin</button>
            </div>
            <button className="icon-btn" aria-label="Notificações"><Icon name="bell" /></button>
          </div>
          {isChat
            ? <div id="main" style={{ flex: 1, overflow: 'hidden' }}>{screens[route]}</div>
            : <div id="main" className="scroll">{screens[route]}</div>}
        </div>
      </div>
    </ToastProvider>
  );
}
