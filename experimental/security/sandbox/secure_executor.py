"""Experimental secure execution utilities preserved for reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class SecureExecutor:
    """Placeholder executor that would run commands inside a sandbox."""

    allowed_binaries: Iterable[str]

    def validate_command(self, command: Iterable[str]) -> bool:
        """Validate command to ensure it only uses allowed binaries."""
        iterator = iter(command)
        try:
            binary = next(iterator)
        except StopIteration:
            return False
        return binary in set(self.allowed_binaries)

    def execute(self, command: Iterable[str]) -> None:
        """Simulate execution raising error to avoid real execution."""
        if not self.validate_command(command):
            raise ValueError("Command not permitted in SecureExecutor sandbox")
        raise RuntimeError("SecureExecutor is experimental and disabled for MVP")
