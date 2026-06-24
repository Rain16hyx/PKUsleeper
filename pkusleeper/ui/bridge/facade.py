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
        {
            "node_id": "red_building",
            "name": "红楼",
            "short_name": "红楼",
            "required_records": 2,
            "min_total_hours": 10,
        },
        {
            "node_id": "west",
            "name": "西校门",
            "short_name": "西校门",
            "required_records": 4,
            "night_records": 3,
            "min_total_hours": 22,
        },
        {
            "node_id": "stone_boat",
            "name": "石舫",
            "short_name": "石舫",
            "required_records": 7,
            "nap_records": 1,
            "min_total_hours": 40,
        },
        {
            "node_id": "tower",
            "name": "博雅塔",
            "short_name": "博雅塔",
            "required_records": 10,
            "long_nights": 4,
            "streak_days": 2,
        },
        {
            "node_id": "history",
            "name": "校史馆",
            "short_name": "校史馆",
            "required_records": 14,
            "dorm_nights": 5,
            "goal_days": 3,
        },
        {
            "node_id": "library",
            "name": "图书馆",
            "short_name": "图书馆",
            "required_records": 18,
            "long_nights": 8,
            "min_total_hours": 110,
        },
        {
            "node_id": "hall",
            "name": "百周年纪念讲堂",
            "short_name": "百讲",
            "required_records": 24,
            "nap_records": 3,
            "goal_days": 5,
            "streak_days": 4,
        },
        {
            "node_id": "field",
            "name": "五四操场",
            "short_name": "五四操场",
            "required_records": 30,
            "long_nights": 14,
            "min_total_hours": 190,
            "streak_days": 7,
        },
    )

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []
        self.has_planned = False
        self.current_timetable_df: pd.DataFrame | None = None
        self._last_report_summary: str | None = None
