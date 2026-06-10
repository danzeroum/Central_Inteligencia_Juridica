// Primitivas de UI — ícones monoline + componentes base (de shared.jsx do mockup),
// acrescidos de Toast, Modal e Confirm para substituir alert()/prompt()/confirm().
import React, { useEffect, useRef } from 'react';

const ICONS = {
  spark: 'M13 2 4 14h6l-1 8 9-12h-6z',
  chat: 'M4 5h16v11H8l-4 4z',
  process: 'M7 3h7l4 4v14H7z M14 3v4h4',
  scale: 'M12 3v18 M5 8h14 M5 8 2 15h6z M19 8l-3 7h6z M8 21h8',
  gavel: 'M14 4 9 9 M11 6l4 4 M5 19l6-6 M3 21h7',
  law: 'M4 7h16 M4 7 12 3l8 4 M6 7v9 M10 7v9 M14 7v9 M18 7v9 M4 19h16',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2',
  shield: 'M12 3 5 6v5c0 4 3 7 7 9 4-2 7-5 7-9V6z M9 12l2 2 4-4',
  graduate: 'M12 4 2 9l10 5 10-5z M6 11v5c0 1 3 3 6 3s6-2 6-3v-5',
  robot: 'M8 7h8a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z M12 4v3 M9.5 12h.01 M14.5 12h.01 M3 11v4 M21 11v4',
  ledger: 'M5 3h11l3 3v15H5z M9 8h7 M9 12h7 M9 16h4',
  flow: 'M6 4h5v4H6z M13 16h5v4h-5z M8.5 8v4h7v4 M3.5 12h5',
  pulse: 'M3 12h4l2-6 4 12 2-6h6',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M21 21l-4-4',
  send: 'M4 12 20 4l-6 16-3-7z',
  attach: 'M21 11l-8 8a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7-7',
  filter: 'M3 5h18l-7 8v6l-4 2v-8z',
  plus: 'M12 5v14 M5 12h14',
  check: 'M5 12l4 4 10-10',
  x: 'M6 6l12 12 M18 6 6 18',
  edit: 'M4 20h4L19 9l-4-4L4 16z M14 5l4 4',
  alert: 'M12 3 2 20h20z M12 10v5 M12 18h.01',
  bell: 'M18 9a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8 M10.5 21h3',
  chevron: 'M9 6l6 6-6 6',
  down: 'M6 9l6 6 6-6',
  external: 'M14 4h6v6 M20 4l-9 9 M19 14v5H5V5h5',
  cog: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M12 2v3 M12 19v3 M5 5l2 2 M17 17l2 2 M2 12h3 M19 12h3 M5 19l2-2 M17 7l2-2',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c0-4 4-6 8-6s8 2 8 6',
  doc: 'M6 3h8l4 4v14H6z M14 3v4h4 M9 13h6 M9 17h4',
  refresh: 'M4 12a8 8 0 0 1 14-5l2 2 M20 5v4h-4 M20 12a8 8 0 0 1-14 5l-2-2 M4 19v-4h4',
  lock: 'M6 10h12v10H6z M9 10V7a3 3 0 0 1 6 0v3',
  compare: 'M12 3v18 M7 7 3 11l4 4 M17 7l4 4-4 4',
  // Fase 1
  radar: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M12 2v2 M12 20v2 M2 12h2 M20 12h2',
  home: 'M3 11l9-8 9 8v10h-5v-6h-8v6H3z',
  building: 'M3 21h18 M6 3h12v18H6z M9 7h2 M13 7h2 M9 11h2 M13 11h2 M9 15h2 M13 15h2',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 10v5 M12 8h.01',
  unlock: 'M6 10h12v10H6z M8 10V7a4 4 0 0 1 8 0',
  privacy: 'M12 3 4 6v5c0 5 4 9 8 11 4-2 8-6 8-11V6z M9 12l2 2 4-4',
  map: 'M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z M9 3v15 M15 6v15',
  kit: 'M4 4h5v5H4z M15 4h5v5h-5z M4 15h5v5H4z M15 15h5v5h-5z',
  copy: 'M16 3H5a1 1 0 0 0-1 1v11 M9 7h10a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z',
};

export function Icon({ name, className, style, title }) {
  const d = ICONS[name] || ICONS.chat;
  return (
    <svg
      className={className}
      style={style}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : 'true'}
    >
      {title && <title>{title}</title>}
      {d.split(' M').map((seg, i) => (
        <path key={i} d={(i ? 'M' : '') + seg} />
      ))}
    </svg>
  );
}

export function Badge({ kind = 'mut', dot, icon, title, children }) {
  return (
    <span className={`badge b-${kind}`} title={title}>
      {dot && <span className="dot" style={{ background: 'currentColor' }} />}
      {icon && <Icon name={icon} style={{ width: 11, height: 11 }} />}
      {children}
    </span>
  );
}

export function Stat({ label, value, delta, dir }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-val">
        {value}
        {delta && <span className={`stat-delta ${dir}`}>{delta}</span>}
      </div>
    </div>
  );
}

export function Spark({ points, color = 'var(--navy)' }) {
  if (!points || !points.length) return null;
  const max = Math.max(...points), min = Math.min(...points);
  const rng = max - min || 1;
  const w = 200, h = 40;
  const pts = points
    .map((p, i) => `${(i / (points.length - 1)) * w},${h - ((p - min) / rng) * (h - 6) - 3}`)
    .join(' ');
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Gauge({ value, label, color = 'var(--ok)' }) {
  const r = 26, c = 2 * Math.PI * r, off = c * (1 - value / 100);
  return (
    <div className="gauge">
      <svg viewBox="0 0 62 62">
        <circle cx="31" cy="31" r={r} fill="none" stroke="var(--line)" strokeWidth="6" />
        <circle cx="31" cy="31" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off} transform="rotate(-90 31 31)" />
        <text x="31" y="35" textAnchor="middle" fontSize="14" fontWeight="600" fill="var(--ink)" fontFamily="var(--mono)">{value}</text>
      </svg>
      <div><div style={{ fontWeight: 600, fontSize: 13 }}>{label}</div></div>
    </div>
  );
}

// ----- Drawer lateral acessível (painel deslizante da direita) -----
export function Drawer({ title, sub, children, footer, onClose }) {
  const drawerRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    const node = drawerRef.current;
    if (!node) return undefined;
    const SELECTOR = 'a[href],button:not([disabled]),textarea,input:not([disabled]),select,[tabindex]:not([tabindex="-1"])';
    const focusables = () => Array.from(node.querySelectorAll(SELECTOR));
    const first = focusables()[0];
    if (first) first.focus();
    const trap = (e) => {
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) return;
      if (e.shiftKey && document.activeElement === items[0]) { e.preventDefault(); items[items.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === items[items.length - 1]) { e.preventDefault(); items[0].focus(); }
    };
    node.addEventListener('keydown', trap);
    return () => node.removeEventListener('keydown', trap);
  }, []);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-label={title}
        onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <div className="drawer-title">{title}</div>
            {sub && <div className="drawer-sub">{sub}</div>}
          </div>
          <button className="icon-btn" aria-label="Fechar" onClick={onClose}><Icon name="x" /></button>
        </div>
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-foot">{footer}</div>}
      </div>
    </div>
  );
}

// ----- CopyLine — linha copiável com feedback visual -----
export function CopyLine({ value, label }) {
  const [copied, setCopied] = React.useState(false);
  const doCopy = async () => {
    try { await navigator.clipboard.writeText(value); } catch { /* fallback */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <button className="copy-line" onClick={doCopy} aria-label={`Copiar ${label || value}`}>
      <span className="mono" style={{ fontSize: 12 }}>{value}</span>
      <span className="copy-act">
        <Icon name={copied ? 'check' : 'copy'} />
        {copied ? 'Copiado' : 'Copiar'}
      </span>
    </button>
  );
}

// ----- Modal acessível (substitui alert/confirm/prompt) -----
export function Modal({ title, children, onClose, actions }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // M15: focus trap — mantém o Tab dentro do diálogo e foca o primeiro elemento.
  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return undefined;
    const SELECTOR =
      'a[href],button:not([disabled]),textarea,input:not([disabled]),select,[tabindex]:not([tabindex="-1"])';
    const focusables = () => Array.from(node.querySelectorAll(SELECTOR));
    const first = focusables()[0];
    if (first) first.focus();
    const onKeyDown = (e) => {
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    };
    node.addEventListener('keydown', onKeyDown);
    return () => node.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" aria-label="Fechar" onClick={onClose}><Icon name="x" /></button>
        </div>
        <div className="modal-body">{children}</div>
        {actions && <div className="modal-actions">{actions}</div>}
      </div>
    </div>
  );
}

// ----- Toasts persistentes com ação (resolve H9 — erros efêmeros) -----
export function Toasts({ toasts, onDismiss }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind || 'info'}`}>
          <Icon name={t.kind === 'error' ? 'alert' : t.kind === 'success' ? 'check' : 'bell'} style={{ width: 16, height: 16, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>{t.message}</div>
          {t.action && <button className="btn btn-sm" onClick={() => { t.action.onClick(); onDismiss(t.id); }}>{t.action.label}</button>}
          <button className="icon-btn" aria-label="Dispensar" onClick={() => onDismiss(t.id)}><Icon name="x" style={{ width: 14, height: 14 }} /></button>
        </div>
      ))}
    </div>
  );
}
