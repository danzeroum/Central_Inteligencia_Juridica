"""Experimental Docker sandbox integration placeholder."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DockerSandbox:
    """Placeholder Docker sandbox configuration."""

    image: str = "python:3.11-alpine"

    def build(self) -> None:
        raise RuntimeError("DockerSandbox is experimental and disabled for MVP")

    def run(self, command: list[str]) -> None:
        raise RuntimeError("DockerSandbox is experimental and disabled for MVP")
