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
        new_SleepInterruption = SleepInterruption(interrupted_at, reason=reason)
        self.active_interruption = new_SleepInterruption
        return new_SleepInterruption

    def resume_sleeping(self, resumed_at: datetime) -> SleepInterruption:
        """Finish the active interruption and continue the session."""
        if self.active_interruption:
            self.active_interruption.ended_at = resumed_at
            self.session.interruptions.append(self.active_interruption)
            self.active_interruption = None
        return self.session.interruptions[-1]

    def finalize_sleep(self, ended_at: datetime) -> SleepRecord:
        """Convert the mutable session draft into a finalized SleepRecord."""
        new_SleepRecord = SleepRecord(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.session.user_id,
            self.session.started_at,
            ended_at,
            self.session.expected_duration_minutes,
            self.session.sleep_type,
            self.session.environment,
            tuple(self.session.interruptions),
        )
        return new_SleepRecord
