"""Unit tests for LearningRouter."""

from __future__ import annotations

import pytest

from src.routing.learning_router import LearningRouter


@pytest.fixture
def router() -> LearningRouter:
    return LearningRouter()


class TestUpdateAndGetRoutePerformance:
    def test_initial_stats_empty(self, router: LearningRouter) -> None:
        snapshot = router.get_route_snapshot()
        assert isinstance(snapshot, dict)

    def test_update_creates_entry(self, router: LearningRouter) -> None:
        router.update_route_performance("TestAgent", "fast_route", success=True, latency=0.1)
        snapshot = router.get_route_snapshot()
        assert ("TestAgent", "fast_route") in snapshot
