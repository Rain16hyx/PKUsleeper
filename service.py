"""服务类"""

from __future__ import annotations

from datetime import datetime

from models import (
    SleepAchievement,
    SleepEnvironment,
    SleepGoal,
    SleepRecord,
    SleepReport,
    SleepSessionDraft,
    SleepType,
)
from states import SleepingState, State
from utils.data_processing import SleepReportBuilder
from storage import SleepRecordRepository


class SleepTracker:
    """
    控制睡眠跟踪的核心服务，管理睡眠状态、记录、报告、成就和目标。
     1. 负责处理睡眠事件（开始、打断、继续、结束），并维护当前状态。
     2. 通过 SleepRecordRepository 持久化睡眠记录。
     3. 通过 SleepReportBuilder 生成睡眠报告。
     4. 评估和更新成就和目标管理器。
    """

    def __init__(
        self,
        user_id: str,
        record_repository: SleepRecordRepository | None = None,
        report_builder: SleepReportBuilder | None = None,
    ) -> None:
        self.user_id = user_id
        self.record_repository = record_repository
        self.report_builder = report_builder
        self.current_state: State | None = None
        self.active_session: SleepSessionDraft | None = None
        self.latest_record: SleepRecord | None = None
        self.latest_report: SleepReport | None = None

    def start_sleeping(
        self,
        started_at: datetime,
        expected_duration_minutes: int | None,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> SleepingState:
        """进入睡眠状态"""
        self.active_session = SleepSessionDraft(
            self.user_id,
            started_at,
            expected_duration_minutes,
            sleep_type,
            environment,
            [],
            {},
        )
        self.current_state = SleepingState(self, self.active_session)
        return self.current_state

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        """为当前 SleepingState 记录一次中断事件"""
        self.current_state.record_interruption(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        """睡眠中断后继续睡眠"""
        interruption = self.current_state.resume_sleeping(resumed_at)
        self.active_session.interruptions.append(interruption)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        """结束当前阶段，退出睡眠状态"""
        record = self.current_state.finalize_sleep(ended_at)
        self.latest_record = record
        return record

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        """创建睡眠记录的分析报告"""
        self.latest_report = self.report_builder.build(record)
        return self.latest_report

    def save_record(self, record: SleepRecord) -> None:
        """将睡眠记录保存到数据存储中"""
        self.record_repository.save(record)

    def is_sleeping(self) -> bool:
        """返回是否在睡眠状态"""
        return isinstance(self.current_state, SleepingState)


class AchievementManager:
    def __init__(self) -> None:
        self.all_achievements: list[SleepAchievement] = []
        self.unlocked_achievements: list[SleepAchievement] = []

    def evaluate(self, record: SleepRecord) -> list[SleepAchievement]:
        """返回某次睡眠解锁的成就列表"""
        unlocked = []
        for i in range(len(self.all_achievements)):
            acv = self.all_achievements[i]
            if acv not in self.unlocked_achievements and acv.fulfilled_by(record):
                unlocked.append(acv)
        return unlocked

    def update(self, unlocked: list[SleepAchievement]) -> None:
        """将新解锁的成就加入已解锁列表"""
        self.unlocked_achievements.extend(unlocked)


class SleepGoalManager:
    def __init__(self) -> None:
        self.sleep_goals: list[SleepGoal] = []
        self.completed_goals: list[SleepGoal] = []

    def add_goal(self, goal: SleepGoal) -> None:
        """添加新的睡眠目标到用户的目标列表"""
        self.sleep_goals.append(goal)

    def evaluate(self, record: SleepRecord) -> list[SleepGoal]:
        """返回某次睡眠完成的目标列表"""
        completed = []
        for i in range(len(self.sleep_goals)):
            goal = self.sleep_goals[i]
            if goal.fulfilled_by(record):
                completed.append(goal)
        return completed

    def update(self, completed: list[SleepGoal]) -> None:
        """将新完成的目标加入用户档案"""
        self.completed_goals.extend(completed)


class SleepMapManager:
    def __init__(self) -> None:
        self.sleep_maps: dict[str, SleepRecord] = {}

    def evaluate(self):
        """评估用户是否达成了解锁一个节点的全部要求，并返回解锁的节点"""
        pass

    def update(self):
        """将新解锁的节点加入用户档案"""
        pass

    def get_unlocked_nodes(self):
        """返回用户已解锁的节点列表"""
        pass
