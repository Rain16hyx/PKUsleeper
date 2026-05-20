"""状态类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from models import SleepInterruption, SleepRecord, SleepSessionDraft

if TYPE_CHECKING:
    from service import SleepTracker


class State(ABC):
    def __init__(self, tracker: "SleepTracker") -> None:
        self.tracker = tracker

    @abstractmethod
    def name(self) -> str:
        """返回当前状态的名称"""
        pass


class SleepingState(State):
    """
    该状态表示用户正在睡觉，负责管理睡眠过程，包括记录睡眠中断和最终生成睡眠记录。
    """

    def __init__(self, tracker: "SleepTracker", session: SleepSessionDraft) -> None:
        super().__init__(tracker)
        self.session = session
        self.active_interruption: SleepInterruption | None = None

    def name(self) -> str:
        return "sleeping"

    def record_interruption(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> SleepInterruption:
        """开始记录一次睡眠中断事件"""
        new_SleepInterruption = SleepInterruption(interrupted_at, reason=reason)
        self.active_interruption = new_SleepInterruption
        return new_SleepInterruption

    def resume_sleeping(self, resumed_at: datetime) -> SleepInterruption:
        """完成当前中断并继续睡眠"""
        if self.active_interruption:
            self.active_interruption.ended_at = resumed_at
            self.session.interruptions.append(self.active_interruption)
            self.active_interruption = None
        return self.session.interruptions[-1]

    def finalize_sleep(self, ended_at: datetime) -> SleepRecord:
        """将可变的临时睡眠记录转换为最终的 SleepRecord."""
        new_SleepRecord = SleepRecord(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.session.user_id,
            self.session.started_at,
            ended_at,
            self.session.expected_duration_minutes,
            self.session.sleep_type,
            self.session.environment,
            tuple(self.session.interruptions),
        )
        return new_SleepRecord
