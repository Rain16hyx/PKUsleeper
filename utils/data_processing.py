"""sleep data processing functions"""

from models import SleepRecord
from typing import Protocol
from models import SleepReport


class SleepReportBuilder(Protocol):
    def build(self, record: SleepRecord) -> SleepReport:
        """Create a report from one finalized sleep record."""
        raise NotImplementedError

    def calculate_sleep_quality(record: SleepRecord) -> float:
        """Calculate a quality score for one sleep record."""
        raise NotImplementedError

    def evaluate_environment(record: SleepRecord) -> str:
        """Evaluate the sleep environment based on one sleep record."""
        raise NotImplementedError
