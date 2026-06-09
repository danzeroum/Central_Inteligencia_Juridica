import React, { useMemo, useState } from 'react';
import { Icon } from './components/primitives.jsx';
import { ToastProvider } from './components/toast.jsx';
import { api } from './api/client.js';
import { setToken, logout, isAuthed, getPrincipal, isAdmin } from './api/auth.js';

import AssistantScreen from './screens/user/AssistantScreen.jsx';
import ProcessScreen from './screens/user/ProcessScreen.jsx';
import JurisScreen from './screens/user/JurisScreen.jsx';
import LegisScreen from './screens/user/LegisScreen.jsx';
import HistoryScreen from './screens/user/HistoryScreen.jsx';
import ProfileScreen from './screens/user/ProfileScreen.jsx';

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
    { id: 'perfil', label: 'Meu Perfil', icon: 'cog' },
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
  perfil: ['Espaço de Trabalho', 'Meu Perfil'],
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

// CRÍTICO-09/M14: login REAL — formulário semântico que autentica via
// /auth/login e armazena o JWT. Sem mais authed=true sem credenciais nem senha
// hardcoded. Os botões "Demo" só funcionam quando o backend expõe usuários de
// desenvolvimento (ENVIRONMENT=development/test ou AUTH_USERS configurado).
function Login({ onAuthenticated }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const doLogin = async (user, pass) => {
    setBusy(true);
    setError('');
    try {
      const res = await api.login(user, pass);
      setToken(res.access_token);
      onAuthenticated();
    } catch (e) {
      setError(e?.message || 'Falha ao autenticar.');
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    doLogin(username.trim(), password);
  };

  return (
    <div className="login-wrap">
      <form className="login" onSubmit={onSubmit}>
        <BrandMark />
        <h1>Central de Inteligência Jurídica</h1>
        <div className="sub">Plataforma de agentes jurídicos</div>
        <div className="field">
          <label htmlFor="login-user">Usuário</label>
          <input id="login-user" className="input" type="text" autoComplete="username"
            value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="login-pass">Senha</label>
          <input id="login-pass" className="input" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && (
          <div className="login-error" role="alert" style={{ color: 'var(--danger, #c0392b)', fontSize: 13, marginTop: 4 }}>
            {error}
          </div>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}
          style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
          <Icon name="lock" /> {busy ? 'Entrando…' : 'Entrar'}
        </button>
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button type="button" className="btn btn-sm" disabled={busy} style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => doLogin('operator', 'operator')}>Demo: Operador</button>
          <button type="button" className="btn btn-sm" disabled={busy} style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => doLogin('admin', 'admin')}>Demo: Admin</button>
        </div>
      </form>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(isAuthed());
  const [mode, setMode] = useState(isAdmin() ? 'admin' : 'user');
  const [route, setRoute] = useState(isAdmin() ? 'hitl' : 'assistant');
  const [pendingCount, setPendingCount] = useState(0);

  const switchMode = (m) => { setMode(m); setRoute(m === 'admin' ? 'hitl' : 'assistant'); };
  const go = (r) => setRoute(r);

  const onAuthenticated = () => {
    const admin = isAdmin();
    setMode(admin ? 'admin' : 'user');
    setRoute(admin ? 'hitl' : 'assistant');
    setAuthed(true);
  };
  const doLogout = () => { logout(); setAuthed(false); };

  // M13: o objeto de telas é memoizado (não é recriado a cada render). O hook é
  // chamado SEMPRE (antes de qualquer return) para respeitar as regras de hooks.
  const screens = useMemo(() => ({
    assistant: <AssistantScreen />,
    process: <ProcessScreen />,
    juris: <JurisScreen />,
    legis: <LegisScreen />,
    history: <HistoryScreen go={go} />,
    perfil: <ProfileScreen />,
    hitl: <HitlScreen go={go} onPendingChange={setPendingCount} />,
    'hitl-detail': <HitlDetailScreen go={go} />,
    training: <TrainingScreen />,
    agents: <AgentsScreen />,
    ledger: <LedgerScreen />,
    dmn: <DmnScreen />,
    monitor: <MonitorScreen />,
  }), []);

  if (!authed) return <ToastProvider><Login onAuthenticated={onAuthenticated} /></ToastProvider>;

  const principal = getPrincipal();
  const displayName = principal?.userId || 'Usuário';
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
              <div className="avatar">{displayName.slice(0, 2).toUpperCase()}</div>
              <div style={{ flex: 1 }}><div className="user-name">{displayName}</div><div className="user-role">{(principal?.roles || []).join(', ') || 'sem papel'}</div></div>
              <Icon name="cog" style={{ width: 15, height: 15, color: 'var(--faint)' }} />
            </button>
            <button className="btn btn-sm" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }} onClick={doLogout}>
              <Icon name="lock" /> Sair
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
