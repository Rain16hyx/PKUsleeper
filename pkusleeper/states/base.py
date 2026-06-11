from __future__ import annotations

from abc import ABC, abstractmethod


class State(ABC):
    """Base class for explicit application states."""

    @abstractmethod
    def name(self) -> str:
        """Return a stable state name for UI or debugging."""
        raise NotImplementedError
