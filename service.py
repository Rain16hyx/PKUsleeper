"""functional classes"""


class SleepTracker:
    def __init__(self, user, state):
        self.current_state = state
        self.user = user

    def start_sleeping(self):
        """transition to sleeping state and record sleep start time"""

    def wake_up(self):
        """transition to awake state and record sleep end time"""

    def generate_sleep_report(self):
        """generate a report of the user's sleep patterns and achievements"""


class AchievementSystem:
    def __init__(self):
        self.achievements = []

    def unlock_achievement(self, achievement):
        """unlock a new achievement and add it to the list of achievements"""
