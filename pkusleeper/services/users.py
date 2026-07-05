from __future__ import annotations

from typing import Any

from pkusleeper.domain import Roommate, User


class UserManager:
    """管理用户资料、室友和课表数据的服务。"""

    def __init__(self, user_id: str) -> None:
        self.current_user = User(user_id=user_id, username="PKU student")
        self.roommate_list: list[Roommate] = []
        self.current_level: int = 1
        self.current_experience: int = 0
        self.schedule_storage: dict[str, Any] = {}

    def update_personal_info(self, new_username: str | None = None) -> User:
        if new_username:
            self.current_user.username = new_username
        return self.current_user

    def add_roommate(self, roommate: Roommate) -> None:
        if roommate not in self.roommate_list:
            self.roommate_list.append(roommate)

    def remove_roommate(self, roommate_id: str) -> None:
        self.roommate_list = [
            roommate
            for roommate in self.roommate_list
            if roommate.roommate_id != roommate_id
        ]

    def import_schedule(self, schedule_data: dict[str, Any]) -> None:
        self.schedule_storage = schedule_data

    def add_experience(self, exp_gained: int) -> tuple[int, int]:
        if exp_gained > 0:
            self.current_experience += exp_gained
            while self.current_experience >= 100:
                self.current_experience -= 100
                self.current_level += 1
        return self.current_level, self.current_experience
