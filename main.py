"""PySide6 界面程序入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pkusleeper.achievements.catalog import build_default_achievements
from pkusleeper.services import MainTracker
from pkusleeper.storage import SleepRecordRepository
from pkusleeper.ui import MainWindowController
from pkusleeper.reports import SleepReportBuilder


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

    tracker.achievement_manager.init_all_achievements(build_default_achievements())

    controller = MainWindowController(tracker, project_root=project_root)
    controller.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
