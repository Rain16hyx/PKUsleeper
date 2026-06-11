from __future__ import annotations

from typing import Any

import pandas as pd

from pkusleeper.domain import SleepRecord
from pkusleeper.services import MainTracker
from pkusleeper.ui.bridge.achievements import AchievementsBridgeMixin
from pkusleeper.ui.bridge.common import BridgeCommonMixin
from pkusleeper.ui.bridge.goals import GoalsBridgeMixin
from pkusleeper.ui.bridge.home_sleep import HomeSleepBridgeMixin
from pkusleeper.ui.bridge.map import MapBridgeMixin
from pkusleeper.ui.bridge.planning import PlanningBridgeMixin
from pkusleeper.ui.bridge.records import RecordsBridgeMixin
from pkusleeper.ui.bridge.reports import ReportsBridgeMixin


class ServiceBridge(
    HomeSleepBridgeMixin,
    RecordsBridgeMixin,
    ReportsBridgeMixin,
    GoalsBridgeMixin,
    AchievementsBridgeMixin,
    MapBridgeMixin,
    PlanningBridgeMixin,
    BridgeCommonMixin,
):
    """UI 层使用的薄门面。"""

    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]
    ALL_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    MAP_NODES: tuple[dict[str, Any], ...] = (
        {"node_id": "west", "name": "西门", "condition": "完成第 1 次睡眠打卡"},
        {"node_id": "library", "name": "图书馆", "condition": "累计完成 2 条睡眠记录"},
        {"node_id": "tower", "name": "博雅塔", "condition": "累计完成 4 条睡眠记录"},
        {"node_id": "lake", "name": "未名湖", "condition": "累计完成 6 条睡眠记录"},
    )

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []
        self.has_planned = False
        self.current_timetable_df: pd.DataFrame | None = None
        self._last_report_summary: str | None = None
