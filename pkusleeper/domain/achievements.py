from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pkusleeper.domain.sleep import SleepRecord


@dataclass(slots=True)
class SleepAchievement:
    achievement_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """判断该记录是否满足成就条件。"""
        aggregate_keys = {
            "min_records",
            "min_night_records",
            "min_nap_records",
            "min_goal_records",
            "min_streak_days",
            "min_unique_days",
            "min_average_duration_hours",
        }
        if aggregate_keys.intersection(self.demands):
            return False

        # 睡眠类型
        sleep_type_demand = self.demands.get("sleep_type")
        if sleep_type_demand and record.sleep_type != sleep_type_demand:
            return False

        # 睡眠环境
        environment_demand = self.demands.get("environment")
        if environment_demand and record.environment != environment_demand:
            return False
        
        # 最小睡眠时长
        min_hours = self.demands.get("min_duration_hours")
        if min_hours is not None:
            duration_hours = (record.ended_at - record.started_at).total_seconds() / 3600
            if duration_hours < min_hours:
                return False

        max_hours = self.demands.get("max_duration_hours")
        if max_hours is not None:
            duration_hours = (record.ended_at - record.started_at).total_seconds() / 3600
            if duration_hours > max_hours:
                return False

        max_interruptions = self.demands.get("max_interruption_count")
        if max_interruptions is not None and len(record.interruptions) > max_interruptions:
            return False
        
        # 最晚入睡时间
        max_start = self.demands.get("max_start_time")
        if max_start is not None:
            if record.started_at.time() > max_start:
                return False
        
        return True
