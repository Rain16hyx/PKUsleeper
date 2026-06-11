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


class HomeSleepBridgeMixin:
    def get_home_snapshot(self) -> dict[str, Any]:
        snapshot = self._safe_call(self.tracker.get_ui_snapshot, default={})
        is_sleeping = bool(snapshot.get("is_sleeping", False))
        goal = self._load_goal()
        goal_hours = self._goal_hours(goal)

        if is_sleeping:
            current_status = "正在睡眠中"
        elif self.has_planned:
            current_status = "方案运行中"
        else:
            current_status = "就绪"

        return {
            "is_sleeping": is_sleeping,
            "today_goal_hours": goal_hours,
            "current_status": current_status,
            "streak_days": self._estimate_streak_days(),
            "record_count": len(self.get_recent_records(9999)),
        }


    def start_sleep(
        self,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> ActionResult:
        try:
            goal = self._load_goal()
            expected_minutes = 30 if sleep_type == SleepType.NAP else int(goal.target_duration_minutes)
            state = self.tracker.start_sleeping(
                started_at=datetime.now(),
                expected_duration_minutes=expected_minutes,
                sleep_type=sleep_type,
                environment=environment,
            )
            state.session.metadata["expected_start_time"] = goal.expected_sleep_start_time
        except Exception as exc:  # noqa: BLE001
            return ActionResult(False, f"开始睡眠失败：{exc}")
        return ActionResult(True, "已开始记录本次睡眠")


    def finish_sleep(self) -> ActionResult:
        try:
            record = self.tracker.wake_up(datetime.now())
        except Exception as exc:  # noqa: BLE001
            fallback = self._finish_sleep_with_ui_fallback()
            if fallback is None:
                return ActionResult(False, f"结束睡眠失败：{exc}")
            record = fallback

        self._last_report_summary = self._build_single_record_report(record)
        return ActionResult(True, "本次睡眠已记录", record)


    def _build_single_record_report(self, record: SleepRecord) -> str:
        try:
            report = self.tracker.generate_sleep_report(record)
            return report.summary or ""
        except Exception:  # noqa: BLE001
            hours = self._duration_hours(record)
            return f"本次睡眠 {hours:.1f} 小时，记录已保存。"


    def _finish_sleep_with_ui_fallback(self) -> SleepRecord | None:
        session = getattr(self.tracker, "active_session", None)
        if session is None:
            return None

        ended_at = datetime.now()
        expected_start = session.metadata.get("expected_start_time", session.started_at)
        record = SleepRecord(
            record_id=uuid4().hex,
            user_id=session.user_id,
            started_at=session.started_at,
            ended_at=ended_at,
            expected_duration_minutes=session.expected_duration_minutes,
            expected_start_time=expected_start,
            sleep_type=session.sleep_type,
            environment=session.environment,
            interruptions=tuple(session.interruptions),
        )
        self._fallback_records.append(record)

        repository = getattr(self.tracker, "repository", None)
        if repository is not None:
            repository.save(record)

        sleep_manager = getattr(self.tracker, "sleep_manager", None)
        if sleep_manager is not None:
            sleep_manager.current_state = None
            sleep_manager.active_session = None
            sleep_manager.latest_record = record
            sleep_manager.all_records.append(record)
        return record
