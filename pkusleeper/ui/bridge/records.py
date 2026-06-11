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


class RecordsBridgeMixin:
    def get_recent_records(
        self,
        days: int = 7,
        sleep_type: SleepType | None = None,
    ) -> list[SleepRecord]:
        records = self._collect_records()

        if sleep_type is not None:
            records = [r for r in records if r.sleep_type == sleep_type]

        if days < 9999:
            start_date = date.today() - timedelta(days=days - 1)
            records = [r for r in records if self.record_date(r) >= start_date]

        records.sort(key=lambda record: record.started_at, reverse=True)
        return records


    def get_records_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days)
        return {"records": records, "count": len(records), "days": days}
