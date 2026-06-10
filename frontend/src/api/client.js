// Cliente de API central — ponto único de configuração de base URL e
// tratamento de erros (resolve o "API_BASE hardcoded" apontado na auditoria).
// Em dev, o Vite faz proxy de /api -> :8000; em produção, mesma origem.

import { getToken, setToken } from './auth.js';

const BASE = import.meta.env.VITE_API_BASE || '';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, headers } = {}) {
  // FH01: injeta o token de autenticação (Authorization: Bearer) quando há sessão.
  const token = getToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', ...authHeaders, ...headers },
      body: body != null ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError('Falha de rede — verifique sua conexão e tente novamente.', 0);
  }
  if (res.status === 401) {
    // Sessão expirada/inválida: limpa o token para forçar novo login.
    setToken(null);
  }
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || data.title || detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

// WebSocket base (mantém o esquema correto ws/wss e a origem). O token de
// autenticação viaja por query param (H04: o WS HITL valida o JWT no handshake).
export function wsUrl(path) {
  const token = getToken();
  const sep = path.includes('?') ? '&' : '?';
  const auth = token ? `${sep}token=${encodeURIComponent(token)}` : '';
  if (BASE) return BASE.replace(/^http/, 'ws') + path + auth;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}${auth}`;
}

export const api = {
  // Autenticação (CRÍTICO-09)
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),

  // Tarefas / consultas (consulente + advogado)
  submitTask: (task_description) =>
    request('/api/v1/tasks', { method: 'POST', body: { task_description } }),
  history: (limit = 20) => request(`/api/v1/history?limit=${limit}`),

  // Jurisprudência (CNJ DataJud — Frente F.1)
  jurisprudencia: ({ tribunal, q, tema, assunto, grau, size } = {}) => {
    const params = new URLSearchParams()
    if (tribunal) params.set('tribunal', tribunal)
    if (q) params.set('q', q)
    if (tema) params.set('tema', tema)
    if (grau) params.set('grau', grau)
    if (size) params.set('size', String(size))
    for (const a of assunto || []) params.append('assunto', String(a))
    return request(`/api/v1/jurisprudencia?${params.toString()}`)
  },

  // Legislativo
  legislativeBills: (q, { pagina = 1, itens = 15 } = {}) =>
    request(
      `/api/v1/proposicoes-legislativas?q=${encodeURIComponent(q)}&pagina=${pagina}&itens=${itens}`
    ),
  legislativeAnalysis: (tema) =>
    request('/api/v1/analises-legislativas', { method: 'POST', body: { tema } }),

  // HITL
  hitlPending: () => request('/api/v1/hitl/pending'),
  hitlStats: () => request('/api/v1/hitl/stats'),
  hitlDecision: (payload) =>
    request('/api/v1/hitl/decisions', { method: 'POST', body: payload }),

  // Treinamento
  trainingStats: (agentType) =>
    request(`/api/v1/training/stats${agentType ? `?agent_type=${agentType}` : ''}`),
  trainingHistory: (limit = 20) => request(`/api/v1/training/history?limit=${limit}`),
  trainingActive: () => request('/api/v1/training/active-sessions'),
  trainingTrain: (agent_type, force = false) =>
    request('/api/v1/training/train', { method: 'POST', body: { agent_type, force } }),

  // Agentes (MCP)
  agents: (capability) => {
    const qs = capability ? `?capability=${encodeURIComponent(capability)}` : '';
    return request(`/api/v1/agents${qs}`);
  },
  agentDetail: (agentId) => request(`/api/v1/agents/${agentId}`),
  agentInvoke: (agentId, task_description) =>
    request(`/api/v1/agents/${agentId}/invoke`, {
      method: 'POST',
      body: { task_description },
    }),
  updateAgentTrust: (agentId, trust_score) =>
    request(`/api/v1/agents/${agentId}/trust`, {
      method: 'PATCH',
      body: { trust_score },
    }),

  // Auditoria (Decision Ledger)
  ledger: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/v1/ledger${qs ? `?${qs}` : ''}`);
  },
  ledgerExportUrl: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return `${BASE}/api/v1/ledger/export.csv${qs ? `?${qs}` : ''}`;
  },

  // Autonomia (DMN)
  autonomyConfig: () => request('/api/v1/autonomy/config'),
  updateAutonomyConfig: (payload) =>
    request('/api/v1/autonomy/config', { method: 'PUT', body: payload }),

  // Monitoramento
  monitoringHealth: () => request('/api/v1/monitoring/health'),

  // Perfil de usuário
  getProfile: () => request('/api/v1/profile'),
  updateProfile: (payload) => request('/api/v1/profile', { method: 'PUT', body: payload }),
  deleteProfile: () => request('/api/v1/profile', { method: 'DELETE' }),
  getProfileArea: () => request('/api/v1/profile/area'),
  updateProfileArea: (especialidades) =>
    request('/api/v1/profile/area', { method: 'PUT', body: { especialidades } }),
  listClientes: () => request('/api/v1/profile/clientes'),
  getCliente: (clienteId) => request(`/api/v1/profile/clientes/${clienteId}`),
  createCliente: (payload) =>
    request('/api/v1/profile/clientes', { method: 'POST', body: payload }),

  // Investigação 360° (GraphQL)
  intelligence360: (identifier, expandQsa = false) => {
    const gql = `query I360($identifier: String!, $expandQsa: Boolean!) {
      intelligence(identifier: $identifier, expandQsa: $expandQsa) {
        queryId identifierMasked identifierType riskScore
        riskDimensions { name score }
        riskFactors { code description weight source dimension }
        relatedParties { nome vinculo tipo fonte totalOcorrencias homonimoPossivel resumo }
        recommendations summary hitlStatus
        results { source status dataMode latencyMs totalAvailable items error }
      }
    }`;
    return request('/api/v1/intelligence/graphql', {
      method: 'POST',
      body: { query: gql, variables: { identifier, expandQsa } },
    });
  },

  // Métodos genéricos para uso direto por screens que precisam de flexibilidade
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
};
