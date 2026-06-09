import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';

const AREAS = [
  { id: 'trabalhista', label: 'Trabalhista' },
  { id: 'previdenciario', label: 'Previdenciário' },
  { id: 'tributario', label: 'Tributário' },
  { id: 'civil', label: 'Civil' },
  { id: 'penal', label: 'Penal' },
  { id: 'empresarial', label: 'Empresarial' },
  { id: 'consumidor', label: 'Consumidor' },
  { id: 'ambiental', label: 'Ambiental' },
  { id: 'administrativo', label: 'Administrativo' },
  { id: 'constitucional', label: 'Constitucional' },
  { id: 'familia_sucessoes', label: 'Família e Sucessões' },
  { id: 'imobiliario', label: 'Imobiliário' },
  { id: 'contratual', label: 'Contratual' },
  { id: 'digital', label: 'Direito Digital' },
  { id: 'servidor_publico', label: 'Servidor Público' },
  { id: 'saude', label: 'Saúde' },
];

const FORMALITY_OPTIONS = [
  { value: 'accessible', label: 'Acessível' },
  { value: 'formal', label: 'Formal' },
  { value: 'technical', label: 'Técnico' },
];

export default function ProfileScreen() {
  const [profile, setProfile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [clientes, setClientes] = useState([]);
  const [newCliente, setNewCliente] = useState({ nome: '', nivel_tecnicidade_saida: 3, tipo_pessoa: 'fisica', consentimento_lgpd: false });
  const [clienteBusy, setClienteBusy] = useState(false);

  useEffect(() => {
    loadProfile();
    loadClientes();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await api.get('/api/v1/profile');
      setProfile(data);
    } catch {
      setError('Não foi possível carregar o perfil.');
    }
  };

  const loadClientes = async () => {
    try {
      const data = await api.get('/api/v1/profile/clientes');
      setClientes(Array.isArray(data) ? data : []);
    } catch {
      // clientes não críticos
    }
  };

  const handleSave = async () => {
    if (!profile) return;
    setBusy(true);
    setSaved(false);
    setError('');
    try {
      const updated = await api.put('/api/v1/profile', {
        name: profile.name,
        oab_number: profile.oab_number,
        preferred_language: profile.preferred_language,
        preferred_formality: profile.preferred_formality,
        nivel_tecnicidade: profile.nivel_tecnicidade,
        notify_enabled: profile.notify_enabled,
        privacidade_enviar_llm: profile.privacidade_enviar_llm,
        especialidades: profile.especialidades || [],
      });
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e?.message || 'Erro ao salvar perfil.');
    } finally {
      setBusy(false);
    }
  };

  const handleAreaToggle = (areaId) => {
    const current = profile?.especialidades || [];
    const updated = current.includes(areaId)
      ? current.filter((a) => a !== areaId)
      : [...current, areaId];
    setProfile({ ...profile, especialidades: updated });
  };

  const handleAddCliente = async () => {
    if (!newCliente.nome.trim()) return;
    setClienteBusy(true);
    try {
      const created = await api.post('/api/v1/profile/clientes', newCliente);
      setClientes([...clientes, created]);
      setNewCliente({ nome: '', nivel_tecnicidade_saida: 3, tipo_pessoa: 'fisica', consentimento_lgpd: false });
    } catch (e) {
      setError(e?.message || 'Erro ao criar cliente.');
    } finally {
      setClienteBusy(false);
    }
  };

  if (!profile) {
    return <div className="page-pad"><p>{error || 'Carregando perfil…'}</p></div>;
  }

  return (
    <div className="page-pad" style={{ maxWidth: 720 }}>
      <h2 style={{ marginBottom: 24 }}>Meu Perfil</h2>

      {error && (
        <div role="alert" style={{ color: 'var(--danger)', marginBottom: 12 }}>{error}</div>
      )}

      <section style={{ marginBottom: 32 }}>
        <h3 style={{ marginBottom: 16 }}>Dados Gerais</h3>
        <div className="field">
          <label>Nome</label>
          <input className="input" value={profile.name || ''} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
        </div>
        <div className="field">
          <label>OAB</label>
          <input className="input" placeholder="Ex: SP 123456" value={profile.oab_number || ''} onChange={(e) => setProfile({ ...profile, oab_number: e.target.value })} />
        </div>
        <div className="field">
          <label>Formalidade de saída</label>
          <select className="input" value={profile.preferred_formality || 'accessible'} onChange={(e) => setProfile({ ...profile, preferred_formality: e.target.value })}>
            {FORMALITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Nível de tecnicidade (1–5): {profile.nivel_tecnicidade}</label>
          <input type="range" min={1} max={5} value={profile.nivel_tecnicidade || 3}
            onChange={(e) => setProfile({ ...profile, nivel_tecnicidade: parseInt(e.target.value, 10) })} style={{ width: '100%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--faint)' }}>
            <span>Acessível</span><span>Técnico</span>
          </div>
        </div>
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" id="notify" checked={!!profile.notify_enabled} onChange={(e) => setProfile({ ...profile, notify_enabled: e.target.checked })} />
          <label htmlFor="notify">Receber notificações</label>
        </div>
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" id="privacy" checked={!!profile.privacidade_enviar_llm} onChange={(e) => setProfile({ ...profile, privacidade_enviar_llm: e.target.checked })} />
          <label htmlFor="privacy">Autorizar envio de dados ao LLM externo (LGPD)</label>
        </div>
      </section>

      <section style={{ marginBottom: 32 }}>
        <h3 style={{ marginBottom: 16 }}>Áreas de Especialidade</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {AREAS.map((area) => {
            const selected = (profile.especialidades || []).includes(area.id);
            return (
              <button key={area.id} type="button"
                className={'btn btn-sm' + (selected ? ' btn-primary' : '')}
                onClick={() => handleAreaToggle(area.id)}>
                {area.label}
              </button>
            );
          })}
        </div>
      </section>

      <div style={{ marginBottom: 32 }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={busy}>
          {busy ? 'Salvando…' : 'Salvar perfil'}
        </button>
        {saved && <span style={{ marginLeft: 12, color: 'var(--success, green)', fontSize: 14 }}>Salvo!</span>}
      </div>

      <section>
        <h3 style={{ marginBottom: 16 }}>Clientes</h3>
        {clientes.length === 0 && <p style={{ color: 'var(--faint)' }}>Nenhum cliente cadastrado.</p>}
        {clientes.map((c) => (
          <div key={c.cliente_id} style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '10px 14px', marginBottom: 8 }}>
            <strong>{c.nome}</strong>
            <span style={{ marginLeft: 12, fontSize: 12, color: 'var(--faint)' }}>
              Tecnicidade: {c.nivel_tecnicidade_saida} | {c.tipo_pessoa} | LGPD: {c.consentimento_lgpd ? 'Sim' : 'Não'}
            </span>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12, alignItems: 'flex-end' }}>
          <div className="field" style={{ flex: '1 1 180px', margin: 0 }}>
            <label style={{ fontSize: 12 }}>Nome do cliente</label>
            <input className="input" value={newCliente.nome} onChange={(e) => setNewCliente({ ...newCliente, nome: e.target.value })} placeholder="Nome" />
          </div>
          <div className="field" style={{ flex: '0 0 auto', margin: 0 }}>
            <label style={{ fontSize: 12 }}>Tecnicidade</label>
            <input type="number" className="input" min={1} max={5} value={newCliente.nivel_tecnicidade_saida}
              onChange={(e) => setNewCliente({ ...newCliente, nivel_tecnicidade_saida: parseInt(e.target.value, 10) })} style={{ width: 64 }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" id="novo-lgpd" checked={newCliente.consentimento_lgpd}
              onChange={(e) => setNewCliente({ ...newCliente, consentimento_lgpd: e.target.checked })} />
            <label htmlFor="novo-lgpd" style={{ fontSize: 12 }}>Consentimento LGPD</label>
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleAddCliente} disabled={clienteBusy || !newCliente.nome.trim()}>
            {clienteBusy ? 'Adicionando…' : '+ Adicionar'}
          </button>
        </div>
      </section>
    </div>
  );
}
