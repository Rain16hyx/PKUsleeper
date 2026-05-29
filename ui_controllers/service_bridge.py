"""Safe adapter between UI controllers and the current service layer.

The bridge intentionally keeps UI code independent from unfinished service
details. It calls MainTracker where stable methods exist, and returns simple
fallback data where lower-level features are still being implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from models import SleepEnvironment, SleepRecord, SleepType
from service import MainTracker


@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str = ""
    payload: Any | None = None


class ServiceBridge:
    """UI-facing facade with defensive fallbacks."""

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []

    def get_home_snapshot(self) -> dict[str, Any]:
        snapshot = self._safe_call(self.tracker.get_ui_snapshot, default={})
        return {
            "is_sleeping": bool(snapshot.get("is_sleeping", False)),
            "today_goal_hours": 7.5,
            "current_status": "记录中" if snapshot.get("is_sleeping") else "待记录",
            "streak_days": self._estimate_streak_days(),
            "record_count": len(self.get_recent_records(9999)),
        }

    def start_sleep(self) -> ActionResult:
        try:
            self.tracker.start_sleeping(
                started_at=datetime.now(),
                expected_duration_minutes=450,
                sleep_type=SleepType.NIGHT,
                environment=SleepEnvironment.DORMITORY,
            )
        except Exception as exc:  # noqa: BLE001 - keeps unfinished service safe for UI.
            return ActionResult(False, f"开始睡眠失败：{exc}")
        return ActionResult(True, "已开始记录本次睡眠")

    def finish_sleep(self) -> ActionResult:
        try:
            record = self.tracker.wake_up(datetime.now())
        except Exception as exc:  # noqa: BLE001
            fallback = self._finish_sleep_with_ui_fallback()
            if fallback is None:
                return ActionResult(False, f"结束睡眠失败：{exc}")
            return ActionResult(True, "底层记录接口尚未完成，已生成一条临时 UI 记录。", fallback)
        return ActionResult(True, "本次睡眠已记录", record)

    def get_recent_records(self, days: int = 7) -> list[SleepRecord]:
        records = list(getattr(self.tracker, "all_records", []) or [])
        records.extend(self._fallback_records)
        records.sort(key=lambda record: record.started_at, reverse=True)
        return records[:days]

    def get_records_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days)
        return {
            "records": records,
            "count": len(records),
        }

    def get_report_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days)
        if not records:
            return {
                "avg_sleep_hours": 0.0,
                "avg_sleep_time": "--:--",
                "avg_wake_time": "--:--",
                "goal_completion_rate": 0,
                "score": 0,
            }

        durations = [self._duration_hours(record) for record in records]
        completed = sum(1 for value in durations if value >= 7.0)
        return {
            "avg_sleep_hours": round(sum(durations) / len(durations), 1),
            "avg_sleep_time": self._average_time_text(
                [record.started_at for record in records]
            ),
            "avg_wake_time": self._average_time_text(
                [record.ended_at for record in records]
            ),
            "goal_completion_rate": round(completed / len(records) * 100),
            "score": min(100, round(60 + sum(durations) / len(durations) * 3)),
        }

    def get_goal_dashboard(self) -> dict[str, Any]:
        records = self.get_recent_records(7)
        done = sum(1 for record in records if self._duration_hours(record) >= 7.0)
        return {
            "target_hours": 7.5,
            "done_days": done,
            "total_days": 7,
            "rate": round(done / 7 * 100),
        }

    def get_achievement_dashboard(self) -> dict[str, Any]:
        records = self.get_recent_records(9999)
        unlocked = 0
        if records:
            unlocked += 1
        if any(record.started_at.strftime("%H:%M") <= "23:30" for record in records):
            unlocked += 1
        if len(records) >= 3:
            unlocked += 1
        if sum(1 for record in records if self._duration_hours(record) >= 7.0) >= 5:
            unlocked += 1
        return {
            "unlocked_count": unlocked,
            "streak_days": self._estimate_streak_days(),
            "points": unlocked * 50,
        }

    def get_map_dashboard(self) -> dict[str, Any]:
        count = len(self.get_recent_records(9999))
        unlocked = min(4, 1 + count // 2) if count else 0
        return {
            "unlocked_count": unlocked,
            "total_count": 4,
            "recommended_node": "图书馆" if unlocked >= 2 else "西门",
        }

    def get_planning_dashboard(self) -> dict[str, Any]:
        return {
            "night_sleep": "23:30-07:00",
            "nap": "周二/周四 13:00-13:30",
            "places": "宿舍、图书馆",
        }

    def _estimate_streak_days(self) -> int:
        records = self.get_recent_records(9999)
        return min(7, sum(1 for record in records if self._duration_hours(record) >= 7.0))

    def _finish_sleep_with_ui_fallback(self) -> SleepRecord | None:
        session = getattr(self.tracker, "active_session", None)
        if session is None:
            return None

        ended_at = datetime.now()
        kwargs = {
            "record_id": uuid4().hex,
            "user_id": session.user_id,
            "started_at": session.started_at,
            "ended_at": ended_at,
            "expected_duration_minutes": session.expected_duration_minutes,
            "sleep_type": session.sleep_type,
            "environment": session.environment,
            "interruptions": tuple(session.interruptions),
        }
        try:
            record = SleepRecord(expected_start_time=session.started_at, **kwargs)
        except TypeError:
            record = SleepRecord(**kwargs)

        self._fallback_records.append(record)
        sleep_manager = getattr(self.tracker, "sleep_manager", None)
        if sleep_manager is not None:
            sleep_manager.current_state = None
            sleep_manager.active_session = None
        return record

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        minutes = (record.ended_at - record.started_at).total_seconds() / 60
        return round(minutes / 60, 1)

    @staticmethod
    def _average_time_text(values: list[datetime]) -> str:
        if not values:
            return "--:--"
        minutes = [value.hour * 60 + value.minute for value in values]
        avg = round(sum(minutes) / len(minutes))
        return f"{avg // 60 % 24:02d}:{avg % 60:02d}"

    @staticmethod
    def _safe_call(callback: object, default: Any) -> Any:
        try:
            return callback()  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            return default
