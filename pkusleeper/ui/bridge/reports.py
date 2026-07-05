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


class ReportsBridgeMixin:
    def get_report_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days, sleep_type=SleepType.NIGHT)
        previous_records = self._get_previous_period_records(days)
        goal = self._load_goal()
        threshold_hours = self._goal_hours(goal)

        if not records:
            return {
                "avg_sleep_hours": 0.0,
                "avg_sleep_time": "--:--",
                "avg_wake_time": "--:--",
                "goal_completion_rate": 0,
                "score": 0,
                "record_days": 0,
                "completed_days": 0,
                "summary": self._empty_summary(days),
                "changes": self._empty_changes(),
            }

        durations = [self._duration_hours(record) for record in records]
        completed_days = sum(1 for value in durations if value >= threshold_hours)
        grader = SleepReportBuilder()
        scores = [grader.calculate_sleep_quality(r) for r in records]
        avg_score = round(sum(scores) / len(scores))
        current_metrics = self._period_metrics(records, threshold_hours)
        previous_metrics = self._period_metrics(previous_records, threshold_hours)

        return {
            "avg_sleep_hours": round(sum(durations) / len(durations), 1),
            "avg_sleep_time": self._average_time_text([r.started_at for r in records], night_start=True),
            "avg_wake_time": self._average_time_text([r.ended_at for r in records]),
            "goal_completion_rate": round(completed_days / len(records) * 100),
            "score": min(100, avg_score),
            "record_days": len(records),
            "completed_days": completed_days,
            "summary": self._build_period_summary(records, durations, completed_days, days),
            "changes": self._build_period_changes(current_metrics, previous_metrics),
        }


    def _build_period_summary(
        self,
        records: list[SleepRecord],
        durations: list[float],
        completed_days: int,
        days: int,
    ) -> list[tuple[str, str]]:
        avg_duration = round(sum(durations) / len(durations), 1)
        rate = round(completed_days / len(records) * 100)

        if avg_duration >= 8:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，睡眠时长比较充足。"
        elif avg_duration >= 7:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，整体接近目标。"
        else:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，建议优先补足夜间睡眠。"

        if rate >= 80:
            goal_text = f"本期达标率 {rate}%，目标完成情况很好。"
        elif rate >= 50:
            goal_text = f"本期达标率 {rate}%，仍有提升空间。"
        else:
            goal_text = f"本期达标率 {rate}%，可以先从固定入睡时间开始。"

        record_text = f"最近 {days} 天内有 {len(records)} 条夜间睡眠记录。"
        return [("记录覆盖", record_text), ("时长表现", duration_text), ("目标完成", goal_text)]


    @staticmethod
    def _empty_summary(days: int) -> list[tuple[str, str]]:
        return [
            ("记录覆盖", f"最近 {days} 天暂无夜间睡眠记录。"),
            ("时长表现", "完成一次睡眠打卡后即可生成趋势分析。"),
            ("目标完成", "暂无数据时，本周完成圆点保持未点亮。"),
        ]


    def _get_previous_period_records(self, days: int) -> list[SleepRecord]:
        current_start = date.today() - timedelta(days=days - 1)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start - timedelta(days=1)

        records = [
            record
            for record in self._collect_records()
            if record.sleep_type == SleepType.NIGHT
            and previous_start <= self.record_date(record) <= previous_end
        ]
        records.sort(key=lambda record: record.started_at, reverse=True)
        return records


    def _period_metrics(self, records: list[SleepRecord], threshold_hours: float) -> dict[str, Any] | None:
        if not records:
            return None

        durations = [self._duration_hours(record) for record in records]
        completed_days = sum(1 for value in durations if value >= threshold_hours)
        return {
            "avg_sleep_hours": round(sum(durations) / len(durations), 1),
            "avg_sleep_minutes": self._average_time_minutes([r.started_at for r in records], night_start=True),
            "avg_wake_minutes": self._average_time_minutes([r.ended_at for r in records]),
            "goal_completion_rate": round(completed_days / len(records) * 100),
        }


    @staticmethod
    def _empty_changes() -> dict[str, dict[str, Any]]:
        return {
            "avg_sleep_hours": {"available": False},
            "avg_sleep_time": {"available": False},
            "avg_wake_time": {"available": False},
            "goal_completion_rate": {"available": False},
        }


    def _build_period_changes(
        self,
        current: dict[str, Any] | None,
        previous: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        if current is None or previous is None:
            return self._empty_changes()

        return {
            "avg_sleep_hours": {
                "available": True,
                "kind": "hours",
                "delta": round(current["avg_sleep_hours"] - previous["avg_sleep_hours"], 1),
            },
            "avg_sleep_time": {
                "available": True,
                "kind": "time",
                "delta": self._time_delta_minutes(
                    current["avg_sleep_minutes"],
                    previous["avg_sleep_minutes"],
                ),
            },
            "avg_wake_time": {
                "available": True,
                "kind": "time",
                "delta": self._time_delta_minutes(
                    current["avg_wake_minutes"],
                    previous["avg_wake_minutes"],
                ),
            },
            "goal_completion_rate": {
                "available": True,
                "kind": "percent",
                "delta": current["goal_completion_rate"] - previous["goal_completion_rate"],
            },
        }


    @staticmethod
    def _average_time_text(values: list[datetime], night_start: bool = False) -> str:
        avg = ReportsBridgeMixin._average_time_minutes(values, night_start)
        if avg is None:
            return "--:--"
        return f"{avg // 60:02d}:{avg % 60:02d}"


    @staticmethod
    def _average_time_minutes(values: list[datetime], night_start: bool = False) -> int | None:
        if not values:
            return None
        minutes = []
        for value in values:
            total = value.hour * 60 + value.minute
            if night_start and total < 12 * 60:
                total += 24 * 60
            minutes.append(total)
        avg = round(sum(minutes) / len(minutes)) % (24 * 60)
        return avg


    @staticmethod
    def _time_delta_minutes(current: int | None, previous: int | None) -> int:
        if current is None or previous is None:
            return 0
        delta = current - previous
        if delta > 12 * 60:
            delta -= 24 * 60
        elif delta < -12 * 60:
            delta += 24 * 60
        return delta
