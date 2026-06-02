"""Application entry point for the PySide6 UI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from service import MainTracker
from ui_controllers import MainWindowController


def main() -> int:
    app = QApplication(sys.argv)
    tracker = MainTracker(user_id="default_user")

    from datetime import time
    from models import SleepAchievement, SleepType

    tracker.achievement_manager.init_all_achievements(
        [
            SleepAchievement(
                achievement_id="first_sleep", 
                name="初入梦乡", 
                description="完成第一次睡眠记录", 
                demands={}
            ), 

            SleepAchievement(
                achievement_id="sleep_8h", 
                name="睡眠达人", 
                description="单次睡眠达到8小时", 
                demands={
                    "min_duration_hours": 8, 
                }
            ), 

            SleepAchievement(
                achievement_id="early_sleep", 
                name="早睡早起", 
                description="23点前入睡且睡眠8小时以上", 
                demands={
                    "max_start_time": time(23, 0), 
                    "min_duration_hours": 8, 
                }
            ), 

            SleepAchievement(
                achievement_id="nap_master", 
                name="午睡大师", 
                description="完成一次有效午睡", 
                demands={
                    "sleep_type": SleepType.NAP, 
                    "min_duration_hours": 0.25, 
                }
            ), 
        ]
    )

    controller = MainWindowController(tracker, project_root=Path(__file__).parent)
    controller.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
