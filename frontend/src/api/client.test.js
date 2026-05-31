// Testes do cliente HTTP: injeção do header Authorization (FH01) e ws token (H04).
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { api, wsUrl } from './client.js';
import { setToken, logout } from './auth.js';

function jwt(payload) {
  const b64 = (o) =>
    btoa(JSON.stringify(o)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64({ alg: 'HS256' })}.${b64(payload)}.sig`;
}
const TOKEN = jwt({ sub: 'u', roles: ['operator'], exp: Math.floor(Date.now() / 1000) + 3600 });

describe('api client', () => {
  beforeEach(() => logout());

  it('injeta Authorization: Bearer quando há token (FH01)', async () => {
    setToken(TOKEN);
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ ok: true }),
    }));
    global.fetch = fetchMock;

    await api.hitlPending();

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it('não envia Authorization quando não há sessão', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({}),
    }));
    global.fetch = fetchMock;

    await api.agents();
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBeUndefined();
  });

  it('limpa o token ao receber 401 (sessão expirada)', async () => {
    setToken(TOKEN);
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'expired' }),
    }));
    await expect(api.hitlPending()).rejects.toThrow();
    const { getToken } = await import('./auth.js');
    expect(getToken()).toBeNull();
  });

  it('wsUrl anexa o token como query param (H04)', () => {
    setToken(TOKEN);
    const url = wsUrl('/api/v1/hitl/ws');
    expect(url).toContain(`token=${encodeURIComponent(TOKEN)}`);
  });
});
