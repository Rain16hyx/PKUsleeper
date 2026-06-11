from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pkusleeper.domain.enums import SleepEnvironment, SleepType


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
