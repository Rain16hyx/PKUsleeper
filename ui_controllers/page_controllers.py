"""Controllers for individual stacked pages."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtWidgets import QProgressBar

from models import SleepRecord
from ui_controllers.base import UiController
from ui_controllers.service_bridge import ServiceBridge

NavigateCallback = Callable[[str], None]
RefreshCallback = Callable[[], None]


class HomeController(UiController):
    def __init__(
        self,
        page,
        bridge: ServiceBridge,
        navigate: NavigateCallback,
        refresh_all: RefreshCallback,
    ) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate
        self.refresh_all = refresh_all

    def bind_events(self) -> None:
        self.connect_button("pushButton_8", self.toggle_sleep)
        self.connect_button("pushButton_2", lambda: self.navigate("analysis"))
        self.connect_button("pushButton_3", lambda: self.navigate("planning"))
        self.connect_button("pushButton_4", lambda: self.navigate("sleepmap"))
        self.connect_button("pushButton_5", lambda: self.navigate("goal"))
        self.connect_button("pushButton_6", lambda: self.navigate("analysis"))
        self.connect_button("pushButton_7", lambda: self.navigate("achievement"))

    def refresh(self) -> None:
        data = self.bridge.get_home_snapshot()
        self.set_button_text(
            "pushButton_8",
            "结束睡眠" if data["is_sleeping"] else "开始睡眠",
        )
        self.set_label_text("label_4", f"◎  今日目标： {data['today_goal_hours']} 小时")
        self.set_label_text("label_5", f"▤  当前状态： {data['current_status']}")
        self.set_label_text("label_6", f"♨  连续达成： {data['streak_days']} 天")

    def toggle_sleep(self) -> None:
        if self.bridge.get_home_snapshot()["is_sleeping"]:
            result = self.bridge.finish_sleep()
        else:
            result = self.bridge.start_sleep()

        if not result.ok:
            self.warning("睡眠记录", result.message)
        self.refresh_all()


class RecordsController(UiController):
    def __init__(
        self,
        page,
        bridge: ServiceBridge,
        navigate: NavigateCallback,
    ) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate

    def bind_events(self) -> None:
        for name in [
            "reportButton",
            "reportButton_2",
            "reportButton_3",
            "reportButton_4",
            "reportButton_5",
        ]:
            self.connect_button(name, lambda _checked=False: self.navigate("analysis"))
        self.connect_button("rangeButton", self.refresh)
        self.connect_button("rangeButton_2", self.refresh)

    def refresh(self) -> None:
        records = self.bridge.get_recent_records(5)
        self.set_label_text("countLabel", f"共 {len(records)} 条记录")
        for index, record in enumerate(records, start=1):
            suffix = "" if index == 1 else f"_{index}"
            self._apply_record_to_row(record, suffix)

    def _apply_record_to_row(self, record: SleepRecord, suffix: str) -> None:
        self.set_label_text(f"dateText{suffix}", record.started_at.strftime("%m/%d（%a）"))
        self.set_label_text(f"durationText{suffix}", f"{self._duration_hours(record):.1f} 小时")
        self.set_label_text(
            f"timeText{suffix}",
            f"{record.started_at:%H:%M} - {record.ended_at:%H:%M}",
        )
        self.set_label_text(f"scoreBadge{suffix}", f"{self._score_for(record)} 分")

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        return round((record.ended_at - record.started_at).total_seconds() / 3600, 1)

    @classmethod
    def _score_for(cls, record: SleepRecord) -> int:
        return min(100, round(60 + cls._duration_hours(record) * 3))


class AnalysisController(UiController):
    def refresh(self) -> None:
        data = self.bridge.get_report_dashboard(7)
        self.set_label_text("statValue", f"{data['avg_sleep_hours']:.1f}")
        self.set_label_text("statValue_2", data["avg_sleep_time"])
        self.set_label_text("statValue_3", data["avg_wake_time"])
        self.set_label_text("statValue_4", str(data["goal_completion_rate"]))
        self.set_label_text("ringLabel_2", f"{data['score']}\n分")


class PlanningController(UiController):
    def bind_events(self) -> None:
        self.connect_button("pushButton", self._show_placeholder)
        self.connect_button("pushButton_2", self._show_placeholder)

    def refresh(self) -> None:
        data = self.bridge.get_planning_dashboard()
        self.set_label_text(
            "resultLine",
            f"☾  推荐夜间睡眠：\n    {data['night_sleep']}",
        )
        self.set_label_text("resultLine_2", f"☼  推荐午休：\n    {data['nap']}")
        self.set_label_text("resultLine_3", f"⌖  常用地点：\n    {data['places']}")

    def _show_placeholder(self) -> None:
        self.info("智能规划", "课表编辑和自动规划接口已预留，底层规则完成后可接入。")


class SleepMapController(UiController):
    def refresh(self) -> None:
        data = self.bridge.get_map_dashboard()
        self.set_label_text(
            "label_2",
            f"已解锁 {data['unlocked_count']} / {data['total_count']} 个地标",
        )
        self.set_label_text("recommendPlace", data["recommended_node"])


class GoalController(UiController):
    def bind_events(self) -> None:
        self.connect_button("saveButton", self._show_placeholder)
        self.connect_button("newGoalButton", self._show_placeholder)

    def refresh(self) -> None:
        data = self.bridge.get_goal_dashboard()
        self.set_label_text("goalValueLabel", f"{data['target_hours']:.1f}")
        self.set_label_text("weekTextStrong", f"{data['done_days']} / {data['total_days']} 天")
        self.set_label_text("percentLabel", f"{data['rate']}%")
        progress = self.page.findChild(QProgressBar, "progressBar")
        if progress is not None:
            progress.setValue(data["rate"])

    def _show_placeholder(self) -> None:
        self.info("睡眠目标", "目标编辑接口已预留，底层存储与规则完成后可接入。")


class AchievementController(UiController):
    def refresh(self) -> None:
        data = self.bridge.get_achievement_dashboard()
        self.set_label_text("statValue", str(data["unlocked_count"]))
        self.set_label_text("statValue_2", str(data["streak_days"]))
        self.set_label_text("statValue_3", str(data["points"]))
        self.set_label_text("nextCount", str(max(0, 5 - data["unlocked_count"])))


class StaticPageController(UiController):
    """Controller for pages that are intentionally display-only for now."""

    def refresh(self) -> None:
        now = datetime.now()
        self.set_label_text("subtitleLabel", f"当前时间：{now:%Y-%m-%d %H:%M}")
