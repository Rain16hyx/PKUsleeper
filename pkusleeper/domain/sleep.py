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
    睡眠进行中使用的可变对象。
    用户确认醒来后转换为 SleepRecord。
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
    睡眠流程结束后保存的最终记录。
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
