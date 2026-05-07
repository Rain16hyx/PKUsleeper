"""state classes"""

from abc import ABC, abstractmethod
from service import SleepTracker, AchievementManager, SleepGoalManager


class State(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def handle(self, action: str):
        pass


class SleepState(State):
    def __init__(self):
        super().__init__()
        self.sleep_tracker = SleepTracker()
        self.achievement_manager = AchievementManager()
        self.sleep_goal_manager = SleepGoalManager()

    def handle(self, action: str):
        """process actions in sleeping state"""

        if action == "start sleeping":
            print("start sleeping")
            self.sleep_tracker.start_sleeping()

        elif action == "interrupt":
            print("sleep interrupted")
            self.sleep_tracker.interrupt_sleep()

        elif action == "wake up":
            print("wake up")
            self.sleep_tracker.wake_up()

        elif action == "generate report":
            print("generate sleep report")
            self.sleep_tracker.generate_sleep_report()

        elif action == "unlock achievement":
            print("unlock achievement")
            achieved = self.achievement_manager.check_fulfillment(
                self.sleep_tracker.sleep_recorder
            )
            for achievement in achieved:
                self.achievement_manager.unlock_achievement(achievement)


class AwakeState(State):
    def __init__(self):
        super().__init__()
        self.sleep_tracker = SleepTracker()
        self.achievement_manager = AchievementManager()
        self.sleep_goal_manager = SleepGoalManager()

    def handle(self, action: str):
        """process actions in awake state"""

        if action == "create sleep goal":
            print("create sleep goal")

        elif action == "view achievements":
            print("view achievements")
            unlocked_achievements = self.achievement_manager.get_achievements()

        elif action == "view sleep goals":
            print("view sleep goals")
            sleep_goals = self.sleep_goal_manager.get_sleep_goals()

        elif action == "view sleep statistics":
            print("view sleep statistics")
