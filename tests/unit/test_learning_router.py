"""Unit tests for LearningRouter."""

from __future__ import annotations

import pytest

from src.routing.learning_router import LearningRouter, RouteStats


@pytest.fixture
def router() -> LearningRouter:
    return LearningRouter()


class TestRouteStats:
    def test_initial_zero(self) -> None:
        stats = RouteStats()
        assert stats.calls == 0
        assert stats.success_rate == 0.0
        assert stats.average_latency == 0.0

    def test_record_success(self) -> None:
        stats = RouteStats()
        stats.record(success=True, latency=0.5)
        assert stats.calls == 1
        assert stats.success == 1
        assert stats.success_rate == 1.0

    def test_record_failure(self) -> None:
        stats = RouteStats()
        stats.record(success=False, latency=0.2)
        assert stats.calls == 1
        assert stats.failure == 1
        assert stats.success_rate == 0.0

    def test_mixed_records(self) -> None:
        stats = RouteStats()
        stats.record(True, 0.1)
        stats.record(True, 0.2)
        stats.record(False, 0.3)
        assert stats.calls == 3
        assert stats.success_rate == pytest.approx(2/3)
        assert stats.average_latency == pytest.approx(0.2)


class TestLearningRouter:
    def test_update_creates_entry(self) -> None:
        router = LearningRouter()
        router.update_route_performance(
            {"agent_type": "SupervisorAgent"}, "fast_route", True, 0.1
        )
        snapshot = router.get_route_snapshot()
        assert "SupervisorAgent" in snapshot
        assert "fast_route" in snapshot["SupervisorAgent"]
        assert snapshot["SupervisorAgent"]["fast_route"]["success_rate"] == 1.0

    def test_get_route_snapshot_empty(self) -> None:
        router = LearningRouter()
        snapshot = router.get_route_snapshot()
        assert isinstance(snapshot, dict)
        assert len(snapshot) == 0

    def test_multiple_routes(self) -> None:
        router = LearningRouter()
        router.update_route_performance({"agent_type": "A"}, "r1", True, 0.1)
        router.update_route_performance({"agent_type": "A"}, "r2", False, 0.2)
        snapshot = router.get_route_snapshot()
        assert len(snapshot["A"]) == 2
        assert snapshot["A"]["r1"]["calls"] == 1.0
        assert snapshot["A"]["r2"]["success_rate"] == 0.0
