from __future__ import annotations

from datetime import datetime
from typing import Any

from pkusleeper.domain import SleepEnvironment, SleepRecord, SleepReport, SleepSessionDraft, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.services.achievements import AchievementManager
from pkusleeper.services.goals import GoalManager
from pkusleeper.services.map import SleepMapManager
from pkusleeper.services.sleep import SleepManager
from pkusleeper.services.users import UserManager
from pkusleeper.states import SleepingState, State
from pkusleeper.storage import SleepRecordRepository


class MainTracker:
    """
    供 UI 和命令行入口使用的轻量门面。

    该类只负责协调各服务，不直接实现所有功能。
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
        """兼容旧接口，访问当前睡眠状态。"""
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
        """切换 UI 视图状态，不影响当前睡眠会话。"""
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
        """返回可供 UI 直接渲染的简要状态数据。"""
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
