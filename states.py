"""状态类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from models import (
    Node, 
    Roommate, 
    SleepAchievement, 
    SleepGoal, 
    SleepInterruption, 
    SleepRecord, 
    SleepReport, 
    SleepSessionDraft, 
    SleepType, 
    SleepEnvironment, 
    User, 
    SleepReport
)
from service import SleepTracker

if TYPE_CHECKING:
    from service import SleepTracker, SleepMapManager


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


class MappingState(State):
    """
    该状态表示用户正在查看睡眠地图，负责管理地图数据的加载和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)
        self.unlocked_nodes: list[Node] = []
        self.all_available_nodes: list[Node] = []

    def name(self) -> str:
        return "mapping"
    
    def load_map_nodes(self) -> dict[str, Any]:
        """加载当前睡眠地图的所有节点信息"""
        unlocked_ids = {node.node_id for node in self.unlocked_nodes}
        locked_nodes = [node for node in self.all_available_nodes if node.node_id not in unlocked_ids]

        total_count = len(self.all_available_nodes)
        unlocked_count = len(self.unlocked_nodes)
        completion_rate = (
            unlocked_count / total_count if total_count > 0 else 0.0
        )

        return {
            "total_count": total_count, 
            "unlocked_count": unlocked_count, 
            "unlocked_nodes": self.unlocked_nodes, 
            "locked_nodes": locked_nodes, 
            "completion_rate": completion_rate
        }

    def evaluate_and_update_unlocks(self, latest_record: SleepRecord | None) -> list[Node]:
        """评估用户是否达成了解锁新节点的全部要求"""
        if not latest_record: 
            return []
        
        newly_unlocked: list[Node] = []
        unlocked_ids = {node.node_id for node in self.unlocked_nodes}

        for node in self.all_available_nodes:
            if node.node_id not in unlocked_ids:
                if node.unlocked_by(latest_record):
                    newly_unlocked.append(node)
                    self.unlocked_nodes.append(node)
        
        return newly_unlocked

    def view_node_details(self, node_id: str) -> dict[str, Any]:
        """查看特定地图节点的详细介绍和解锁条件"""
        target_node = next(
            (node for node in self.all_available_nodes if node.node_id == node_id), 
            None, 
        )

        if not target_node:
            raise ValueError(f"无法找到 ID 为 {node_id} 的地图节点配置")
        
        is_unlocked = any(node.node_id == node_id for node in self.unlocked_nodes)

        return {
            "node": target_node, 
            "is_unlocked": is_unlocked, 
            "unlock_hints": target_node.demands.get(
                "hint_text", "保持健康的作息习惯即可点亮该地点"
            ), 
            "lore_descrption": (
                target_node.description if is_unlocked else "该地点仍处于迷雾中，解锁后可查看背后的故事……"
            ), 
        }
    
    def get_unlocked_nodes_list(self) -> list[Node]:
        return self.unlocked_nodes


class SleepReportState(State):
    """
    该状态表示用户正在查看睡眠报告，负责管理报告数据的加载和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)

    def name(self) -> str:
        return "report"
    
    def generate_daily_report(self, record: "SleepRecord") -> SleepReport:
        """为单次睡眠记录生成质量评分与总结报告"""
        if not record:
            raise ValueError("传入的睡眠记录 SleepRecord 不能为空")
        
        if not self.tracker.report_builder:
            raise RuntimeError("SleepTracker 中未注入合法的 SleepReportBuilder")
        
        final_report: SleepReport = self.tracker.report_builder.build(record)

        return final_report

    def export_report_for_sharing(self, report: SleepReport) -> str:
        """导出报告数据用于舍友间共享"""
        if not report or not report.record:
            raise ValueError("无法导出空睡眠报告")
        
        record = report.record
        date_str = record.started_at.strftime("%Y年%m月%d日")

        actual_min = report.actual_duration_minutes or 0
        hours = actual_min // 60
        minutes = actual_min % 60
        duration_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"

        summary_text = report.summary if report.summary else "作息打卡成功！"

        share_text = (
            f"【PKUSleeper 睡眠打卡】\n"
            f"日期：{date_str}\n"
            f"实际睡眠：{duration_str}\n"
            f"最终得分：{report.quality_score} 分\n"
            f"睡眠摘要：{summary_text}\n"
            f"-----------------------\n"
            f"和我一起用 PKUSleeper 关注作息健康吧！"
        )
        
        return share_text


class SleepGoalState(State):
    """
    该状态表示用户正在管理睡眠目标，负责管理目标的创建、编辑和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)
        self.goals_list: list[SleepGoal] = []
        self.schedule_storage: dict[str, Any] = {}  # 存储导入的原始课表或日程数据

    def name(self) -> str:
        return "goal_management"
    
    def set_manual_goal(self, goal_type: str, target_value: float, difficulty_level: int) -> SleepGoal:
        """设置目标的入睡时间、起床时间和睡眠时长"""
        pass

    def import_schedule(self, schedule_data: dict[str, Any]) -> None:
        """导入课表形式，获取软件根据课表信息安排的睡眠建议"""
        pass

    def generate_sleep_suggestions(self, roommates: list[Roommate]) -> str:
        """根据导入的课表以及舍友的作息信息，生成建议"""
        pass

    def check_reminders(self, current_time: datetime) -> list[str]:
        """
        获取睡眠提醒通知。输入当前时间或前一日的睡眠指标。
        若发现睡眠严重不足，或晚于正常作息，就在次日生成特别提醒。
        """
        pass


class AchievementState(State):
    """
    该状态表示用户正在查看成就，负责管理成就数据的加载和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)
        self.all_achievements: list[SleepAchievement] = []
        self.unlocked_achievements: list[SleepAchievement] = []

    def name(self) -> str:
        return "achievement"
    
    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        """加载用户已经获得和未获得的所有成就展示列表"""
        locked = [
            acv for acv in self.all_achievements if acv not in self.unlocked_achievements
        ]
        return {
            "unlocked": self.unlocked_achievements, 
            "locked": locked, 
        }

    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        """每次睡眠后，评估该记录是否满足新成就的解锁条件"""
        newly_unlocked: list[SleepAchievement] = []

        for acv in self.all_achievements:
            if acv not in self.unlocked_achievements:
                if acv.fulfilled_by(record):
                    newly_unlocked.append(acv)
                    self.unlocked_achievements.append(acv)

        return newly_unlocked


class UserProfileState(State):
    """
    该状态表示用户正在查看个人档案，负责管理个人信息和历史数据的加载和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)
        self.current_user = User(user_id=self.tracker.user_id, username="未登录北大同学")
        self.roommates_list: list[Roommate] = []
        self.current_level: int = 1
        self.current_experience: int = 0

    def name(self) -> str:
        return "user_profile"
    
    def load_personal_info(self) -> User:
        """加载用户名与ID"""
        return self.current_user

    def update_personal_info(self, new_username: str | None = None) -> User:
        """更新用户个人信息"""
        if new_username:
            self.current_user.username = new_username
        return self.current_user

    def add_experience(self, exp_gained: int) -> tuple[int, int]:
        """增加经验值，每 100 经验升一级，返回最新的(当前等级, 当前经验值)"""
        if exp_gained <= 0:
            return self.current_level, self.current_experience
        
        self.current_experience += exp_gained
        while self.current_experience >= 100:
            self.current_experience -= 100
            self.current_level += 1

        return self.current_level, self.current_experience
    
    def manage_roommates(self, action: str, roommate: Roommate | None = None) -> list[Roommate]:
        """
        action: "add", "remove". "list"
        """
        pass

    def load_history_summary(self, all_records: list[SleepRecord]) -> dict[str, Any]:
        """
        加载历史数据的摘要，用于在个人档案主页展示。
        """
        pass


class SleepHistoryState(State):
    """
    该状态表示用户正在查看睡眠历史与相关数据分析，负责管理历史记录的加载和展示。
    """
    def __init__(self, tracker: SleepTracker) -> None:
        super().__init__(tracker)
        self.history_records: list[SleepRecord] = []

    def name(self) -> str:
        return "sleep_history"
    
    def add_manual_record(
        self, 
        started_at: datetime, ended_at: datetime, 
        sleep_type: SleepType = SleepType.NIGHT, 
        environment: SleepEnvironment = SleepEnvironment.DORMITORY
    ) -> SleepRecord:
        """用户手动补录睡眠数据"""
        pass

    def edit_existing_record(self, record_id: str, new_started_at: datetime, new_ended_at: datetime) -> SleepRecord:
        """在软件自动判别生成的睡眠时间的基础上进行修改、校正"""
        pass

    def get_calender_view(self, year: int, month: int) -> dict[str, dict[str, Any]]:
        """
        获取睡眠日历的数据，筛选指定年月下的所有睡眠数据
        输出说明：Key为YYYY-MM-DD，Value为一个字典，字典中包含Key："record_id", "color_tag", "details"。
        """
        pass

    def calculate_statistics(self, time_span_days: int) -> dict[str, Any]:
        """
        计算数据统计，返回平均入睡时间等
        输出说明：Key为"avg_sleep_hours", "avg_bedtime", "avg_wake_time", "trend_data"
        """
        pass
