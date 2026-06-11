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


class AchievementsBridgeMixin:
    def get_achievement_dashboard(self) -> dict[str, Any]:
        achievement_lists = self.get_achievement_lists()
        unlocked_count = len(achievement_lists["unlocked"])
        total_count = unlocked_count + len(achievement_lists["locked"])
        level_index = unlocked_count // 5 + 1
        level_names = {
            1: "作息新手",
            2: "作息探索者",
            3: "稳定作息家",
            4: "梦境收藏家",
        }
        progress_current = unlocked_count % 5
        next_count = 5 - progress_current
        if total_count and unlocked_count >= total_count:
            progress_current = 5
            next_count = 0
        return {
            "unlocked_count": unlocked_count,
            "total_count": total_count,
            "streak_days": self._estimate_streak_days(),
            "points": unlocked_count * 50,
            "level": level_index,
            "level_name": level_names.get(level_index, "睡眠大师"),
            "level_progress_current": progress_current,
            "level_progress_target": 5,
            "level_progress_rate": round(progress_current / 5 * 100),
            "next_count": next_count,
        }


    def get_achievement_lists(self) -> dict[str, list[SleepAchievement]]:
        records = self.get_recent_records(9999)
        manager = getattr(self.tracker, "achievement_manager", None)
        achievements: list[SleepAchievement] = getattr(manager, "all_achievements", []) if manager else []
        dev_achievement = self._load_developer_state().get("achievement", {})

        auto_unlocked = {
            achievement.achievement_id
            for achievement in achievements
            if self._achievement_fulfilled_by_records(achievement, records)
        }
        manual_unlocked = set(dev_achievement.get("unlocked_ids", []))
        manual_locked = set(dev_achievement.get("locked_ids", []))
        unlocked_ids = (auto_unlocked | manual_unlocked) - manual_locked

        unlocked = [
            achievement
            for achievement in achievements
            if achievement.achievement_id in unlocked_ids
        ]
        locked = [
            achievement
            for achievement in achievements
            if achievement.achievement_id not in unlocked_ids
        ]
        return {"unlocked": unlocked, "locked": locked}


    def _achievement_fulfilled_by_records(
        self,
        achievement: SleepAchievement,
        records: list[SleepRecord],
    ) -> bool:
        demands = achievement.demands
        aggregate_keys = {
            "min_records",
            "min_night_records",
            "min_nap_records",
            "min_goal_records",
            "min_streak_days",
            "min_unique_days",
            "min_average_duration_hours",
        }
        if not aggregate_keys.intersection(demands):
            return any(achievement.fulfilled_by(record) for record in records)

        night_records = [r for r in records if r.sleep_type == SleepType.NIGHT]
        nap_records = [r for r in records if r.sleep_type == SleepType.NAP]

        if len(records) < demands.get("min_records", 0):
            return False
        if len(night_records) < demands.get("min_night_records", 0):
            return False
        if len(nap_records) < demands.get("min_nap_records", 0):
            return False

        min_unique_days = demands.get("min_unique_days")
        if min_unique_days is not None:
            unique_days = {self.record_date(record) for record in records}
            if len(unique_days) < min_unique_days:
                return False

        min_goal_records = demands.get("min_goal_records")
        if min_goal_records is not None:
            goal_records = [
                record
                for record in records
                if self._duration_hours(record) * 60 >= (record.expected_duration_minutes or 480)
            ]
            if len(goal_records) < min_goal_records:
                return False

        min_streak_days = demands.get("min_streak_days")
        if min_streak_days is not None and self._estimate_streak_days() < min_streak_days:
            return False

        min_average = demands.get("min_average_duration_hours")
        if min_average is not None:
            if not night_records:
                return False
            average = sum(self._duration_hours(record) for record in night_records) / len(night_records)
            if average < min_average:
                return False

        return True
