"""data classes"""


class User:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def __str__(self):
        print(f"User Information:")
        print(f"Username: {self.username}; Password: {self.password}")


class Roommate:
    def __init__(self, username: str, roommate_id: int):
        self.username = username
        self.roommate_id = roommate_id

    def __str__(self):
        print(f"Roommate Information:")
        print(f"Username: {self.username}; Roommate ID: {self.roommate_id}")


class SleepRecord:
    def __init__(
        self,
        start_time=None,
        end_time=None,
        expected_sleep_time=None,
        sleep_type=None,
        environment=None,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.expected_sleep_time = expected_sleep_time
        self.sleep_type = sleep_type
        self.environment = environment

    def __str__(self):
        print(f"Sleep Record:")
        print(
            f"Start Time: {self.start_time}; End Time: {self.end_time}; Expected Duration: {self.expected_sleep_time}; Sleep Type: {self.sleep_type}; Sleep Environment: {self.environment}"
        )


class SleepGoal:
    def __init__(self, goal_type: str, difficulty_level: int, target_sleep_time: float):
        self.goal_type = goal_type
        self.difficulty_level = difficulty_level
        self.target_sleep_time = target_sleep_time

    def __str__(self):
        print(f"Sleep Goal:")
        print(
            f"Goal Type: {self.goal_type}; Difficulty Level: {self.difficulty_level}; Target Sleep Time: {self.target_sleep_time}"
        )


class SleepAchievement:
    def __init__(self, achievement_name: str, description: str):
        self.achievement_name = achievement_name
        self.description = description
        self.unlocked = False

    def __str__(self):
        print(f"Sleep Achievement:")
        print(
            f"Achievement Name: {self.achievement_name}; Description: {self.description}"
        )

    def fulfilled(self, sleep_data: SleepRecord) -> bool:
        """check if the achievement criteria are fulfilled based on the user's sleep data"""
        pass
