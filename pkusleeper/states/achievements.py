from __future__ import annotations

from pkusleeper.domain import SleepAchievement, SleepRecord
from pkusleeper.states.base import State


class AchievementState(State):
    """保存成就展示和评估数据的状态容器。"""

    def __init__(self) -> None:
        self.all_achievements: list[SleepAchievement] = []
        self.unlocked_achievements: list[SleepAchievement] = []

    def name(self) -> str:
        return "achievement"

    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        locked = [
            achievement
            for achievement in self.all_achievements
            if achievement not in self.unlocked_achievements
        ]
        return {
            "unlocked": self.unlocked_achievements,
            "locked": locked,
        }

    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        newly_unlocked: list[SleepAchievement] = []

        for achievement in self.all_achievements:
            if achievement in self.unlocked_achievements:
                continue
            if achievement.fulfilled_by(record):
                newly_unlocked.append(achievement)
                self.unlocked_achievements.append(achievement)

        return newly_unlocked
