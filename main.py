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
    controller = MainWindowController(tracker, project_root=Path(__file__).parent)
    controller.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
