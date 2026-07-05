from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pkusleeper.domain import SleepInterruption, SleepRecord, SleepSessionDraft
from pkusleeper.states.base import State


class SleepingState(State):
    """
    一次进行中睡眠会话的状态对象。

    只保存会话级数据，不直接调用服务、仓库或管理器。
    """

    def __init__(self, session: SleepSessionDraft) -> None:
        self.session = session
        self.active_interruption: SleepInterruption | None = None

    def name(self) -> str:
        return "sleeping"

    def record_interruption(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> SleepInterruption:
        """记录当前睡眠会话中的一次中断开始。"""
        if self.active_interruption is not None:
            raise RuntimeError("There is already an active interruption.")

        interruption = SleepInterruption(started_at=interrupted_at, reason=reason)
        self.active_interruption = interruption
        return interruption

    def resume_sleeping(self, resumed_at: datetime) -> SleepInterruption:
        """结束当前中断并继续睡眠。"""
        if self.active_interruption is None:
            raise RuntimeError("There is no active interruption to finish.")

        interruption = self.active_interruption
        interruption.ended_at = resumed_at
        self.session.interruptions.append(interruption)
        self.active_interruption = None
        return interruption

    def finalize_sleep(self, ended_at: datetime) -> SleepRecord:
        """将当前睡眠草稿转换为最终睡眠记录。"""
        if self.active_interruption is not None:
            self.active_interruption.ended_at = ended_at
            self.session.interruptions.append(self.active_interruption)
            self.active_interruption = None

        return SleepRecord(
            record_id=uuid4().hex,
            user_id=self.session.user_id,
            started_at=self.session.started_at,
            ended_at=ended_at,
            expected_duration_minutes=self.session.expected_duration_minutes,
            expected_start_time=self.session.metadata.get(
                "expected_start_time",
                self.session.started_at,
            ),
            sleep_type=self.session.sleep_type,
            environment=self.session.environment,
            interruptions=tuple(self.session.interruptions),
        )
