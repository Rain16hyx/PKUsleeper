from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pkusleeper.domain.sleep import SleepRecord


@dataclass(slots=True)
class SleepGoal:
    target_value: float
    target_duration_minutes: int
    expected_sleep_start_time: datetime
    difficulty_level: int
    nap_target_minutes: int = 30

    def fulfilled_by(self, record: SleepRecord) -> bool:
        """判断该记录是否满足目标条件。"""
        raise NotImplementedError
