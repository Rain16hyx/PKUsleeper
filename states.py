"""Workflow and view state helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

from models import (
    Roommate,
    SleepAchievement,
    SleepEnvironment,
    SleepGoal,
    SleepInterruption,
    SleepRecord,
    SleepReport,
    SleepSessionDraft,
    SleepType,
    User,
)


class State(ABC):
    """Base class for explicit application states."""

    @abstractmethod
    def name(self) -> str:
        """Return a stable state name for UI or debugging."""
        raise NotImplementedError


class SleepingState(State):
    """
    State object for one active sleep session.

    It owns only session-level data. It does not call services, repositories,
    or managers directly.
    """

    def __init__(self, session: SleepSessionDraft) -> None:
        self.session = session
        self.active_interruption: SleepInterruption | None = None

    def name(self) -> str:
        return "sleeping"

    def record_interruption(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> SleepInterruption:
        """Start one interruption during the current sleep session."""
        if self.active_interruption is not None:
            raise RuntimeError("There is already an active interruption.")

        interruption = SleepInterruption(started_at=interrupted_at, reason=reason)
        self.active_interruption = interruption
        return interruption

    def resume_sleeping(self, resumed_at: datetime) -> SleepInterruption:
        """Finish the active interruption and continue sleeping."""
        if self.active_interruption is None:
            raise RuntimeError("There is no active interruption to finish.")

        interruption = self.active_interruption
        interruption.ended_at = resumed_at
        self.session.interruptions.append(interruption)
        self.active_interruption = None
        return interruption

    def finalize_sleep(self, ended_at: datetime) -> SleepRecord:
        """Convert the active session draft into a finalized sleep record."""
        if self.active_interruption is not None:
            self.active_interruption.ended_at = ended_at
            self.session.interruptions.append(self.active_interruption)
            self.active_interruption = None

        return SleepRecord(
            record_id=uuid4().hex,
            user_id=self.session.user_id,
            started_at=self.session.started_at,
            ended_at=ended_at,
            expected_duration_minutes=self.session.expected_duration_minutes,
            expected_start_time=self.session.metadata.get(
                "expected_start_time",
                self.session.started_at,
            ),
            sleep_type=self.session.sleep_type,
            environment=self.session.environment,
            interruptions=tuple(self.session.interruptions),
        )


class AchievementState(State):
    """State container for achievement display and evaluation data."""

    def __init__(self) -> None:
        self.all_achievements: list[SleepAchievement] = []
        self.unlocked_achievements: list[SleepAchievement] = []

    def name(self) -> str:
        return "achievement"

    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        locked = [
            achievement
            for achievement in self.all_achievements
            if achievement not in self.unlocked_achievements
        ]
        return {
            "unlocked": self.unlocked_achievements,
            "locked": locked,
        }

    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        newly_unlocked: list[SleepAchievement] = []

        for achievement in self.all_achievements:
            if achievement in self.unlocked_achievements:
                continue
            if achievement.fulfilled_by(record):
                newly_unlocked.append(achievement)
                self.unlocked_achievements.append(achievement)

        return newly_unlocked


class SleepReportState(State):
    """State helper for report display and sharing."""

    def __init__(self, report_builder: Any | None = None) -> None:
        self.report_builder = report_builder

    def name(self) -> str:
        return "report"

    def generate_daily_report(self, record: SleepRecord) -> SleepReport:
        if self.report_builder is None:
            raise RuntimeError("No report builder is configured.")
        return self.report_builder.build(record)

    def export_report_for_sharing(self, report: SleepReport) -> str:
        if report.record is None:
            raise ValueError("Cannot export an empty sleep report.")

        record = report.record
        date_text = record.started_at.strftime("%Y-%m-%d")
        actual_minutes = report.actual_duration_minutes or 0
        hours = actual_minutes // 60
        minutes = actual_minutes % 60
        duration_text = f"{hours}h {minutes}m" if hours else f"{minutes}m"
        summary = report.summary or "Sleep check-in completed."

        return (
            "PKUSleeper Sleep Check-in\n"
            f"Date: {date_text}\n"
            f"Duration: {duration_text}\n"
            f"Score: {report.quality_score}\n"
            f"Summary: {summary}"
        )


class SleepGoalState(State):
    """State helper for goal editing and suggestion UI."""

    def __init__(
        self,
        goal_manager: Any | None = None,
        schedule_storage: dict[str, Any] | None = None,
    ) -> None:
        self.goal_manager = goal_manager
        self.schedule_storage = schedule_storage if schedule_storage is not None else {}

    def name(self) -> str:
        return "goal_management"

    def set_manual_goal(
        self,
        goal_type: str,
        target_value: float,
        difficulty_level: int,
    ) -> SleepGoal:
        new_goal = SleepGoal(
            goal_id=uuid4().hex,
            goal_type=goal_type,
            target_value=target_value,
            difficulty_level=difficulty_level,
        )
        if self.goal_manager is not None:
            self.goal_manager.add_goal(new_goal)
        return new_goal

    def import_schedule(self, schedule_data: dict[str, Any]) -> None:
        self.schedule_storage = schedule_data

    def generate_sleep_suggestions(self, roommates: list[Roommate]) -> str:
        if not self.schedule_storage:
            return "No schedule data is available."

        has_early_class = any(
            time_text < "08:30" for time_text in self.schedule_storage.values()
        )
        has_roommates = len(roommates) > 0

        if has_early_class and has_roommates:
            return "Sleep before 23:00 and consider using earplugs."
        if has_early_class:
            return "Sleep before 23:30 for tomorrow's early class."
        return "Keep a stable sleep rhythm."

    def check_reminders(self, current_time: datetime) -> list[str]:
        """Return sleep reminders for the current time."""
        raise NotImplementedError


class UserProfileState(State):
    """State helper for profile display data."""

    def __init__(
        self,
        current_user: User,
        roommate_list: list[Roommate] | None = None,
        all_records: list[SleepRecord] | None = None,
    ) -> None:
        self.current_user = current_user
        self.roommate_list = roommate_list if roommate_list is not None else []
        self.all_records = all_records if all_records is not None else []
        self.current_level = 1
        self.current_experience = 0

    def name(self) -> str:
        return "user_profile"

    def load_personal_info(self) -> User:
        return self.current_user

    def update_personal_info(self, new_username: str | None = None) -> User:
        if new_username:
            self.current_user.username = new_username
        return self.current_user

    def add_experience(self, exp_gained: int) -> tuple[int, int]:
        if exp_gained > 0:
            self.current_experience += exp_gained
            while self.current_experience >= 100:
                self.current_experience -= 100
                self.current_level += 1
        return self.current_level, self.current_experience

    def manage_roommates(
        self,
        action: str,
        roommate: Roommate | None = None,
    ) -> list[Roommate]:
        if action == "add" and roommate and roommate not in self.roommate_list:
            self.roommate_list.append(roommate)
        elif action == "remove" and roommate:
            self.roommate_list = [
                item
                for item in self.roommate_list
                if item.roommate_id != roommate.roommate_id
            ]
        return self.roommate_list

    def load_history_summary(self) -> dict[str, Any]:
        total_days = len(self.all_records)
        if total_days == 0:
            return {
                "total_days": 0,
                "global_avg_hours": 0.0,
                "level": self.current_level,
                "experience": self.current_experience,
            }

        total_minutes = sum(
            int((record.ended_at - record.started_at).total_seconds() // 60)
            for record in self.all_records
        )
        return {
            "total_days": total_days,
            "global_avg_hours": round((total_minutes / total_days) / 60, 1),
            "level": self.current_level,
            "experience": self.current_experience,
        }


class SleepHistoryState(State):
    """State helper for history and statistics views."""

    def __init__(self, all_records: list[SleepRecord] | None = None) -> None:
        self.all_records = all_records if all_records is not None else []

    def name(self) -> str:
        return "sleep_history"
