// Testes do store de autenticação (CRÍTICO-09/10, FH01).
import { describe, it, expect, beforeEach } from 'vitest';
import {
  setToken,
  getToken,
  logout,
  isAuthed,
  getPrincipal,
  hasRole,
  operatorId,
  isAdmin,
} from './auth.js';

// Gera um JWT de teste (header.payload.signature) — só o payload importa aqui.
function makeJwt(payload) {
  const b64 = (obj) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.sig`;
}

const future = Math.floor(Date.now() / 1000) + 3600;
const past = Math.floor(Date.now() / 1000) - 10;

describe('auth store', () => {
  beforeEach(() => logout());

  it('persiste e recupera o token', () => {
    setToken('abc');
    expect(getToken()).toBe('abc');
    logout();
    expect(getToken()).toBeNull();
  });

  it('decodifica papéis e user do JWT (getPrincipal)', () => {
    setToken(makeJwt({ sub: 'm.ribeiro', roles: ['operator'], exp: future }));
    const p = getPrincipal();
    expect(p.userId).toBe('m.ribeiro');
    expect(p.roles).toEqual(['operator']);
    expect(hasRole('operator')).toBe(true);
    expect(hasRole('admin')).toBe(false);
  });

  it('operatorId vem do token, não é hardcoded (CRÍTICO-10)', () => {
    setToken(makeJwt({ sub: 'real.operator', roles: ['operator'], exp: future }));
    expect(operatorId()).toBe('real.operator');
  });

  it('isAuthed é falso sem token e verdadeiro com token válido', () => {
    expect(isAuthed()).toBe(false);
    setToken(makeJwt({ sub: 'u', roles: ['admin'], exp: future }));
    expect(isAuthed()).toBe(true);
    expect(isAdmin()).toBe(true);
  });

  it('token expirado é tratado como não autenticado', () => {
    setToken(makeJwt({ sub: 'u', roles: ['admin'], exp: past }));
    expect(isAuthed()).toBe(false);
    expect(getToken()).toBeNull(); // limpo ao detectar expiração
  });
});
