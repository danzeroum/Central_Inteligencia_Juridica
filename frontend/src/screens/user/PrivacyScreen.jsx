import React from 'react';
import { Icon, Badge } from '../../components/primitives.jsx';

export default function PrivacyScreen() {
  return (
    <div className="screen">
      <div className="screen-head">
        <div className="screen-title">Privacidade (LGPD)</div>
        <div className="screen-sub">Gerencie seus dados pessoais na plataforma.</div>
      </div>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-head" style={{ marginBottom: 12 }}>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="privacy" style={{ width: 18, height: 18, color: 'var(--navy)' }} />
            Portal de Direitos do Titular (Art. 18 LGPD)
          </div>
          <Badge kind="navy">Fase 3</Badge>
        </div>
        <p style={{ color: 'var(--ink-2)', fontSize: 13.5, margin: '0 0 16px' }}>
          Esta seção está em desenvolvimento. Em breve você poderá:
        </p>
        <ul style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 8, fontSize: 13.5, color: 'var(--ink-2)' }}>
          <li><b>Acessar seus dados</b> — visualize todas as informações registradas sobre você (Art. 18, II).</li>
          <li><b>Exportar seus dados</b> — baixe um arquivo com tudo que foi armazenado em formato portável (Art. 18, V).</li>
          <li><b>Solicitar exclusão</b> — peça a remoção ou anonimização dos seus dados pessoais (Art. 18, VI).</li>
        </ul>
        <div style={{ marginTop: 20, padding: '12px 14px', background: 'var(--navy-tint)', borderRadius: 'var(--radius-sm)', fontSize: 13, color: 'var(--navy)' }}>
          <Icon name="info" style={{ width: 15, height: 15, verticalAlign: 'middle', marginRight: 6 }} />
          Enquanto esta tela não está disponível, entre em contato com o encarregado (DPO) pelo e-mail institucional.
        </div>
      </div>
    </div>
  );
}
