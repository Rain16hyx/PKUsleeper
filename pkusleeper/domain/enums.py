from __future__ import annotations

from enum import Enum


class SleepType(str, Enum):
    NIGHT = "night"
    NAP = "nap"


class SleepEnvironment(str, Enum):
    DORMITORY = "dormitory"
    HOME = "home"
    OTHER = "other"
