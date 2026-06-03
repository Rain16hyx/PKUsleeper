"""Application entry point for the PySide6 UI."""

from __future__ import annotations

import sys
from datetime import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from models import SleepAchievement, SleepType
from service import MainTracker
from storage import SleepRecordRepository
from ui_controllers import MainWindowController
from utils.data_processing import SleepReportBuilder


def main() -> int:
    app = QApplication(sys.argv)
    project_root = Path(__file__).parent
    user_id = "default_user"
    repository = SleepRecordRepository(user_id=user_id, data_dir=project_root / "data")
    tracker = MainTracker(
        user_id=user_id,
        record_repository=repository,
        report_builder=SleepReportBuilder(),
    )

    tracker.achievement_manager.init_all_achievements(
        [
            SleepAchievement(
                achievement_id="first_sleep",
                name="初入梦乡",
                description="完成第一次睡眠记录",
                demands={},
            ),
            SleepAchievement(
                achievement_id="sleep_8h",
                name="睡眠达人",
                description="单次夜间睡眠达到 8 小时",
                demands={"min_duration_hours": 8},
            ),
            SleepAchievement(
                achievement_id="early_sleep",
                name="早睡早起",
                description="23 点前入睡且睡眠 8 小时以上",
                demands={
                    "max_start_time": time(23, 0),
                    "min_duration_hours": 8,
                },
            ),
            SleepAchievement(
                achievement_id="nap_master",
                name="午休大师",
                description="完成一次有效午睡",
                demands={
                    "sleep_type": SleepType.NAP,
                    "min_duration_hours": 0.25,
                },
            ),
        ]
    )

    controller = MainWindowController(tracker, project_root=project_root)
    controller.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
