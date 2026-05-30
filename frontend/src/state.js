// Estado leve compartilhado entre telas (ex.: solicitação selecionada para
// edição em "Modificar"). Evita prop-drilling sem trazer uma lib de estado.
export const store = {
  selectedRequest: null,
};

// Humaniza a ação proposta por um agente em campos jurídicos legíveis
// (resolve H2 — JSON cru). Mantém o payload original sob "detalhes técnicos".
export function humanizeAction(req) {
  const action = req.action || {};
  const ctx = req.context || {};
  const critical = Boolean(action.critical);
  const consensus = action.consensus ?? ctx.trust_score ?? null;

  const label =
    action.label ||
    ({
      peticionar: 'Protocolar petição',
      process_movements: 'Consultar movimentações',
      status_check: 'Verificar status do tribunal',
      jurisprudence_comparison: 'Comparar jurisprudência',
    }[action.type] || action.type || action.action || 'Ação proposta');

  const target =
    action.processo || action.numero_processo || action.proc || action.task || '—';

  const tribunal = action.tribunal || ctx.tribunal || (action.tribunais || [])[0] || '';

  let why;
  if (critical) why = 'Ação marcada como crítica — exige revisão humana (regra DMN #1).';
  else if (consensus != null && consensus < 0.6)
    why = `Consenso abaixo do limiar (${fmt(consensus)} < 0,60) — regra DMN #2.`;
  else if (ctx.autonomy_level === 'restricted')
    why = 'Nível de autonomia restrito para este agente — regra DMN #3.';
  else why = 'Operação requer supervisão humana.';

  return {
    critical,
    consensus,
    label,
    target,
    tribunal,
    why,
    agentName: ctx.agent_name || req.agent,
    autonomy: ctx.autonomy_level,
  };
}

export function fmt(n) {
  return typeof n === 'number' ? n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : n;
}
