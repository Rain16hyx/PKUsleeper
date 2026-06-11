from __future__ import annotations

from pkusleeper.domain import SleepAchievement, SleepRecord
from pkusleeper.states import AchievementState


class AchievementManager:
    """Service facade for achievement state."""

    def __init__(self, state: AchievementState | None = None) -> None:
        self._state = state if state is not None else AchievementState()

    @property
    def all_achievements(self) -> list[SleepAchievement]:
        return self._state.all_achievements

    @property
    def unlocked_achievements(self) -> list[SleepAchievement]:
        return self._state.unlocked_achievements

    def init_all_achievements(self, achievements: list[SleepAchievement]) -> None:
        self._state.all_achievements = achievements

    def init_unlocked_achievements(self, achievements: list[SleepAchievement]) -> None:
        self._state.unlocked_achievements = achievements

    def load_user_achievements(self) -> dict[str, list[SleepAchievement]]:
        return self._state.load_user_achievements()

    def evaluate_new_achievements(self, record: SleepRecord) -> list[SleepAchievement]:
        return self._state.evaluate_new_achievements(record)
