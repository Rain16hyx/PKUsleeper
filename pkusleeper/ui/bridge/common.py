from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

import pandas as pd

from pkusleeper.domain import SleepAchievement, SleepEnvironment, SleepRecord, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.ui.bridge.result import ActionResult


class BridgeCommonMixin:
    def _collect_records(self) -> list[SleepRecord]:
        records: list[SleepRecord] = []
        records.extend(getattr(self.tracker, "all_records", []) or [])
        records.extend(self._fallback_records)

        repository = getattr(self.tracker, "repository", None)
        if repository is not None:
            try:
                records.extend(repository.user_list(getattr(self.tracker, "user_id", "")))
            except Exception as exc:  # noqa: BLE001
                print(f"读取历史睡眠记录失败：{exc}")

        unique: dict[str, SleepRecord] = {}
        for record in records:
            if record.started_at and record.ended_at:
                unique[record.record_id] = record
        return list(unique.values())


    def _load_goal(self):
        goal = None
        goal_manager = getattr(self.tracker, "goal_manager", None)
        if goal_manager is not None:
            goal = goal_manager.sleep_goal

        if goal is None:
            repository = getattr(self.tracker, "repository", None)
            if repository is not None:
                goal = repository.load_current_goal()
                if goal_manager is not None:
                    goal_manager.sleep_goal = goal

        if goal is None:
            from pkusleeper.domain import SleepGoal

            goal = SleepGoal(
                target_value=8.0,
                target_duration_minutes=480,
                expected_sleep_start_time=datetime.strptime("23:30", "%H:%M"),
                difficulty_level=1,
            )
        return goal


    def _load_developer_state(self) -> dict[str, Any]:
        repository = getattr(self.tracker, "repository", None)
        if repository is not None and hasattr(repository, "load_developer_state"):
            return repository.load_developer_state()
        return {
            "achievement": {"unlocked_ids": [], "locked_ids": []},
            "map": {
                "unlocked_node_ids": [],
                "unlocked_count": None,
                "total_count": 4,
                "recommended_node": None,
            },
        }


    @staticmethod
    def _goal_hours(goal: Any) -> float:
        minutes = getattr(goal, "target_duration_minutes", None) or 480
        return round(minutes / 60.0, 1)


    def _estimate_streak_days(self) -> int:
        records = self.get_recent_records(9999, sleep_type=SleepType.NIGHT)
        completed_dates = {
            self.record_date(record)
            for record in records
            if self._duration_hours(record) >= 7.0
        }
        streak = 0
        cursor = date.today()
        while cursor in completed_dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak


    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        minutes = (record.ended_at - record.started_at).total_seconds() / 60
        return round(minutes / 60, 1)


    @staticmethod
    def record_date(record: SleepRecord) -> date:
        """夜间睡眠按醒来日期统计，避免跨午夜记录偏到前一天。"""
        if record.sleep_type == SleepType.NIGHT and record.ended_at:
            return record.ended_at.date()
        return record.started_at.date()


    @staticmethod
    def _safe_call(callback: object, default: Any) -> Any:
        try:
            return callback()  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            return default
