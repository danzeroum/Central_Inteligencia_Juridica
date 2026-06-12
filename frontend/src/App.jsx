import React, { useMemo, useState } from 'react';
import { Icon } from './components/primitives.jsx';
import { ToastProvider } from './components/toast.jsx';
import { api } from './api/client.js';
import { setToken, logout, isAuthed, getPrincipal, isAdmin } from './api/auth.js';

import AssistantScreen   from './screens/user/AssistantScreen.jsx';
import ProcessScreen     from './screens/user/ProcessScreen.jsx';
import JurisScreen       from './screens/user/JurisScreen.jsx';
import LegisScreen       from './screens/user/LegisScreen.jsx';
import HistoryScreen     from './screens/user/HistoryScreen.jsx';
import ProfileScreen     from './screens/user/ProfileScreen.jsx';
import Invest360Screen   from './screens/user/Invest360Screen.jsx';
import PrivacyScreen     from './screens/user/PrivacyScreen.jsx';

import FiscalDashboardScreen from './screens/fiscal/FiscalDashboardScreen.jsx';

import HitlScreen        from './screens/admin/HitlScreen.jsx';
import HitlDetailScreen  from './screens/admin/HitlDetailScreen.jsx';
import TrainingScreen    from './screens/admin/TrainingScreen.jsx';
import AgentsScreen      from './screens/admin/AgentsScreen.jsx';
import LedgerScreen      from './screens/admin/LedgerScreen.jsx';
import DmnScreen         from './screens/admin/DmnScreen.jsx';
import MonitorScreen     from './screens/admin/MonitorScreen.jsx';

// ── Navegação agrupada (Fase 1) ────────────────────────────────────────────
const NAV = {
  user: [
    { group: 'Consultar', items: [
      { id: 'assistant', label: 'Assistente',     icon: 'spark'    },
      { id: 'process',   label: 'Processos',      icon: 'process'  },
      { id: 'juris',     label: 'Jurisprudência', icon: 'scale'    },
      { id: 'legis',     label: 'Legislativo',    icon: 'law'      },
    ]},
    { group: 'Investigar', items: [
      { id: 'invest360', label: 'Investigação 360°', icon: 'radar', isNew: true },
      { id: 'history',   label: 'Minhas consultas',  icon: 'clock'              },
    ]},
    { group: 'Conta', items: [
      { id: 'perfil',       label: 'Meu Perfil',          icon: 'cog'     },
      { id: 'privacidade',  label: 'Privacidade (LGPD)',   icon: 'privacy', isNew: true },
    ]},
  ],
  admin: [
    { group: 'Fiscal', items: [
      { id: 'fiscal-dashboard', label: 'Analytics Fiscal', icon: 'law', isNew: true },
    ]},
    { group: 'Operação', items: [
      { id: 'hitl',    label: 'Aprovações',    icon: 'shield', hasBadge: true },
      { id: 'monitor', label: 'Monitoramento', icon: 'pulse'                  },
    ]},
    { group: 'Governança', items: [
      { id: 'ledger', label: 'Auditoria', icon: 'ledger' },
      { id: 'dmn',    label: 'Autonomia', icon: 'flow'   },
    ]},
    { group: 'Treinamento', items: [
      { id: 'training', label: 'Treinamento', icon: 'graduate' },
      { id: 'agents',   label: 'Agentes',     icon: 'robot'    },
    ]},
  ],
};

const TITLES = {
  assistant:   ['Consultar',   'Assistente'],
  process:     ['Consultar',   'Processos'],
  juris:       ['Consultar',   'Jurisprudência'],
  legis:       ['Consultar',   'Legislativo'],
  invest360:   ['Investigar',  'Investigação 360°'],
  history:     ['Investigar',  'Minhas consultas'],
  perfil:      ['Conta',       'Meu Perfil'],
  privacidade: ['Conta',       'Privacidade (LGPD)'],
  'fiscal-dashboard': ['Fiscal', 'Analytics Fiscal'],
  hitl:        ['Operação',    'Aprovações'],
  'hitl-detail': ['Operação',  'Aprovações', 'Modificar'],
  monitor:     ['Operação',    'Monitoramento'],
  ledger:      ['Governança',  'Auditoria'],
  dmn:         ['Governança',  'Autonomia'],
  training:    ['Treinamento', 'Treinamento'],
  agents:      ['Treinamento', 'Agentes'],
};

function BrandMark({ className }) {
  return <div className={'brand-mark ' + (className || '')}><Icon name="scale" /></div>;
}

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

  const onSubmit = (e) => { e.preventDefault(); doLogin(username.trim(), password); };

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
          <div role="alert" style={{ color: 'var(--crit)', fontSize: 13, marginTop: 4 }}>{error}</div>
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
  const [authed, setAuthed]           = useState(isAuthed());
  const [mode, setMode]               = useState(isAdmin() ? 'admin' : 'user');
  const [route, setRoute]             = useState(isAdmin() ? 'hitl' : 'assistant');
  const [pendingCount, setPendingCount] = useState(0);

  const switchMode = (m) => { setMode(m); setRoute(m === 'admin' ? 'hitl' : 'invest360'); };
  const go = (r) => {
    setRoute(r);
    const isAdminRoute = NAV.admin.some((g) => g.items.some((i) => i.id === r));
    if (isAdminRoute) setMode('admin');
  };

  const onAuthenticated = () => {
    const admin = isAdmin();
    setMode(admin ? 'admin' : 'user');
    setRoute(admin ? 'hitl' : 'invest360');
    setAuthed(true);
  };
  const doLogout = () => { logout(); setAuthed(false); };

  const screens = useMemo(() => ({
    assistant:    <AssistantScreen />,
    process:      <ProcessScreen />,
    juris:        <JurisScreen />,
    legis:        <LegisScreen />,
    history:      <HistoryScreen go={go} />,
    perfil:       <ProfileScreen />,
    invest360:    <Invest360Screen go={go} />,
    privacidade:  <PrivacyScreen />,
    'fiscal-dashboard': <FiscalDashboardScreen />,
    hitl:         <HitlScreen go={go} onPendingChange={setPendingCount} />,
    'hitl-detail': <HitlDetailScreen go={go} />,
    training:     <TrainingScreen />,
    agents:       <AgentsScreen />,
    ledger:       <LedgerScreen />,
    dmn:          <DmnScreen />,
    monitor:      <MonitorScreen />,
  }), []);

  if (!authed) return <ToastProvider><Login onAuthenticated={onAuthenticated} /></ToastProvider>;

  const principal  = getPrincipal();
  const displayName = principal?.userId || 'Usuário';
  const crumb = TITLES[route] || ['', ''];
  const isChat = route === 'assistant';
  const groups = NAV[mode] || NAV.user;

  return (
    <ToastProvider>
      <div className="app">
        <a href="#main" className="btn btn-sm" style={{ position: 'absolute', left: -9999, top: 8 }}
          onFocus={(e) => (e.target.style.left = '8px')}
          onBlur={(e)  => (e.target.style.left = '-9999px')}>
          Pular para o conteúdo
        </a>

        <aside className="sidebar">
          <div className="brand">
            <BrandMark />
            <div>
              <div className="brand-name">Central Jurídica</div>
              <div className="brand-sub">Inteligência · Agentes</div>
            </div>
          </div>

          <nav className="nav" aria-label="Navegação principal">
            {groups.map((g) => (
              <div className="nav-group" key={g.group}>
                <div className="nav-group-label">{g.group}</div>
                {g.items.map((it) => {
                  const isActive = route === it.id || (it.id === 'hitl' && route === 'hitl-detail');
                  return (
                    <button
                      key={it.id}
                      className={'nav-item' + (isActive ? ' active' : '')}
                      onClick={() => { setMode(mode); setRoute(it.id); }}>
                      <Icon name={it.icon} className="nav-icon" />
                      {it.label}
                      {it.hasBadge && pendingCount > 0 && (
                        <span className="nav-badge">{pendingCount}</span>
                      )}
                      {it.isNew && !it.hasBadge && (
                        <span className="tag-new">NOVO</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-foot">
            <button className="user-chip">
              <div className="avatar">{displayName.slice(0, 2).toUpperCase()}</div>
              <div style={{ flex: 1 }}>
                <div className="user-name">{displayName}</div>
                <div className="user-role">{(principal?.roles || []).join(', ') || 'sem papel'}</div>
              </div>
              <Icon name="cog" style={{ width: 15, height: 15, color: 'var(--faint)' }} />
            </button>
            <button className="btn btn-sm" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
              onClick={doLogout}>
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
              <button className={mode === 'user'  ? 'on' : ''} onClick={() => switchMode('user')}>Usuário</button>
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
