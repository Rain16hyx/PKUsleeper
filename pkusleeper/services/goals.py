from __future__ import annotations

from typing import Any

from pkusleeper.domain import SleepGoal, SleepRecord


class GoalManager:
    def __init__(self, record_repository: Any = None) -> None:
        self.repository = record_repository
        self._sleep_goal: SleepGoal | None = None

    @property
    def sleep_goal(self) -> SleepGoal | None:
        """内存为空时从 repository 读取当前目标。"""
        if self._sleep_goal is None and self.repository is not None:
            self._sleep_goal = self.repository.load_current_goal()
        return self._sleep_goal

    @sleep_goal.setter
    def sleep_goal(self, new_goal: SleepGoal) -> None:
        self._sleep_goal = new_goal

    def evaluate(self, record: SleepRecord) -> list[SleepGoal]:
        """判断本次睡眠是否完成当前目标。"""
        goal = self.sleep_goal
        if goal is None or record.started_at is None or record.ended_at is None:
            return []

        expected_minutes = goal.target_duration_minutes or 480
        actual_minutes = (record.ended_at - record.started_at).total_seconds() / 60
        return [goal] if actual_minutes >= expected_minutes else []

    def update(self, completed_goals: list[SleepGoal]) -> None:
        """当前版本只需要保留目标本身，完成记录由 UI 统计历史数据。"""
        return None
