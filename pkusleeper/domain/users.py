from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class User:
    user_id: str
    username: str



@dataclass(slots=True)
class Roommate:
    roommate_id: str
    username: str
