"""Application services for PKUSleeper."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models import (
    Node,
    Roommate,
    SleepAchievement,
    SleepEnvironment,
    SleepGoal,
    SleepRecord,
    SleepReport,
    SleepSessionDraft,
    SleepType,
    User,
)
from states import (
    AchievementState,
    MappingState,
    SleepingState,
    SleepReportState,
    State,
)
from storage import SleepRecordRepository
from utils.data_processing import SleepReportBuilder


class MainTracker:
    """
    Thin facade for UI and command-line entry points.

    It is reasonable to keep this controller as long as it coordinates services
    instead of implementing every feature itself.
    """

    def __init__(
        self,
        user_id: str,
        record_repository: SleepRecordRepository | None = None,
        report_builder: SleepReportBuilder | None = None,
    ) -> None:
        self.user_id = user_id
        self.repository = record_repository
        self.sleep_manager = SleepManager(
            user_id=user_id,
            record_repository=record_repository,
            report_builder=report_builder,
        )
        self.achievement_manager = AchievementManager()
        self.goal_manager = GoalManager(record_repository=record_repository)
        self.map_manager = SleepMapManager()
        self.user_manager = UserManager(user_id)
        self.current_view_state: State | None = None

    @property
    def current_state(self) -> SleepingState | None:
        """Backward-compatible access to the active sleep state."""
        return self.sleep_manager.current_state

    @property
    def active_session(self) -> SleepSessionDraft | None:
        return self.sleep_manager.active_session

    @property
    def latest_record(self) -> SleepRecord | None:
        return self.sleep_manager.latest_record

    @property
    def latest_report(self) -> SleepReport | None:
        return self.sleep_manager.latest_report

    @property
    def all_records(self) -> list[SleepRecord]:
        return self.sleep_manager.all_records

    def shift_state(self, new_state: State | None) -> None:
        """Switch UI/view state without changing the active sleep session."""
        self.current_view_state = new_state

    def start_sleeping(
        self,
        started_at: datetime,
        expected_duration_minutes: int | None,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> SleepingState:
        return self.sleep_manager.start_sleeping(
            started_at=started_at,
            expected_duration_minutes=expected_duration_minutes,
            sleep_type=sleep_type,
            environment=environment,
        )

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        self.sleep_manager.interrupt_sleep(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        self.sleep_manager.continue_sleeping(resumed_at)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        record = self.sleep_manager.wake_up(ended_at)

        self.achievement_manager.evaluate_new_achievements(record)

        completed_goals = self.goal_manager.evaluate(record)
        self.goal_manager.update(completed_goals)

        newly_unlocked_nodes = self.map_manager.evaluate(record)
        self.map_manager.update(newly_unlocked_nodes)

        return record

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        return self.sleep_manager.generate_sleep_report(record)

    def is_sleeping(self) -> bool:
        return self.sleep_manager.is_sleeping()

    def get_ui_snapshot(self) -> dict[str, Any]:
        """Return simple state data that a future UI can render directly."""
        return {
            "user_id": self.user_id,
            "is_sleeping": self.is_sleeping(),
            "active_session": self.active_session,
            "latest_record": self.latest_record,
            "latest_report": self.latest_report,
            "current_view": (
                self.current_view_state.name() if self.current_view_state else None
            ),
        }


class SleepManager:
    """Service responsible for the sleep-session workflow."""

    def __init__(
        self,
        user_id: str,
        record_repository: SleepRecordRepository | None = None,
        report_builder: SleepReportBuilder | None = None,
    ) -> None:
        self.user_id = user_id
        self.record_repository = record_repository
        self.report_builder = report_builder
        self.current_state: SleepingState | None = None
        self.active_session: SleepSessionDraft | None = None
        self.all_records: list[SleepRecord] = []
        self.latest_record: SleepRecord | None = None
        self.latest_report: SleepReport | None = None

    def start_sleeping(
        self,
        started_at: datetime,
        expected_duration_minutes: int | None,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> SleepingState:
        if self.current_state is not None:
            raise RuntimeError("A sleep session is already active.")

        self.active_session = SleepSessionDraft(
            user_id=self.user_id,
            started_at=started_at,
            expected_duration_minutes=expected_duration_minutes,
            sleep_type=sleep_type,
            environment=environment,
        )
        self.current_state = SleepingState(self.active_session)
        return self.current_state

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        self._require_sleeping_state().record_interruption(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        self._require_sleeping_state().resume_sleeping(resumed_at)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        state = self._require_sleeping_state()
        record = state.finalize_sleep(ended_at)

        self.latest_record = record
        self.all_records.append(record)
        self.current_state = None
        self.active_session = None

        if self.record_repository is not None:
            self.record_repository.save(record)

        return record

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        if self.report_builder is None:
            raise RuntimeError("No report builder is configured.")
        self.latest_report = self.report_builder.build(record)
        return self.latest_report

    def is_sleeping(self) -> bool:
        return self.current_state is not None

    def _require_sleeping_state(self) -> SleepingState:
        if self.current_state is None:
            raise RuntimeError("No active sleep session.")
        return self.current_state


class AchievementManager:
    """Service facade for achievement state."""

    def __init__(self, state: AchievementState | None = None) -> None:
        self._state = state if state is not None else AchievementState()

    @property
    def all_achievements(self) -> list[SleepAchievement]:
        return self._state.all_achievements

    @property
    def unlocked_achievements(self) -> list[SleepAchievement]:
        return self._state.unlocked_achievements

    def init_all_achievements(self, achievements: list[SleepAchievement]) -> None:
        self._state.all_achievements = achievements

    def init_unlocked_achievements(self, achievements: list[SleepAchievement]) -> None:
        self._state.unlocked_achievements = achievements

    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        return self._state.load_user_achievements()

    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        return self._state.evaluate_new_achievements(record)


class GoalManager:
    def __init__(self, record_repository: Any = None) -> None:
        self.repository = record_repository
        self._sleep_goal: SleepGoal | None = None

    @property
    def sleep_goal(self) -> SleepGoal | None:
        """
        当外部访问 .sleep_goal 时，如果内存为空，自动触发通过 repository 捞取数据
        """
        if self._sleep_goal is None:
            if self.repository:
                self._sleep_goal = self.repository.load_current_goal()
        return self._sleep_goal

    @sleep_goal.setter
    def sleep_goal(self, new_goal: SleepGoal) -> None:
        self._sleep_goal = new_goal

class SleepMapManager:
    """Service for sleep map unlock progress."""

    def __init__(self) -> None:
        self.all_available_nodes: list[Node] = []
        self.unlocked_nodes: list[Node] = []

    def as_state(self) -> MappingState:
        return MappingState(self.all_available_nodes, self.unlocked_nodes)

    def load_map_nodes(self) -> dict[str, Any]:
        return self.as_state().load_map_nodes()

    def evaluate(self, record: SleepRecord | None) -> list[Node]:
        return self.as_state().evaluate_new_unlocks(record)

    def update(self, newly_unlocked: list[Node]) -> None:
        for node in newly_unlocked:
            if node not in self.unlocked_nodes:
                self.unlocked_nodes.append(node)

    def view_node_details(self, node_id: str) -> dict[str, Any]:
        return self.as_state().view_node_details(node_id)


class UserManager:
    """Service for user profile, roommates, and schedule data."""

    def __init__(self, user_id: str) -> None:
        self.current_user = User(user_id=user_id, username="PKU student")
        self.roommate_list: list[Roommate] = []
        self.current_level: int = 1
        self.current_experience: int = 0
        self.schedule_storage: dict[str, Any] = {}

    def update_personal_info(self, new_username: str | None = None) -> User:
        if new_username:
            self.current_user.username = new_username
        return self.current_user

    def add_roommate(self, roommate: Roommate) -> None:
        if roommate not in self.roommate_list:
            self.roommate_list.append(roommate)

    def remove_roommate(self, roommate_id: str) -> None:
        self.roommate_list = [
            roommate
            for roommate in self.roommate_list
            if roommate.roommate_id != roommate_id
        ]

    def import_schedule(self, schedule_data: dict[str, Any]) -> None:
        self.schedule_storage = schedule_data

    def add_experience(self, exp_gained: int) -> tuple[int, int]:
        if exp_gained > 0:
            self.current_experience += exp_gained
            while self.current_experience >= 100:
                self.current_experience -= 100
                self.current_level += 1
        return self.current_level, self.current_experience


class SleepAdvisor:
    def generate_sleep_suggestions(
        self,
        schedule_data: dict[str, Any],
        roommates: list[Roommate],
    ) -> str:
        if not schedule_data:
            return "No schedule data is available."

        has_early_class = any(
            time_text < "08:30" for time_text in schedule_data.values()
        )
        has_roommates = len(roommates) > 0

        if has_early_class and has_roommates:
            return "Sleep before 23:00 and consider using earplugs."
        if has_early_class:
            return "Sleep before 23:30 for tomorrow's early class."
        return "Keep a stable sleep rhythm."


class SleepReportManager:
    def __init__(self, report_builder: SleepReportBuilder | None = None) -> None:
        self._state = SleepReportState(report_builder)

    def generate_daily_report(self, record: SleepRecord) -> SleepReport:
        return self._state.generate_daily_report(record)

    def export_report_for_sharing(self, report: SleepReport) -> str:
        return self._state.export_report_for_sharing(report)
