"""Custom Prometheus metrics for agent decision tracking."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ============================================
# MÉTRICAS DE DECISÕES DO AGENTE
# ============================================

agent_decisions_total = Counter(
    "agent_decisions_total",
    "Total decisions made by agents",
    labelnames=("agent", "decision_type", "outcome"),
)

agent_decision_confidence = Histogram(
    "agent_decision_confidence",
    "Confidence score of agent decisions",
    labelnames=("agent", "decision_type"),
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)

agent_decision_duration_seconds = Histogram(
    "agent_decision_duration_seconds",
    "Time taken to make a decision",
    labelnames=("agent", "decision_type"),
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# ============================================
# MÉTRICAS DE CONSENSO
# ============================================

consensus_attempts_total = Counter(
    "consensus_attempts_total",
    "Total consensus attempts",
    labelnames=("decision_type", "outcome"),
)

consensus_strength = Histogram(
    "consensus_strength",
    "Strength of consensus achieved",
    labelnames=("decision_type",),
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

consensus_participants = Gauge(
    "consensus_participants",
    "Number of agents participating in consensus",
    labelnames=("decision_type",),
)

consensus_decision_maker = Counter(
    "consensus_decision_maker_total",
    "Which agent won consensus most often",
    labelnames=("winning_agent", "decision_type"),
)

# ============================================
# MÉTRICAS DE HITL (Human-in-the-Loop)
# ============================================

hitl_requests_total = Counter(
    "hitl_requests_total",
    "Total HITL approval requests",
    labelnames=("agent", "status"),
)

hitl_approval_rate = Gauge(
    "hitl_approval_rate",
    "Percentage of approved HITL requests",
    labelnames=("agent",),
)

hitl_response_time_seconds = Histogram(
    "hitl_response_time_seconds",
    "Time taken for human to respond to HITL request",
    labelnames=("agent", "outcome"),
    buckets=(5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

hitl_queue_depth = Gauge(
    "hitl_queue_depth",
    "Number of pending HITL requests",
)

# ============================================
# MÉTRICAS DE AUTONOMIA
# ============================================

agent_autonomy_level = Gauge(
    "agent_autonomy_level",
    "Current autonomy level of agent (0-5)",
    labelnames=("agent",),
)

agent_trust_score = Gauge(
    "agent_trust_score",
    "Trust score of agent (0.0-1.0)",
    labelnames=("agent",),
)

autonomy_escalations_total = Counter(
    "autonomy_escalations_total",
    "Number of times autonomy was reduced due to failures",
    labelnames=("agent", "reason"),
)

# ============================================
# MÉTRICAS DE TRAJETÓRIA
# ============================================

agent_trajectory_steps = Histogram(
    "agent_trajectory_steps",
    "Number of steps in agent trajectory",
    labelnames=("agent", "task_type"),
    buckets=(1, 2, 3, 5, 7, 10, 15, 20, 30),
)

agent_trajectory_success_rate = Gauge(
    "agent_trajectory_success_rate",
    "Success rate of agent trajectories",
    labelnames=("agent",),
)

agent_reasoning_depth = Histogram(
    "agent_reasoning_depth",
    "Depth of reasoning chains",
    labelnames=("agent", "reasoning_type"),
    buckets=(1, 2, 3, 5, 7, 10),
)

# ============================================
# MÉTRICAS DE PADRÕES ATIVOS
# ============================================

active_patterns = Gauge(
    "agent_active_patterns",
    "Number of active patterns per agent",
    labelnames=("agent", "pattern_family"),
)

pattern_activation_total = Counter(
    "pattern_activation_total",
    "Total pattern activations",
    labelnames=("pattern", "agent"),
)

pattern_failure_total = Counter(
    "pattern_failure_total",
    "Total pattern failures",
    labelnames=("pattern", "agent", "failure_reason"),
)

# ============================================
# MÉTRICAS DE FALLBACK
# ============================================

fallback_triggers_total = Counter(
    "fallback_triggers_total",
    "Total fallback strategy activations",
    labelnames=("from_pattern", "to_pattern", "reason"),
)

fallback_success_rate = Gauge(
    "fallback_success_rate",
    "Success rate of fallback strategies",
    labelnames=("strategy",),
)


class DecisionMetricsCollector:
    """Helper class to simplify metric collection for agent decisions."""

    @staticmethod
    def record_decision(
        agent: str,
        decision_type: str,
        outcome: str,
        confidence: float,
        duration_seconds: float,
    ) -> None:
        """Record a complete agent decision with all metrics."""
        agent_decisions_total.labels(
            agent=agent,
            decision_type=decision_type,
            outcome=outcome,
        ).inc()

        agent_decision_confidence.labels(
            agent=agent,
            decision_type=decision_type,
        ).observe(confidence)

        agent_decision_duration_seconds.labels(
            agent=agent,
            decision_type=decision_type,
        ).observe(duration_seconds)

    @staticmethod
    def record_consensus(
        decision_type: str,
        strength: float,
        participants: int,
        winning_agent: str,
        outcome: str,
    ) -> None:
        """Record consensus metrics."""
        consensus_attempts_total.labels(
            decision_type=decision_type,
            outcome=outcome,
        ).inc()

        consensus_strength.labels(
            decision_type=decision_type,
        ).observe(strength)

        consensus_participants.labels(
            decision_type=decision_type,
        ).set(participants)

        consensus_decision_maker.labels(
            winning_agent=winning_agent,
            decision_type=decision_type,
        ).inc()

    @staticmethod
    def record_hitl_request(
        agent: str,
        status: str,
        response_time_seconds: float | None = None,
    ) -> None:
        """Record HITL request metrics."""
        hitl_requests_total.labels(
            agent=agent,
            status=status,
        ).inc()

        if response_time_seconds is not None:
            hitl_response_time_seconds.labels(
                agent=agent,
                outcome=status,
            ).observe(response_time_seconds)

    @staticmethod
    def update_hitl_queue_depth(depth: int) -> None:
        """Update HITL queue depth gauge."""
        hitl_queue_depth.set(depth)

    @staticmethod
    def update_agent_autonomy(agent: str, level: int, trust_score: float) -> None:
        """Update agent autonomy metrics."""
        agent_autonomy_level.labels(agent=agent).set(level)
        agent_trust_score.labels(agent=agent).set(trust_score)

    @staticmethod
    def record_pattern_activation(agent: str, pattern: str) -> None:
        """Record pattern activation."""
        pattern_activation_total.labels(
            pattern=pattern,
            agent=agent,
        ).inc()

    @staticmethod
    def record_pattern_failure(agent: str, pattern: str, reason: str) -> None:
        """Record pattern failure."""
        pattern_failure_total.labels(
            pattern=pattern,
            agent=agent,
            failure_reason=reason,
        ).inc()

    @staticmethod
    def record_fallback(from_pattern: str, to_pattern: str, reason: str) -> None:
        """Record fallback trigger."""
        fallback_triggers_total.labels(
            from_pattern=from_pattern,
            to_pattern=to_pattern,
            reason=reason,
        ).inc()


__all__ = ["DecisionMetricsCollector"]
