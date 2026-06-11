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


class ProfileController(UiController):
    """我的页面：仅提供轻量个性化设置。"""

    def bind_events(self) -> None:
        self.connect_button("editUsernameButton", self._on_edit_username)

    def refresh(self) -> None:
        user = getattr(self.bridge.tracker.user_manager, "current_user", None)
        username = getattr(user, "username", "PKU student")
        self.set_label_text("usernameValue", username)
        self.set_label_text("profileHint", "用户名仅用于本地展示，不影响打卡、报告或成就数据。")

    def _on_edit_username(self) -> None:
        current = self.label("usernameValue").text() if self.label("usernameValue") else "PKU student"
        text, ok = QInputDialog.getText(
            self.page,
            "设置用户名",
            "请输入用户名：",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not ok:
            return

        username = text.strip()
        if not username:
            self.warning("提示", "用户名不能为空。")
            return

        self.bridge.tracker.user_manager.update_personal_info(username)
        self.refresh()
