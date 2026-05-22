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
    Node, 
    User, Roommate
)
from states import SleepingState, State, MappingState, AchievementState
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

        self.achievement_state = AchievementState(self)
        self.achievement_manager = AchievementManager(self.achievement_state)
        self.goal_manager = SleepGoalManager()
        self.map_manager = SleepMapManager()
        self.user_manager = UserManager(user_id)

        self.all_records: list[SleepRecord] = []

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
            {}
        )
        self.current_state = SleepingState(self, self.active_session)
        return self.current_state

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        """为当前 SleepingState 记录一次中断事件"""
        if isinstance(self.current_state, SleepingState):
            self.current_state.record_interruption(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        """睡眠中断后继续睡眠"""
        if isinstance(self.current_state, SleepingState):
            interruption = self.current_state.resume_sleeping(resumed_at)
            if self.active_session:
                self.active_session.interruptions.append(interruption)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        """结束当前阶段，退出睡眠状态，将该记录归档到历史列表中"""
        if isinstance(self.current_state, SleepingState):
            record = self.current_state.finalize_sleep(ended_at)
            self.latest_record = record
            self.all_records.append(record)
            if self.record_repository:
                self.record_repository.save(record)
            return record
        raise RuntimeError("当前不在睡眠状态，无法唤醒")

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        """创建睡眠记录的分析报告"""
        if self.report_builder:
            self.latest_report = self.report_builder.build(record)
            return self.latest_report
        raise RuntimeError("当前类中没有生成报告的模型，无法生成报告")

    def is_sleeping(self) -> bool:
        """返回是否在睡眠状态"""
        return isinstance(self.current_state, SleepingState)


class AchievementManager:
    def __init__(self, state: "AchievementState") -> None:
        self._state = state

    def init_all_achievements(self, achievements: list[SleepAchievement]) -> None:
        """初始化系统中的所有成就配置"""
        self._state.all_achievements = achievements

    def init_unlocked_achievements(self, achievements: list[SleepAchievement]) -> None:
        """初始化该用户已经解锁的成就记录"""
        self._state.unlocked_achievements = achievements

    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        """加载用户已经获得和未曾获得的所有成就展示列表"""
        return self._state.load_user_achievements()
    
    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        """每次睡眠之后都去评估并且返回本次新解锁的成就"""
        return self._state.evaluate_new_achievements(record)


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
        self.all_available_nodes: list[Node] = []
        self.unlocked_nodes: list[Node] = []

    def evaluate(self):
        """评估用户是否达成了解锁一个节点的全部要求，并返回解锁的节点"""
        if isinstance(self.tracker.current_state, MappingState):
            return self.tracker.current_state.evaluate_and_update_unlocks(self.tracker.latest_record)
        return []

    def update(self, newly_unlocked: list[Node]) -> None:
        """将新解锁的节点加入用户档案"""
        self.unlocked_nodes.extend(newly_unlocked)


class UserManager:
    def __init__(self, user_id: str) -> None:
        self.current_user = User(user_id, "未登录北大同学")
        self.roommate_list: list[Roommate] = []
        self.current_level: int = 1
        self.current_experience: int = 0
        self.schedule_storage: dict[str, Any] = {}