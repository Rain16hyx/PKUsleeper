"""functional classes"""

from models import User, Roommate, SleepRecord, SleepGoal, SleepAchievement


class SleepTracker:
    def __init__(self, user: User, state):
        self.current_state = state
        self.user = user
        self.sleep_recorder = SleepRecord()

    def start_sleeping(self):
        """transition to sleeping state and record sleep start time"""

    def wake_up(self):
        """transition to awake state and record sleep end time"""

    def interrupt_sleep(self):
        """handle sleep interruptions and update sleep data accordingly"""

    def generate_sleep_report(self):
        """generate a report of the user's sleep patterns and achievements"""


class AchievementManager:
    def __init__(self):
        self.all_achievements = []
        self.unlocked_achievements = []

    def unlock_achievement(self, achievement: SleepAchievement):
        """unlock a new achievement and add it to the list of achievements"""
        if achievement not in self.unlocked_achievements:
            self.unlocked_achievements.append(achievement)

    def get_achievements(self) -> list:
        """return a list of all unlocked achievements"""
        return self.unlocked_achievements

    def check_fulfillment(self, sleep_data: SleepRecord):
        """check if the user has fulfilled the criteria for any achievements based on their sleep data"""
        for achievement in self.all_achievements:
            if achievement.fulfilled(sleep_data):
                self.unlock_achievement(achievement)


class SleepGoalManager:
    def __init__(self):
        self.sleep_goals = []

    def create_sleep_goal(
        self, goal_type: str, difficulty_level: int, target_sleep_time: float
    ):
        """create a new sleep goal and add it to the list of goals"""
        new_goal = SleepGoal(goal_type, difficulty_level, target_sleep_time)
        self.sleep_goals.append(new_goal)

    def get_sleep_goals(self) -> list:
        """return a list of all sleep goals"""
        return self.sleep_goals


class StatisticsManager:
    def __init__(self):
        pass


class RoommateManager:
    def __init__(self):
        self.roommates = []

    def add_roommate(self, roommate: Roommate):
        """add a new roommate to the list of roommates"""
        self.roommates.append(roommate)

    def get_roommates(self) -> list:
        """return a list of all roommates"""
        return self.roommates


class SleepAdvisor:
    def __init__(self):
        pass


class SleepMap:
    def __init__(self):
        pass
