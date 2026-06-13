/**
 * VaultScreen — S-G.3
 * Cofre de credenciais: armazenar, consultar metadados, rotacionar, remover e assinar.
 *
 * Segurança: o payload decifrado NUNCA retorna pela API — apenas metadados.
 * Certificados: apenas caminho de arquivo aceito (não conteúdo PEM/DER).
 */

import React, { useState } from 'react';
import { api } from '../../api/client.js';

// ── helpers ──────────────────────────────────────────────────────────────────

function ErrAlert({ msg }) {
  if (!msg) return null;
  return (
    <div role="alert" style={{
      background: 'var(--crit-bg, #fee2e2)', color: 'var(--crit)', borderRadius: 6,
      padding: '10px 14px', marginBottom: 12, fontSize: 13,
    }}>{msg}</div>
  );
}

function OkBox({ children }) {
  return (
    <div style={{
      background: 'var(--surface2, #1e293b)', borderRadius: 6,
      padding: '12px 16px', marginTop: 12, fontSize: 12,
    }}>{children}</div>
  );
}

function Label({ children }) {
  return (
    <label style={{ fontSize: 12, color: 'var(--faint)', display: 'block', marginBottom: 4 }}>
      {children}
    </label>
  );
}

function SecurityNote() {
  return (
    <div style={{
      fontSize: 11, color: 'var(--faint)', padding: '8px 12px',
      background: 'var(--surface2)', borderRadius: 6, marginBottom: 16,
      borderLeft: '3px solid var(--warn)',
    }}>
      O payload decifrado <strong>nunca</strong> é retornado pela API — apenas metadados.
      Certificados: use apenas o <strong>caminho</strong> do arquivo (.pfx), não o conteúdo.
    </div>
  );
}

function SourceTenantFields({ source, setSource, tenant, setTenant }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
      <div>
        <Label>Source *</Label>
        <input className="input" required placeholder="ex: ecac_cert"
          value={source} onChange={e => setSource(e.target.value)} style={{ fontSize: 12 }} />
      </div>
      <div>
        <Label>Tenant ID *</Label>
        <input className="input" required placeholder="ex: empresa_01"
          value={tenant} onChange={e => setTenant(e.target.value)} style={{ fontSize: 12 }} />
      </div>
    </div>
  );
}

// ── Armazenar ─────────────────────────────────────────────────────────────────

function ArmazenarTab() {
  const [source,   setSource]   = useState('');
  const [tenant,   setTenant]   = useState('');
  const [payload,  setPayload]  = useState('{\n  "username": "usuario",\n  "api_key": "valor"\n}');
  const [certPath, setCertPath] = useState('');
  const [result,   setResult]   = useState(null);
  const [busy,     setBusy]     = useState(false);
  const [err,      setErr]      = useState('');

  const store = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const parsedPayload = JSON.parse(payload);
      const body = { source: source.trim(), tenant_id: tenant.trim(), payload: parsedPayload };
      if (certPath.trim()) body.cert_path = certPath.trim();
      const data = await api.post('/api/v1/vault/store', body);
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao armazenar credencial.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <SecurityNote />
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={store}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Armazenar Credencial</h3>
        <SourceTenantFields source={source} setSource={setSource}
          tenant={tenant} setTenant={setTenant} />
        <div style={{ marginBottom: 10 }}>
          <Label>Payload (JSON — NÃO inclua conteúdo PEM/DER) *</Label>
          <textarea className="input" rows={6} required value={payload}
            onChange={e => setPayload(e.target.value)}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
        </div>
        <div style={{ marginBottom: 14 }}>
          <Label>Caminho do certificado A1 (opcional)</Label>
          <input className="input" placeholder="/run/secrets/cert.pfx"
            value={certPath} onChange={e => setCertPath(e.target.value)} style={{ fontSize: 12 }} />
          <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2 }}>
            Apenas o caminho — nunca o conteúdo do certificado (AP-05).
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Armazenando…' : '🔒 Armazenar'}
        </button>
      </form>
      {result && (
        <OkBox>
          <div style={{ fontWeight: 600, color: 'var(--ok)', marginBottom: 4 }}>✓ Credencial armazenada</div>
          <div style={{ fontFamily: 'monospace', fontSize: 11 }}>slot_id: {result.slot_id}</div>
        </OkBox>
      )}
    </div>
  );
}

// ── Consultar Metadados ───────────────────────────────────────────────────────

function MetadataTab() {
  const [source, setSource] = useState('');
  const [tenant, setTenant] = useState('');
  const [meta,   setMeta]   = useState(null);
  const [busy,   setBusy]   = useState(false);
  const [err,    setErr]    = useState('');

  const consultar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setMeta(null);
    try {
      const qs = new URLSearchParams({ source: source.trim(), tenant_id: tenant.trim() });
      const data = await api.get(`/api/v1/vault/metadata?${qs}`);
      setMeta(data);
    } catch (ex) {
      setErr(ex?.message || 'Credencial não encontrada.');
    } finally {
      setBusy(false);
    }
  };

  const fmt = (ts) => ts ? new Date(ts * 1000).toLocaleString('pt-BR') : '—';

  return (
    <div style={{ maxWidth: 480 }}>
      <ErrAlert msg={err} />
      <form onSubmit={consultar} style={{ marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
          <div>
            <Label>Source *</Label>
            <input className="input" required value={source}
              onChange={e => setSource(e.target.value)} style={{ fontSize: 12 }} />
          </div>
          <div>
            <Label>Tenant ID *</Label>
            <input className="input" required value={tenant}
              onChange={e => setTenant(e.target.value)} style={{ fontSize: 12 }} />
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? '…' : 'Consultar Metadados'}
        </button>
      </form>
      {meta && (
        <div className="card" style={{ padding: 16, fontSize: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Metadados (payload não exposto)</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
            <span style={{ color: 'var(--faint)' }}>slot_id:</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{meta.slot_id}</span>
            <span style={{ color: 'var(--faint)' }}>source:</span><span>{meta.source}</span>
            <span style={{ color: 'var(--faint)' }}>tenant:</span><span>{meta.tenant_id}</span>
            <span style={{ color: 'var(--faint)' }}>criado:</span><span>{fmt(meta.created_at)}</span>
            <span style={{ color: 'var(--faint)' }}>rotacionado:</span><span>{fmt(meta.rotated_at)}</span>
            <span style={{ color: 'var(--faint)' }}>tem cert:</span>
            <span style={{ color: meta.has_cert_path ? 'var(--ok)' : 'var(--faint)' }}>
              {meta.has_cert_path ? 'sim' : 'não'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Rotacionar ────────────────────────────────────────────────────────────────

function RotacionarTab() {
  const [source,    setSource]    = useState('');
  const [tenant,    setTenant]    = useState('');
  const [newPayload,setNewPayload]= useState('{\n  "username": "novo_usuario",\n  "api_key": "novo_valor"\n}');
  const [result,    setResult]    = useState(null);
  const [busy,      setBusy]      = useState(false);
  const [err,       setErr]       = useState('');

  const rotacionar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/vault/rotate', {
        source:      source.trim(),
        tenant_id:   tenant.trim(),
        new_payload: JSON.parse(newPayload),
      });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao rotacionar credencial.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <SecurityNote />
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={rotacionar}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Rotacionar Credencial</h3>
        <SourceTenantFields source={source} setSource={setSource}
          tenant={tenant} setTenant={setTenant} />
        <div style={{ marginBottom: 14 }}>
          <Label>Novo payload (JSON) *</Label>
          <textarea className="input" rows={6} required value={newPayload}
            onChange={e => setNewPayload(e.target.value)}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Rotacionando…' : '↻ Rotacionar'}
        </button>
      </form>
      {result && (
        <OkBox>
          <span style={{ color: 'var(--ok)', fontWeight: 600 }}>✓ Rotacionada</span>
          {' — '}{result.existed ? 'credencial existia e foi atualizada' : 'nova credencial criada'}
        </OkBox>
      )}
    </div>
  );
}

// ── Remover ───────────────────────────────────────────────────────────────────

function RemoverTab() {
  const [source,  setSource]  = useState('');
  const [tenant,  setTenant]  = useState('');
  const [confirm, setConfirm] = useState(false);
  const [result,  setResult]  = useState(null);
  const [busy,    setBusy]    = useState(false);
  const [err,     setErr]     = useState('');

  const remover = async (e) => {
    e.preventDefault();
    if (!confirm) { setErr('Marque a confirmação antes de remover.'); return; }
    setBusy(true); setErr(''); setResult(null);
    try {
      const qs = new URLSearchParams({ source: source.trim(), tenant_id: tenant.trim() });
      const data = await api.del(`/api/v1/vault/delete?${qs}`);
      setResult(data);
      setConfirm(false);
    } catch (ex) {
      setErr(ex?.message || 'Credencial não encontrada ou erro ao remover.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={remover}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Remover Credencial</h3>
        <SourceTenantFields source={source} setSource={setSource}
          tenant={tenant} setTenant={setTenant} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
          marginBottom: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />
          Confirmo que desejo remover permanentemente esta credencial
        </label>
        <button type="submit" className="btn" disabled={busy}
          style={{ background: 'var(--crit)', color: '#fff', border: 'none' }}>
          {busy ? 'Removendo…' : '✕ Remover'}
        </button>
      </form>
      {result && (
        <OkBox>
          <span style={{ color: 'var(--ok)', fontWeight: 600 }}>✓ Credencial removida</span>
        </OkBox>
      )}
    </div>
  );
}

// ── Assinar ───────────────────────────────────────────────────────────────────

function AssinarTab() {
  const [payloadB64, setPayloadB64] = useState('');
  const [result,     setResult]     = useState(null);
  const [busy,       setBusy]       = useState(false);
  const [err,        setErr]        = useState('');

  const assinar = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(''); setResult(null);
    try {
      const data = await api.post('/api/v1/vault/sign', { payload_b64: payloadB64.trim() });
      setResult(data);
    } catch (ex) {
      setErr(ex?.message || 'Erro ao assinar payload.');
    } finally {
      setBusy(false);
    }
  };

  const exampleB64 = btoa('Payload de exemplo para assinatura');

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ fontSize: 11, color: 'var(--faint)', padding: '8px 12px',
        background: 'var(--surface2)', borderRadius: 6, marginBottom: 16,
        borderLeft: '3px solid var(--info)' }}>
        Assina o payload com o certificado A1 configurado em <code>CERT_A1_PATH</code>.
        Retorna <code>is_stub: true</code> se nenhum certificado real estiver configurado (AP-05).
      </div>
      <ErrAlert msg={err} />
      <form className="card" style={{ padding: 16 }} onSubmit={assinar}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Assinar Payload</h3>
        <div style={{ marginBottom: 14 }}>
          <Label>Payload em Base64 *</Label>
          <textarea className="input" rows={4} required value={payloadB64}
            onChange={e => setPayloadB64(e.target.value)}
            placeholder={exampleB64}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }} />
          <button type="button" className="btn btn-sm" style={{ marginTop: 4 }}
            onClick={() => setPayloadB64(exampleB64)}>
            Usar exemplo
          </button>
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Assinando…' : '✍ Assinar'}
        </button>
      </form>
      {result && (
        <OkBox>
          <div style={{ fontWeight: 600, color: 'var(--ok)', marginBottom: 8 }}>
            ✓ Assinado {result.is_stub ? '(stub — sem certificado real)' : `(${result.algorithm})`}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
            <span style={{ color: 'var(--faint)' }}>Algoritmo:</span><span>{result.algorithm}</span>
            <span style={{ color: 'var(--faint)' }}>CN:</span><span>{result.subject_cn || '—'}</span>
            <span style={{ color: 'var(--faint)' }}>Serial:</span>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{result.serial_number || '—'}</span>
            <span style={{ color: 'var(--faint)' }}>Assinatura:</span>
            <span style={{ fontFamily: 'monospace', fontSize: 10 }}>
              {(result.signature_b64 || '').slice(0, 60)}…
            </span>
          </div>
        </OkBox>
      )}
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

const TABS = [
  { id: 'armazenar', label: 'Armazenar' },
  { id: 'metadata',  label: 'Consultar' },
  { id: 'rotacionar',label: 'Rotacionar' },
  { id: 'remover',   label: 'Remover' },
  { id: 'assinar',   label: 'Assinar' },
];

export default function VaultScreen() {
  const [tab, setTab] = useState('armazenar');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Cofre de Credenciais</h2>
        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 2 }}>
          Gerenciamento seguro de credenciais e assinatura digital A1/A3
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {TABS.map(t => (
          <button key={t.id}
            className={'btn btn-sm' + (tab === t.id ? ' btn-primary' : '')}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'armazenar'  && <ArmazenarTab />}
      {tab === 'metadata'   && <MetadataTab />}
      {tab === 'rotacionar' && <RotacionarTab />}
      {tab === 'remover'    && <RemoverTab />}
      {tab === 'assinar'    && <AssinarTab />}
    </div>
  );
}
