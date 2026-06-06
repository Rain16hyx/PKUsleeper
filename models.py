"""数据类"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SleepType(str, Enum):
    NIGHT = "night"
    NAP = "nap"


class SleepEnvironment(str, Enum):
    DORMITORY = "dormitory"
    HOME = "home"
    OTHER = "other"


@dataclass(slots=True)
class User:
    user_id: str
    username: str


@dataclass(slots=True)
class Roommate:
    roommate_id: str
    username: str


@dataclass(slots=True)
class SleepInterruption:
    started_at: datetime
    ended_at: datetime | None = None
    reason: str | None = None


@dataclass(slots=True)
class SleepSessionDraft:
    """
    Mutable object used while the user is still sleeping.
    It becomes a SleepRecord only after wake-up is confirmed.
    """

    user_id: str
    started_at: datetime
    expected_duration_minutes: int | None
    sleep_type: SleepType
    environment: SleepEnvironment
    interruptions: list[SleepInterruption] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SleepRecord:
    """
    Finalized sleep data stored after the sleeping flow ends.
    """

    record_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime
    # 记录生成时的睡眠目标快照
    expected_duration_minutes: int | None
    expected_start_time: datetime
    sleep_type: SleepType
    environment: SleepEnvironment
    interruptions: tuple[SleepInterruption, ...] = ()


@dataclass(slots=True)
class SleepReport:
    record: SleepRecord
    actual_duration_minutes: int | None = None
    interruption_count: int | None = None
    quality_score: float | None = None
    summary: str | None = None


@dataclass(slots=True)
class SleepGoal:
    target_value: float
    target_duration_minutes: int
    expected_sleep_start_time: datetime
    difficulty_level: int
    nap_target_minutes: int = 30

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the goal condition."""
        raise NotImplementedError

@dataclass(slots=True)
class SleepAchievement:
    achievement_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the achievement condition."""
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
