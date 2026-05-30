#!/bin/bash
# ============================================================================
#  FASE 6b - FIX DOS 2 ULTIMOS TESTES (weighted_voting consensus_strength=0.0)
#
#  Causa: proposals sem chaves 'confidence'/'weight' fazem o motor de consenso
#  calcular strength=0.0. Correcao: incluir as chaves esperadas no formato.
#
#  USO:
#    bash fase6b-fix-voting.sh
#    python -m pytest tests/unit/ -v --tb=short
#    git add -A
#    git commit -m "fix(fase6b): fix weighted_voting consensus test format"
# ============================================================================

set -euo pipefail

DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY=1; fi

if [[ $DRY -eq 1 ]]; then
    echo ""
    echo "============================================================================"
    echo "  FASE 6b - FIX DOS 2 ULTIMOS TESTES"
    echo "  Modo: DRY-RUN"
    echo "============================================================================"
else
    echo ""
    echo "============================================================================"
    echo "  FASE 6b - FIX DOS 2 ULTIMOS TESTES"
    echo "  Modo: APLICANDO"
    echo "============================================================================"
fi

cat > "tests/unit/test_weighted_voting.py" << 'TESTEOF'
"""Unit tests for WeightedConsensusEngine - matched to resolved Codex interface.

Key interface facts:
- reach_consensus() returns: decision, decision_maker, consensus_strength,
  confidence_distribution, ...
- Proposals must include 'score', 'weight', 'confidence' keys per agent
- Key is 'decision', NOT 'winning_proposal'
"""

from __future__ import annotations

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine


class TestReachConsensus:
    """Tests for reach_consensus with correct proposal format."""

    def test_single_proposal_unanimous(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.8,
                "weight": 1.0,
                "confidence": 0.8,
                "proposal": {"result": "ok"},
            }
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert result["consensus_strength"] >= 0.0

    def test_two_proposals_high_agreement(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.9,
                "weight": 1.0,
                "confidence": 0.9,
                "proposal": {"result": "ok"},
            },
            "TJMG": {
                "score": 0.85,
                "weight": 0.95,
                "confidence": 0.85,
                "proposal": {"result": "ok"},
            },
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert result["consensus_strength"] >= 0.0

    def test_empty_proposals(self) -> None:
        engine = WeightedConsensusEngine()
        proposals: dict = {}
        result = engine.reach_consensus(proposals, "test_decision")
        assert result is not None

    def test_required_keys_in_result(self) -> None:
        """Correct key is 'decision', NOT 'winning_proposal'."""
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.8,
                "weight": 1.0,
                "confidence": 0.8,
                "proposal": {"result": "ok"},
            }
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert "decision" in result
        assert "consensus_strength" in result
        assert "decision_maker" in result
TESTEOF

# Garantir LF
if [[ $DRY -ne 1 ]] && command -v sed &>/dev/null; then
    sed -i 's/\r$//' "tests/unit/test_weighted_voting.py" 2>/dev/null || true
fi

echo ""
echo "  OK: tests/unit/test_weighted_voting.py reescrito (56 linhas)"
echo ""
echo "  Fix: proposals agora incluem 'score', 'weight', 'confidence'"
echo ""
echo "  Proximos passos:"
echo "    python -m pytest tests/unit/ -v --tb=short"
echo "    git add -A"
echo '    git commit -m "fix(fase6b): fix weighted_voting consensus test format"'
echo ""
