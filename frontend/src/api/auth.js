// Autenticação no frontend (CRÍTICO-09/10, FH01): armazenamento do JWT e
// derivação da identidade/papéis a partir do próprio token. Substitui o login
// fake (authed=true sem credenciais) e o OPERATOR_ID hardcoded.

const TOKEN_KEY = 'cij.token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* localStorage indisponível (modo privado/SSR) */
  }
}

export function logout() {
  setToken(null);
}

export function isAuthed() {
  const p = getPrincipal();
  if (!p) return false;
  // Considera expirado se o exp (epoch s) já passou.
  if (p.exp && Date.now() / 1000 >= p.exp) {
    setToken(null);
    return false;
  }
  return true;
}

// Decodifica o payload do JWT (sem verificar assinatura — só para exibição/UX;
// a verificação real é feita no backend a cada requisição).
export function getPrincipal() {
  const token = getToken();
  if (!token) return null;
  try {
    const part = token.split('.')[1];
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
    const payload = JSON.parse(json);
    const rawRoles = payload.roles;
    const roles = Array.isArray(rawRoles) ? rawRoles : rawRoles ? [rawRoles] : [];
    return { userId: payload.sub, roles, exp: payload.exp };
  } catch {
    return null;
  }
}

export function hasRole(role) {
  const p = getPrincipal();
  return !!p && p.roles.includes(role);
}

// Operador efetivo para registros HITL: derivado do token (não mais hardcoded).
export function operatorId() {
  return getPrincipal()?.userId || 'operator';
}

// É um perfil administrativo? (admin/auditor acessam o painel de Administração)
export function isAdmin() {
  const p = getPrincipal();
  return !!p && (p.roles.includes('admin') || p.roles.includes('auditor'));
}
