from __future__ import annotations

from datetime import datetime

from pkusleeper.domain import SleepEnvironment, SleepRecord, SleepReport, SleepSessionDraft, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.states import SleepingState
from pkusleeper.storage import SleepRecordRepository


class SleepManager:
    """负责睡眠记录流程的服务。"""

    def __init__(
        self,
        user_id: str,
        record_repository: SleepRecordRepository | None = None,
        report_builder: SleepReportBuilder | None = None,
    ) -> None:
        self.user_id = user_id
        self.record_repository = record_repository
        self.report_builder = report_builder
        self.current_state: SleepingState | None = None
        self.active_session: SleepSessionDraft | None = None
        self.all_records: list[SleepRecord] = []
        self.latest_record: SleepRecord | None = None
        self.latest_report: SleepReport | None = None

    def start_sleeping(
        self,
        started_at: datetime,
        expected_duration_minutes: int | None,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> SleepingState:
        if self.current_state is not None:
            raise RuntimeError("A sleep session is already active.")

        self.active_session = SleepSessionDraft(
            user_id=self.user_id,
            started_at=started_at,
            expected_duration_minutes=expected_duration_minutes,
            sleep_type=sleep_type,
            environment=environment,
        )
        self.current_state = SleepingState(self.active_session)
        return self.current_state

    def interrupt_sleep(
        self,
        interrupted_at: datetime,
        reason: str | None = None,
    ) -> None:
        self._require_sleeping_state().record_interruption(interrupted_at, reason)

    def continue_sleeping(self, resumed_at: datetime) -> None:
        self._require_sleeping_state().resume_sleeping(resumed_at)

    def wake_up(self, ended_at: datetime) -> SleepRecord:
        state = self._require_sleeping_state()
        record = state.finalize_sleep(ended_at)

        self.latest_record = record
        self.all_records.append(record)
        self.current_state = None
        self.active_session = None

        if self.record_repository is not None:
            self.record_repository.save(record)

        return record

    def generate_sleep_report(self, record: SleepRecord) -> SleepReport:
        if self.report_builder is None:
            raise RuntimeError("No report builder is configured.")
        self.latest_report = self.report_builder.build(record)
        return self.latest_report

    def is_sleeping(self) -> bool:
        return self.current_state is not None

    def _require_sleeping_state(self) -> SleepingState:
        if self.current_state is None:
            raise RuntimeError("No active sleep session.")
        return self.current_state
