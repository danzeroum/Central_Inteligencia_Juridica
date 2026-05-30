// Cliente de API central — ponto único de configuração de base URL e
// tratamento de erros (resolve o "API_BASE hardcoded" apontado na auditoria).
// Em dev, o Vite faz proxy de /api -> :8000; em produção, mesma origem.

const BASE = import.meta.env.VITE_API_BASE || '';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, headers } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', ...headers },
      body: body != null ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError('Falha de rede — verifique sua conexão e tente novamente.', 0);
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

// WebSocket base (mantém o esquema correto ws/wss e a origem).
export function wsUrl(path) {
  if (BASE) return BASE.replace(/^http/, 'ws') + path;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

export const api = {
  // Tarefas / consultas (consulente + advogado)
  submitTask: (task_description) =>
    request('/api/v1/tasks', { method: 'POST', body: { task_description } }),
  history: (limit = 20) => request(`/api/v1/history?limit=${limit}`),

  // Legislativo
  legislativeBills: (q) =>
    request(`/consultar-projetos-lei/?q=${encodeURIComponent(q)}`),
  legislativeAnalysis: (tema) =>
    request(`/analise-legislativa/?tema=${encodeURIComponent(tema)}`, { method: 'POST' }),

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
  agents: () => request('/api/v1/agents'),
  agentInvoke: (agentId, task_description) =>
    request(`/api/v1/agents/${agentId}/invoke`, {
      method: 'POST',
      body: { task_description },
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
};
