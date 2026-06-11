"""默认睡眠成就目录。"""

from __future__ import annotations

from datetime import time

from pkusleeper.domain import SleepAchievement, SleepEnvironment, SleepType


DEFAULT_ACHIEVEMENT_SPECS = [
    {
        "achievement_id": "first_sleep",
        "name": "初入梦乡",
        "description": "完成第一次睡眠记录",
        "demands": {},
    },
    {
        "achievement_id": "sleep_8h",
        "name": "睡眠达人",
        "description": "单次夜间睡眠达到 8 小时",
        "demands": {"sleep_type": SleepType.NIGHT, "min_duration_hours": 8},
    },
    {
        "achievement_id": "early_sleep",
        "name": "早睡早起",
        "description": "23 点前入睡且夜间睡眠达到 8 小时",
        "demands": {
            "sleep_type": SleepType.NIGHT,
            "max_start_time": time(23, 0),
            "min_duration_hours": 8,
        },
    },
    {
        "achievement_id": "nap_master",
        "name": "午休大师",
        "description": "完成一次不少于 15 分钟的有效午睡",
        "demands": {
            "sleep_type": SleepType.NAP,
            "min_duration_hours": 0.25,
        },
    },
    {
        "achievement_id": "deep_recovery",
        "name": "深度回血",
        "description": "单次夜间睡眠达到 9 小时",
        "demands": {
            "sleep_type": SleepType.NIGHT,
            "min_duration_hours": 9,
        },
    },
    {
        "achievement_id": "power_nap",
        "name": "高效小憩",
        "description": "完成一次 15 到 45 分钟的午睡",
        "demands": {
            "sleep_type": SleepType.NAP,
            "min_duration_hours": 0.25,
            "max_duration_hours": 0.75,
        },
    },
    {
        "achievement_id": "quiet_night",
        "name": "一夜安稳",
        "description": "完成一次无中断且不少于 7 小时的夜间睡眠",
        "demands": {
            "sleep_type": SleepType.NIGHT,
            "min_duration_hours": 7,
            "max_interruption_count": 0,
        },
    },
    {
        "achievement_id": "dorm_regular",
        "name": "宿舍作息家",
        "description": "在宿舍完成一次不少于 7 小时的夜间睡眠",
        "demands": {
            "sleep_type": SleepType.NIGHT,
            "environment": SleepEnvironment.DORMITORY,
            "min_duration_hours": 7,
        },
    },
    {
        "achievement_id": "home_recharge",
        "name": "回家充电",
        "description": "在家中完成一次不少于 7 小时的夜间睡眠",
        "demands": {
            "sleep_type": SleepType.NIGHT,
            "environment": SleepEnvironment.HOME,
            "min_duration_hours": 7,
        },
    },
    {
        "achievement_id": "three_checkins",
        "name": "小有坚持",
        "description": "累计完成 3 条睡眠记录",
        "demands": {"min_records": 3},
    },
    {
        "achievement_id": "nap_habit",
        "name": "午休养成",
        "description": "累计完成 3 次午睡记录",
        "demands": {"min_nap_records": 3},
    },
    {
        "achievement_id": "goal_five",
        "name": "目标收割机",
        "description": "累计 5 次睡眠达到当次目标时长",
        "demands": {"min_goal_records": 5},
    },
    {
        "achievement_id": "streak_three",
        "name": "三日连胜",
        "description": "连续 3 天夜间睡眠不少于 7 小时",
        "demands": {"min_streak_days": 3},
    },
    {
        "achievement_id": "week_logger",
        "name": "一周有迹",
        "description": "累计 7 个不同日期留下睡眠记录",
        "demands": {"min_unique_days": 7},
    },
    {
        "achievement_id": "steady_week",
        "name": "稳定作息周",
        "description": "至少 7 次夜间记录，平均睡眠达到 7.5 小时",
        "demands": {
            "min_night_records": 7,
            "min_average_duration_hours": 7.5,
        },
    },
]

DEFAULT_ACHIEVEMENT_NAMES = {
    item["achievement_id"]: item["name"]
    for item in DEFAULT_ACHIEVEMENT_SPECS
}


def build_default_achievements() -> list[SleepAchievement]:
    return [SleepAchievement(**item) for item in DEFAULT_ACHIEVEMENT_SPECS]
