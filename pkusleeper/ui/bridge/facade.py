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
            "intro": "始建于民国5年，原为北大学生宿舍，见证了北大的红色历史。"
        },
        {
            "node_id": "west",
            "name": "西校门",
            "short_name": "西校门",
            "required_records": 4,
            "night_records": 3,
            "min_total_hours": 22,
            "intro": "北大最具特色的校门之一，是著名的打卡点，其古建风格展现着北大的人文底蕴。"
        },
        {
            "node_id": "stone_boat",
            "name": "石舫",
            "short_name": "石舫",
            "required_records": 7,
            "nap_records": 1,
            "min_total_hours": 40,
            "intro": "位于未名湖湖心岛，是北大学子的休闲胜地，与湖光塔影相映成趣。"
        },
        {
            "node_id": "tower",
            "name": "博雅塔",
            "short_name": "博雅塔",
            "required_records": 10,
            "long_nights": 4,
            "streak_days": 2,
            "intro": "位于未名湖畔，是北大最具标志性的建筑，原为水塔。"
        },
        {
            "node_id": "history",
            "name": "校史馆",
            "short_name": "校史馆",
            "required_records": 14,
            "dorm_nights": 5,
            "goal_days": 3,
            "intro": "展示北京大学的历史沿革和重要事件，是了解北大的重要场所。"
        },
        {
            "node_id": "library",
            "name": "图书馆",
            "short_name": "图书馆",
            "required_records": 18,
            "long_nights": 8,
            "min_total_hours": 110,
            "intro": "亚洲最大的单体图书馆，馆藏丰富，且适合考试周复习。"
        },
        {
            "node_id": "hall",
            "name": "百周年纪念讲堂",
            "short_name": "百讲",
            "required_records": 24,
            "nap_records": 3,
            "goal_days": 5,
            "intro": "北京大学的重要建筑之一，常举办各类学术和文化活动。",
            "streak_days": 4,
        },
        {
            "node_id": "field",
            "name": "五四操场",
            "short_name": "五四操场",
            "required_records": 30,
            "long_nights": 14,
            "min_total_hours": 190,
            "intro": "北大唯一的大型操场，承载着北大学子的运动记忆（比如刷85km校园跑）。",
            "streak_days": 7,
        },
    )

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []
        self.has_planned = False
        self.current_timetable_df: pd.DataFrame | None = None
        self._last_report_summary: str | None = None
