from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable
import re

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from pkusleeper.domain import SleepGoal, SleepRecord, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.ui.base import UiController
from pkusleeper.ui.bridge import ServiceBridge
from pkusleeper.ui.dialogs import SleepConfigDialog, TimeAxisItem

NavigateCallback = Callable[[str], None]
RefreshCallback = Callable[[], None]


class HomeController(UiController):
    def __init__(
        self,
        page: QWidget,
        bridge: ServiceBridge,
        navigate: NavigateCallback,
        refresh_all: RefreshCallback,
    ) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate
        self.refresh_all = refresh_all

    def bind_events(self) -> None:
        self.connect_button("pushButton_8", self.toggle_sleep)
        self.connect_button("pushButton_2", lambda: self.navigate("analysis"))
        self.connect_button("pushButton_3", lambda: self.navigate("planning"))
        self.connect_button("pushButton_4", lambda: self.navigate("sleepmap"))
        self.connect_button("pushButton_5", lambda: self.navigate("goal"))
        self.connect_button("pushButton_6", lambda: self.navigate("analysis"))
        self.connect_button("pushButton_7", lambda: self.navigate("achievement"))

    def refresh(self) -> None:
        data = self.bridge.get_home_snapshot()
        self.set_button_text(
            "pushButton_8",
            "结束睡眠" if data["is_sleeping"] else "开始睡眠",
        )
        self.set_label_text("label_4", f"今日目标：{data['today_goal_hours']} 小时")
        self.set_label_text("label_5", f"当前状态：{data['current_status']}")
        self.set_label_text("label_6", f"连续达成：{data['streak_days']} 天")

    def toggle_sleep(self) -> None:
        if self.bridge.get_home_snapshot()["is_sleeping"]:
            result = self.bridge.finish_sleep()
        else:
            dialog = SleepConfigDialog(self.page)
            if dialog.exec() != QDialog.Accepted:
                return
            chosen_type, chosen_env = dialog.get_result()
            result = self.bridge.start_sleep(
                sleep_type=chosen_type,
                environment=chosen_env,
            )

        if not result.ok:
            self.warning("睡眠记录", result.message)
        self.refresh_all()
