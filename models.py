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
    #注意这里的两个目标数据是指：这条睡眠记录产生的时候，用户当时的睡眠目标
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
    #删除了goal_id & goal_type
    target_value: float
    target_duration_minutes:int
    #注意此处添加了一个目标睡眠时长
    expected_sleep_start_time:datetime
    difficulty_level: int

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the goal condition."""
        raise NotImplementedError

#这个可能要改成自动判断某些历史性成就是否达成，每存入一次睡眠记录时都要检查
@dataclass(slots=True)
class SleepAchievement:
    achievement_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the achievement condition."""
        # 睡眠类型
        sleep_type_demand = self.demands.get("sleep_type")
        if sleep_type_demand and record.sleep_type != sleep_type_demand:
            return False
        
        # 最小入睡时长
        min_hours = self.demands.get("min_duration_hours")
        if min_hours is not None:
            duration_hours = (record.ended_at - record.started_at).total_seconds() / 3600
            if duration_hours < min_hours:
                return False
        
        # 最晚入睡时间
        max_start = self.demands.get("max_start_time")
        if max_start is not None:
            if record.started_at.time() > max_start:
                return False
        
        return True


@dataclass(slots=True)
class Node:
    node_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def unlocked_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the node unlocking condition."""
        raise NotImplementedError
