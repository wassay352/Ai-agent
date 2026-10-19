"""Base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request and return the assistant message."""
        ...

    @abstractmethod
    def health(self) -> tuple[bool, str]:
        """Check if the provider is reachable."""
        ...
