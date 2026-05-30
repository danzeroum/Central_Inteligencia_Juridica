// Contexto de Toasts — substitui alert()/HTTP 500 cru por notificações
// persistentes e acessíveis (com ação opcional de retry).
import React, { createContext, useCallback, useContext, useState } from 'react';
import { Toasts } from './primitives.jsx';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((toast) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { ...toast, id }]);
    // Sucesso some sozinho; erros permanecem até dispensa manual (resolve H9).
    if (toast.kind === 'success') setTimeout(() => dismiss(id), 4000);
    return id;
  }, [dismiss]);

  const helpers = {
    push,
    success: (message) => push({ kind: 'success', message }),
    error: (message, action) => push({ kind: 'error', message, action }),
    info: (message) => push({ kind: 'info', message }),
  };

  return (
    <ToastContext.Provider value={helpers}>
      {children}
      <Toasts toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
