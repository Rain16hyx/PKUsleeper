from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

import pandas as pd

from pkusleeper.domain import SleepAchievement, SleepEnvironment, SleepRecord, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.ui.bridge.result import ActionResult


class GoalsBridgeMixin:
    def get_goal_dashboard(self) -> dict[str, Any]:
        goal = self._load_goal()
        target_hours = self._goal_hours(goal)
        week_start = date.today() - timedelta(days=date.today().weekday())
        weekly_completion = [False] * 7

        for record in self.get_recent_records(14, sleep_type=SleepType.NIGHT):
            record_date = self.record_date(record)
            if week_start <= record_date <= week_start + timedelta(days=6):
                expected = (record.expected_duration_minutes or goal.target_duration_minutes) / 60
                weekly_completion[record_date.weekday()] = self._duration_hours(record) >= expected

        done = sum(weekly_completion)
        return {
            "target_hours": target_hours,
            "done_days": done,
            "total_days": 7,
            "rate": round(done / 7 * 100),
            "weekly_completion": weekly_completion,
        }
