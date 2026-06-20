"""Testes das métricas de concordância do WeightedConsensusEngine — C1.

Distingue "um agente confiante" de "vários agentes concordando", expondo
``participant_count``, ``agreeing_count``, ``agreement_ratio`` e ``single_source``
(aditivos — não alteram ``consensus_strength``).
"""

from __future__ import annotations

from src.consensus.weighted_voting import WeightedConsensusEngine


def _vote(score: float, proposal: dict) -> dict:
    return {"score": score, "weight": 1.0, "confidence": score, "proposal": proposal}


def test_single_source_is_flagged() -> None:
    engine = WeightedConsensusEngine()
    result = engine.reach_consensus({"TJSP": _vote(0.85, {"r": "ok"})}, "t")
    assert result["participant_count"] == 1
    assert result["agreeing_count"] == 1
    assert result["agreement_ratio"] == 1.0
    assert result["single_source"] is True


def test_two_agreeing_full_ratio_not_single_source() -> None:
    engine = WeightedConsensusEngine()
    result = engine.reach_consensus(
        {"TJSP": _vote(0.9, {"r": "ok"}), "TJMG": _vote(0.85, {"r": "ok"})}, "t"
    )
    assert result["participant_count"] == 2
    assert result["agreeing_count"] == 2
    assert result["agreement_ratio"] == 1.0
    assert result["single_source"] is False


def test_disagreement_half_ratio() -> None:
    engine = WeightedConsensusEngine()
    result = engine.reach_consensus(
        {"A": _vote(0.9, {"r": "x"}), "B": _vote(0.9, {"r": "y"})}, "t"
    )
    assert result["participant_count"] == 2
    assert result["agreeing_count"] == 1
    assert result["agreement_ratio"] == 0.5
    assert result["single_source"] is False


def test_empty_has_zero_metrics() -> None:
    engine = WeightedConsensusEngine()
    result = engine.reach_consensus({}, "t")
    assert result["participant_count"] == 0
    assert result["agreement_ratio"] == 0.0
    assert result["single_source"] is False
