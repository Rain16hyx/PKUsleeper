from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
import re

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QTime, Qt
from PySide6.QtGui import QPixmap
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


class HeroBackgroundFilter(QObject):
    def __init__(self, callback: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.callback = callback

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.callback()
        return super().eventFilter(watched, event)


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
        self._hero_frame: QFrame | None = None
        self._hero_background_label: QLabel | None = None
        self._hero_background_pixmap: QPixmap | None = None
        self._hero_background_filter: HeroBackgroundFilter | None = None

    def bind_events(self) -> None:
        self._apply_hero_background()
        self._apply_status_bar_background()
        self._apply_feature_button_backgrounds()
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

    def _apply_hero_background(self) -> None:
        hero_frame = self.page.findChild(QFrame, "frame")
        if hero_frame is None:
            return

        image_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "homepage_buttonback.png"
        )
        if not image_path.exists():
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return

        hero_frame.setStyleSheet(
            """
            QFrame#frame {
                border: 1px solid #ead9c5;
                border-radius: 13px;
                background: #fffaf3;
            }
            """
        )
        self.set_label_text("moonLabel", "")

        background_label = QLabel(hero_frame)
        background_label.setObjectName("heroBackgroundLabel")
        background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        background_label.lower()

        self._hero_frame = hero_frame
        self._hero_background_label = background_label
        self._hero_background_pixmap = pixmap
        self._hero_background_filter = HeroBackgroundFilter(self._update_hero_background, hero_frame)
        hero_frame.installEventFilter(self._hero_background_filter)
        self._update_hero_background()

    def _update_hero_background(self) -> None:
        if (
            self._hero_frame is None
            or self._hero_background_label is None
            or self._hero_background_pixmap is None
        ):
            return

        width = self._hero_frame.width()
        height = self._hero_frame.height()
        if width <= 0 or height <= 0:
            return

        scaled = self._hero_background_pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)

        self._hero_background_label.setGeometry(0, 0, width, height)
        self._hero_background_label.setPixmap(cropped)
        self._hero_background_label.lower()

    def _apply_status_bar_background(self) -> None:
        status_frame = self.page.findChild(QFrame, "frame_2")
        if status_frame is None:
            return

        image_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "home_status_bar_bg.svg"
        )
        status_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        status_frame.setStyleSheet(
            f"""
            QFrame#frame_2 {{
                border: none;
                border-image: url("{image_path.as_posix()}") 0 0 0 0 stretch stretch;
                background: transparent;
            }}
            """
        )

        for name in ("line", "line_2"):
            divider = self.page.findChild(QFrame, name)
            if divider is not None:
                divider.hide()

    def _apply_feature_button_backgrounds(self) -> None:
        image_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "home_feature_card_bg.svg"
        )
        if not image_path.exists():
            return

        base_style = f"""
            QPushButton {{
                min-height: 96px;
                padding: 14px 22px 14px 28px;
                border: none;
                border-image: url("{image_path.as_posix()}") 0 0 0 0 stretch stretch;
                background: transparent;
                color: #2c292c;
                font-size: 18px;
                font-weight: 700;
                text-align: left;
            }}
            QPushButton:hover {{
                color: #b8151d;
            }}
            QPushButton:pressed {{
                color: #951017;
                padding: 15px 22px 13px 28px;
            }}
        """
        for name in (
            "pushButton_2",
            "pushButton_3",
            "pushButton_4",
            "pushButton_5",
            "pushButton_6",
            "pushButton_7",
        ):
            button = self.button(name)
            if button is not None:
                button.setStyleSheet(base_style)
