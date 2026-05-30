"""Learning metrics collection and analysis for agent training."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricDataPoint:
    """Single data point for a metric."""

    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricWindow:
    """Rolling window of metric values."""

    name: str
    window_size: int
    values: Deque[MetricDataPoint] = field(default_factory=lambda: deque(maxlen=100))

    def add(self, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a new data point to the window."""

        self.values.append(
            MetricDataPoint(
                timestamp=datetime.now(timezone.utc),
                value=value,
                metadata=metadata or {},
            )
        )

    def mean(self) -> float:
        """Calculate mean of values in window."""

        if not self.values:
            return 0.0
        return sum(data_point.value for data_point in self.values) / len(self.values)

    def std(self) -> float:
        """Calculate standard deviation."""

        if len(self.values) < 2:
            return 0.0
        mean_value = self.mean()
        variance = sum((dp.value - mean_value) ** 2 for dp in self.values) / len(
            self.values
        )
        return variance**0.5

    def trend(self) -> str:
        """Determine if metric is improving, declining, or stable."""

        if len(self.values) < 2:
            return "insufficient_data"

        recent_half = list(self.values)[len(self.values) // 2 :]
        older_half = list(self.values)[: len(self.values) // 2]

        recent_mean = sum(dp.value for dp in recent_half) / len(recent_half)
        older_mean = sum(dp.value for dp in older_half) / len(older_half)

        change_percent = (
            ((recent_mean - older_mean) / older_mean * 100) if older_mean > 0 else 0
        )

        if abs(change_percent) < 5:
            return "stable"
        return "improving" if change_percent > 0 else "declining"

    def percentile(self, percentile_value: int) -> float:
        """Calculate percentile value."""

        if not self.values:
            return 0.0

        sorted_values = sorted(dp.value for dp in self.values)
        k = (len(sorted_values) - 1) * percentile_value / 100
        floor = int(k)
        ceil = floor + 1 if floor < len(sorted_values) - 1 else floor

        if floor == ceil:
            return sorted_values[floor]
        return sorted_values[floor] * (ceil - k) + sorted_values[ceil] * (k - floor)


class LearningMetricsCollector:
    """Collect and analyze learning-specific metrics for agents."""

    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self.metrics: Dict[str, Dict[str, MetricWindow]] = {}

    def record(
        self,
        agent_type: str,
        metric_name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a metric value for an agent."""

        if agent_type not in self.metrics:
            self.metrics[agent_type] = {}

        if metric_name not in self.metrics[agent_type]:
            self.metrics[agent_type][metric_name] = MetricWindow(
                name=metric_name,
                window_size=self.window_size,
            )

        self.metrics[agent_type][metric_name].add(value, metadata)
        logger.debug("Recorded %s for %s: %.3f", metric_name, agent_type, value)

    def get_metric_summary(self, agent_type: str, metric_name: str) -> Dict[str, Any]:
        """Get statistical summary of a metric."""

        if (
            agent_type not in self.metrics
            or metric_name not in self.metrics[agent_type]
        ):
            return {
                "error": f"No data for {agent_type}.{metric_name}",
                "available": False,
            }

        window = self.metrics[agent_type][metric_name]

        return {
            "metric": metric_name,
            "agent": agent_type,
            "available": True,
            "data_points": len(window.values),
            "statistics": {
                "mean": round(window.mean(), 4),
                "std": round(window.std(), 4),
                "p50": round(window.percentile(50), 4),
                "p95": round(window.percentile(95), 4),
                "p99": round(window.percentile(99), 4),
            },
            "trend": window.trend(),
            "latest": window.values[-1].value if window.values else None,
            "timestamp": (
                window.values[-1].timestamp.isoformat() if window.values else None
            ),
        }

    def get_agent_summary(self, agent_type: str) -> Dict[str, Any]:
        """Get summary of all metrics for an agent."""

        if agent_type not in self.metrics:
            return {
                "agent": agent_type,
                "error": "No metrics recorded",
                "metrics": {},
            }

        return {
            "agent": agent_type,
            "metrics": {
                metric_name: self.get_metric_summary(agent_type, metric_name)
                for metric_name in self.metrics[agent_type].keys()
            },
        }

    def compare_agents(
        self, agent_a: str, agent_b: str, metric_name: str
    ) -> Dict[str, Any]:
        """Compare a specific metric between two agents."""

        summary_a = self.get_metric_summary(agent_a, metric_name)
        summary_b = self.get_metric_summary(agent_b, metric_name)

        if not summary_a.get("available") or not summary_b.get("available"):
            return {
                "error": "Insufficient data for comparison",
                "agent_a": summary_a,
                "agent_b": summary_b,
            }

        mean_a = summary_a["statistics"]["mean"]
        mean_b = summary_b["statistics"]["mean"]

        better_agent = agent_a if mean_a >= mean_b else agent_b
        difference = abs(mean_a - mean_b)
        baseline = mean_b if better_agent == agent_a else mean_a
        percent_diff = (difference / baseline * 100) if baseline else 0.0

        return {
            "metric": metric_name,
            "agent_a": {
                "name": agent_a,
                "mean": mean_a,
                "trend": summary_a["trend"],
            },
            "agent_b": {
                "name": agent_b,
                "mean": mean_b,
                "trend": summary_b["trend"],
            },
            "comparison": {
                "absolute_difference": round(difference, 4),
                "percent_difference": round(percent_diff, 2),
                "better_performer": better_agent,
            },
        }

    def detect_anomalies(
        self, agent_type: str, metric_name: str, threshold_std: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Detect anomalous values in a metric using standard deviation."""

        if (
            agent_type not in self.metrics
            or metric_name not in self.metrics[agent_type]
        ):
            return []

        window = self.metrics[agent_type][metric_name]
        mean_value = window.mean()
        std_dev = window.std()

        if std_dev == 0:
            return []

        anomalies = []
        for data_point in window.values:
            z_score = abs((data_point.value - mean_value) / std_dev)
            if z_score > threshold_std:
                anomalies.append(
                    {
                        "timestamp": data_point.timestamp.isoformat(),
                        "value": data_point.value,
                        "z_score": round(z_score, 2),
                        "deviation_percent": (
                            round(
                                ((data_point.value - mean_value) / mean_value * 100), 2
                            )
                            if mean_value
                            else 0.0
                        ),
                        "metadata": data_point.metadata,
                    }
                )

        return anomalies

    def calculate_learning_rate(
        self, agent_type: str, metric_name: str, time_window_hours: int = 24
    ) -> Optional[float]:
        """Calculate learning rate (improvement per hour) for a metric."""

        if (
            agent_type not in self.metrics
            or metric_name not in self.metrics[agent_type]
        ):
            return None

        window = self.metrics[agent_type][metric_name]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        recent_points = [dp for dp in window.values if dp.timestamp >= cutoff]

        if len(recent_points) < 2:
            return None

        first_point = recent_points[0]
        last_point = recent_points[-1]

        time_diff_hours = (
            last_point.timestamp - first_point.timestamp
        ).total_seconds() / 3600
        value_diff = last_point.value - first_point.value

        if time_diff_hours == 0:
            return None

        return value_diff / time_diff_hours

    def export_metrics(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """Export metrics for external analysis."""

        if agent_type:
            if agent_type not in self.metrics:
                return {"error": f"No data for agent {agent_type}"}

            return {
                "agent": agent_type,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    metric_name: {
                        "summary": self.get_metric_summary(agent_type, metric_name),
                        "raw_data": [
                            {
                                "timestamp": data_point.timestamp.isoformat(),
                                "value": data_point.value,
                                "metadata": data_point.metadata,
                            }
                            for data_point in self.metrics[agent_type][
                                metric_name
                            ].values
                        ],
                    }
                    for metric_name in self.metrics[agent_type].keys()
                },
            }

        return {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": {
                agent: self.export_metrics(agent) for agent in self.metrics.keys()
            },
        }


_global_metrics_collector: Optional[LearningMetricsCollector] = None


def get_metrics_collector() -> LearningMetricsCollector:
    """Get or create the global metrics collector."""

    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = LearningMetricsCollector()
    return _global_metrics_collector


__all__ = [
    "LearningMetricsCollector",
    "MetricWindow",
    "MetricDataPoint",
    "get_metrics_collector",
]
