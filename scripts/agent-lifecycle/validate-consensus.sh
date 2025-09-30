#!/usr/bin/env bash
set -euo pipefail

echo "🤝 Validando Consenso Multi-Agente..."

# Teste unitário do consensus engine
echo "1️⃣ Testando WeightedConsensusEngine..."
python -c "
from src.consensus.weighted_voting import WeightedConsensusEngine

engine = WeightedConsensusEngine()
proposals = {
    'agent_a': {'confidence': 0.9, 'proposal': {'tribunal': 'TJSP'}},
    'agent_b': {'confidence': 0.7, 'proposal': {'tribunal': 'TJMG'}},
}

result = engine.reach_consensus(proposals, 'test')
print(f'✅ Consensus Engine OK: {result[\'decision_maker\']}')
"

# Teste integração com supervisor
echo "2️⃣ Testando integração Supervisor + Consensus..."
python -c "
import asyncio
from src.agents.supervisor_agent import SupervisorAgent

async def main() -> None:
    supervisor = SupervisorAgent()
    result = await supervisor.process_task('Decisão crítica sobre TJSP')
    if 'consensus' in result and result['consensus']:
        strength = result['consensus']['strength']
        print(f'✅ Consensus ativado: strength={strength:.2f}')
    else:
        print('⚠️  Consensus não ativado (esperado para tarefas simples)')

asyncio.run(main())
"

# Teste emergente
echo "3️⃣ Executando testes emergentes..."
pytest tests/emergent/test_consensus_resolution.py -v

echo "✅ Validação de Consenso Concluída!"
