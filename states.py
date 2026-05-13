"""State objects for the sleep tracking workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from models import SleepInterruption, SleepRecord, SleepSessionDraft

if TYPE_CHECKING:
    from service import SleepTracker


class State(ABC):
    def __init__(self, tracker: "SleepTracker") -> None:
        self.tracker = tracker

    @abstractmethod
    def name(self) -> str:
        """Return a stable state name for UI or debugging."""
        raise NotImplementedError


class SleepingState(State):
    """
    State active after the user starts sleeping and before final wake-up.
    """

    def __init__(self, tracker: "SleepTracker", session: SleepSessionDraft) -> None:
        super().__init__(tracker)
        self.session = session
        self.active_interruption: SleepInterruption | None = None

    def name(self) -> str:
        return "sleeping"

    def record_interruption(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> SleepInterruption:
        """Start tracking one interruption during the current sleep session."""
        raise NotImplementedError

    def resume_sleeping(self, resumed_at: datetime) -> SleepInterruption:
        """Finish the active interruption and continue the session."""
        raise NotImplementedError

    def finalize_sleep(self, ended_at: datetime) -> SleepRecord:
        """Convert the mutable session draft into a finalized SleepRecord."""
        raise NotImplementedError
