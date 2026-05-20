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
    expected_duration_minutes: int | None
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
    goal_id: str
    goal_type: str
    target_value: float
    difficulty_level: int


@dataclass(slots=True)
class SleepAchievement:
    achievement_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the achievement condition."""
        raise NotImplementedError


@dataclass(slots=True)
class Node:
    node_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def unlocked_by(self, record: SleepRecord) -> bool:
        """Return whether this record satisfies the node unlocking condition."""
        raise NotImplementedError
