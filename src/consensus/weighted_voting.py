"""Weighted consensus engine for multi-agent decision making."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class AgentVote:
    """Representation of an individual agent vote with computed score."""

    agent: str
    score: float
    confidence: float
    weight: float
    proposal: Any


class WeightedConsensusEngine:
    """Compute consensus decisions using weighted confidence voting."""

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "tjsp": 1.0,
        "tjmg": 0.95,
        "tjrs": 0.9,
        "tjrj": 0.92,
        "stf": 1.1,
        "primary_tribunal": 1.0,
        "secondary_tribunal": 0.85,
        "auditor": 0.8,
    }

    def __init__(self, agent_weights: Dict[str, float] | None = None) -> None:
        custom_weights = agent_weights or {}
        merged = {**self.DEFAULT_WEIGHTS, **{k.lower(): v for k, v in custom_weights.items()}}
        self.agent_weights: Dict[str, float] = {k.lower(): float(v) for k, v in merged.items()}

    def set_weight(self, agent_id: str, weight: float) -> None:
        """Update weight for a specific agent."""

        self.agent_weights[agent_id.lower()] = float(max(0.1, weight))

    def get_weight(self, agent_id: str) -> float:
        """Retrieve configured weight for an agent (defaults to 1.0)."""

        return self.agent_weights.get(agent_id.lower(), 1.0)

    def reach_consensus(
        self,
        proposals: Dict[str, Dict[str, Any]],
        decision_type: str,
    ) -> Dict[str, Any]:
        """Calculate weighted consensus from agent proposals."""

        if not proposals:
            return {
                "decision_type": decision_type,
                "decision": None,
                "decision_maker": None,
                "consensus_strength": 0.0,
                "dissenting_opinions": [],
                "confidence_distribution": [],
            }

        cluster_scores: Dict[str, float] = {}
        cluster_members: Dict[str, List[AgentVote]] = {}
        confidence_distribution: List[Dict[str, Any]] = []

        for agent_id, payload in proposals.items():
            confidence = float(payload.get("confidence", 0.0))
            proposal = payload.get("proposal")
            weight = self.get_weight(agent_id)
            normalized_confidence = min(1.0, max(0.0, confidence))
            score = normalized_confidence * weight

            vote = AgentVote(
                agent=agent_id,
                score=round(score, 4),
                confidence=round(normalized_confidence, 4),
                weight=round(weight, 4),
                proposal=proposal,
            )

            cluster_key = self._serialize_proposal(proposal)
            cluster_scores[cluster_key] = cluster_scores.get(cluster_key, 0.0) + score
            cluster_members.setdefault(cluster_key, []).append(vote)

            confidence_distribution.append(
                {
                    "agent": agent_id,
                    "score": vote.score,
                    "confidence": vote.confidence,
                    "weight": vote.weight,
                }
            )

        winning_cluster_key, winning_score = self._select_winning_cluster(cluster_scores)
        winning_votes = cluster_members.get(winning_cluster_key, [])

        if not winning_votes:
            # Should not happen, but guard against inconsistent state
            return {
                "decision_type": decision_type,
                "decision": None,
                "decision_maker": None,
                "consensus_strength": 0.0,
                "dissenting_opinions": [],
                "confidence_distribution": confidence_distribution,
            }

        winning_votes_sorted = sorted(winning_votes, key=lambda vote: vote.score, reverse=True)
        winning_vote = winning_votes_sorted[0]
        supporting_agents = [vote.agent for vote in winning_votes_sorted]

        dissenting: List[Dict[str, Any]] = []
        for cluster_key, votes in cluster_members.items():
            if cluster_key == winning_cluster_key:
                continue
            for vote in votes:
                dissenting.append(
                    {
                        "agent": vote.agent,
                        "score": vote.score,
                        "proposal": vote.proposal,
                    }
                )

        consensus_strength = round(min(1.0, winning_score), 4)

        decision_payload = {
            "proposal": winning_vote.proposal,
            "score": round(winning_score, 4),
            "supporting_agents": supporting_agents,
        }

        return {
            "decision_type": decision_type,
            "decision_maker": winning_vote.agent,
            "decision": decision_payload,
            "consensus_strength": consensus_strength,
            "dissenting_opinions": dissenting,
            "confidence_distribution": confidence_distribution,
        }

    def _select_winning_cluster(
        self, cluster_scores: Dict[str, float]
    ) -> Tuple[str, float]:
        """Select cluster with highest accumulated score."""

        winning_cluster = max(
            cluster_scores.items(),
            key=lambda item: (round(item[1], 6), item[0]),
        )
        return winning_cluster[0], winning_cluster[1]

    @staticmethod
    def _serialize_proposal(proposal: Any) -> str:
        """Create a deterministic representation for clustering proposals."""

        try:
            return json.dumps(proposal, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(proposal)
