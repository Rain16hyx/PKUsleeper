"""Application services for sleep tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from models import (
    SleepAchievement,
    SleepEnvironment,
    SleepGoal,
    SleepRecord,
    SleepReport,
    SleepSessionDraft,
    SleepType,
)
from states import SleepingState, State
from utils.data_processing import SleepReportBuilder


class SleepRecordRepository(Protocol):
    def save(self, record: SleepRecord) -> None:
        """Persist one finalized sleep record."""
        raise NotImplementedError


class SleepTracker:
    """
    Application service that coordinates state transitions and data persistence.

    Recommended direction:
    - UI/controller calls SleepTracker.
    - SleepTracker delegates in-session behavior to SleepingState.
    - SleepingState edits SleepSessionDraft.
    - Wake-up produces SleepRecord.
    - Repositories/report builders handle storage and analysis afterward.
    """

    def __init__(
        self,
        user_id: str,
        record_repository: SleepRecordRepository | None = None,
        report_builder: SleepReportBuilder | None = None,
    ) -> None:
        self.user_id = user_id
        self.record_repository = record_repository
        self.report_builder = report_builder
        self.current_state: State | None = None
        self.active_session: SleepSessionDraft | None = None
        self.latest_record: SleepRecord | None = None
        self.latest_report: SleepReport | None = None

    def start_sleeping(
        self,
        started_at: datetime,
        expected_duration_minutes: int | None,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> SleepingState:
        """Open a new session and enter SleepingState."""
        self.active_session = SleepSessionDraft(
            self.user_id,
            started_at,
            expected_duration_minutes,
            sleep_type,
            environment,
            [],
            {},
        )
        self.current_state = SleepingState(self, self.active_session)
        return self.current_state

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        """Delegate an interruption event to the current SleepingState."""
        self.current_state.record_interruption(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        """Delegate a resume event to the current SleepingState."""
        interruption = self.current_state.resume_sleeping(resumed_at)
        self.active_session.interruptions.append(interruption)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        """
        Finalize the current session, leave SleepingState,
        persist the record, and optionally build a report.
        """
        self.current_state.finalize_sleep(ended_at)

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        """Create a sleep report through the configured report builder."""
        raise NotImplementedError

    def is_sleeping(self) -> bool:
        """Return whether the tracker is currently in SleepingState."""
        return isinstance(self.current_state, SleepingState)


class AchievementManager:
    def __init__(self) -> None:
        self.all_achievements: list[SleepAchievement] = []
        self.unlocked_achievements: list[SleepAchievement] = []

    def evaluate(self, record: SleepRecord) -> list[SleepAchievement]:
        """Return achievements unlocked by one record."""
        unlocked = []
        for i in range(len(self.all_achievements)):
            acv = self.all_achievements[i]
            if acv not in self.unlocked_achievements and acv.fulfilled_by(record):
                unlocked.append(acv)
        return unlocked

    def update(self, unlocked: list[SleepAchievement]) -> None:
        """Add newly unlocked achievements to the user's profile."""
        self.unlocked_achievements.extend(unlocked)


class SleepGoalManager:
    def __init__(self) -> None:
        self.sleep_goals: list[SleepGoal] = []
        self.completed_goals: list[SleepGoal] = []

    def add_goal(self, goal: SleepGoal) -> None:
        """Register one goal for later evaluation."""
        self.sleep_goals.append(goal)

    def evaluate(self, record: SleepRecord) -> list[SleepGoal]:
        """Return goals completed by one record."""
        completed = []
        for i in range(len(self.sleep_goals)):
            goal = self.sleep_goals[i]
            if goal.fulfilled_by(record):
                completed.append(goal)
        return completed

    def update(self, completed: list[SleepGoal]) -> None:
        """Add newly completed goals to the user's profile."""
        self.completed_goals.extend(completed)
