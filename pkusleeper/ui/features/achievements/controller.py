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


class AchievementController(UiController):
    def bind_events(self) -> None:
        self._ensure_achievement_panels()

    def refresh(self) -> None:
        self._ensure_achievement_panels()
        data = self.bridge.get_achievement_dashboard()
        self.set_label_text("statValue", str(data["unlocked_count"]))
        self.set_label_text("statValue_2", str(data["streak_days"]))
        self.set_label_text("statValue_3", str(data["points"]))
        self.set_label_text("levelValue", f"Lv.{data['level']}")
        self.set_label_text("levelName", data["level_name"])
        self.set_label_text("nextCount", str(data["next_count"]))
        self.set_label_text("progressText", f"{data['level_progress_current']} / {data['level_progress_target']}")

        if data["next_count"] == 0:
            self.set_label_text("nextDesc", "已完成当前成就目录")
            self.set_label_text("nextDesc_2", "个成就")
        else:
            self.set_label_text("nextDesc", "距离下一等级还差")
            self.set_label_text("nextDesc_2", "个成就")

        progress_bar = self.page.findChild(QProgressBar, "levelProgress")
        if progress_bar is not None:
            progress_bar.setValue(data["level_progress_rate"])

        achievement_data = self.bridge.get_achievement_lists()
        unlocked_layout = self.page.findChild(QVBoxLayout, "unlockedAchievementsLayout")
        locked_layout = self.page.findChild(QVBoxLayout, "lockedAchievementsLayout")
        if unlocked_layout is None or locked_layout is None:
            return

        self._prepare_scroll_areas()
        self._clear_layout(unlocked_layout)
        self._clear_layout(locked_layout)

        if achievement_data["unlocked"]:
            for achievement in achievement_data["unlocked"]:
                unlocked_layout.addWidget(self._create_achievement_row(achievement, True))
        else:
            unlocked_layout.addWidget(self._create_empty_row("暂无已解锁成就"))

        if achievement_data["locked"]:
            for achievement in achievement_data["locked"]:
                locked_layout.addWidget(self._create_achievement_row(achievement, False))
        else:
            locked_layout.addWidget(self._create_empty_row("全部成就均已解锁"))

        unlocked_layout.addStretch()
        locked_layout.addStretch()

    def _ensure_achievement_panels(self) -> None:
        if self.page.findChild(QWidget, "statFrame_3") is None:
            stats_layout = self.page.findChild(QHBoxLayout, "statsLayout")
            if stats_layout is not None:
                stats_layout.addWidget(self._create_points_frame(), 1)

        if self.page.findChild(QWidget, "levelFrame") is None:
            root_layout = self.page.findChild(QVBoxLayout, "verticalLayout")
            if root_layout is not None:
                root_layout.insertWidget(2, self._create_level_frame())

        self._normalize_stat_cards()

    def _normalize_stat_cards(self) -> None:
        stats_layout = self.page.findChild(QHBoxLayout, "statsLayout")
        if stats_layout is None:
            return

        for index, name in enumerate(("statFrame", "statFrame_2", "statFrame_3")):
            frame = self.page.findChild(QFrame, name)
            if frame is None:
                continue
            frame.setMinimumWidth(0)
            frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            stats_layout.setStretch(index, 1)

    def _create_points_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statFrame_3")
        frame.setStyleSheet(
            """
            #statFrame_3 {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            """
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(16)
        icon = QLabel("★")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            "min-width: 72px; min-height: 72px; border-radius: 36px; "
            "background: #fff4e2; color: #eba73b; font-size: 42px; font-weight: 900;"
        )
        text_layout = QVBoxLayout()
        title = QLabel("成就积分")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        row = QHBoxLayout()
        value = QLabel("0")
        value.setObjectName("statValue_3")
        value.setStyleSheet("color: #b8151d; font-size: 34px; font-weight: 900;")
        unit = QLabel("分")
        unit.setStyleSheet("font-size: 16px;")
        row.addWidget(value)
        row.addWidget(unit)
        text_layout.addWidget(title)
        text_layout.addLayout(row)
        layout.addWidget(icon)
        layout.addLayout(text_layout, 1)
        return frame

    def _create_level_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("levelFrame")
        frame.setStyleSheet(
            """
            #levelFrame {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            """
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(26)

        icon = QLabel("★")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            "min-width: 72px; min-height: 72px; border-radius: 36px; "
            "background: #fff4e2; color: #eba73b; font-size: 42px; font-weight: 900;"
        )
        layout.addWidget(icon)

        info_layout = QVBoxLayout()
        title = QLabel("当前等级")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        name_layout = QHBoxLayout()
        level_value = QLabel("Lv.1")
        level_value.setObjectName("levelValue")
        level_value.setStyleSheet("color: #b8151d; font-size: 34px; font-weight: 900;")
        level_name = QLabel("作息新手")
        level_name.setObjectName("levelName")
        level_name.setStyleSheet("font-size: 24px; font-weight: 900;")
        name_layout.addWidget(level_value)
        name_layout.addWidget(level_name)
        desc = QLabel("保持稳定作息，逐步解锁更多成就")
        desc.setStyleSheet("color: #7f7771; font-size: 14px;")
        info_layout.addWidget(title)
        info_layout.addLayout(name_layout)
        info_layout.addWidget(desc)
        layout.addLayout(info_layout, 1)

        next_layout = QVBoxLayout()
        next_title = QLabel("下一目标")
        next_title.setStyleSheet("font-size: 18px; font-weight: 800;")
        desc_layout = QHBoxLayout()
        next_desc = QLabel("距离下一等级还差")
        next_desc.setObjectName("nextDesc")
        next_count = QLabel("5")
        next_count.setObjectName("nextCount")
        next_count.setStyleSheet("color: #b8151d; font-size: 16px; font-weight: 900;")
        next_desc_2 = QLabel("个成就")
        next_desc_2.setObjectName("nextDesc_2")
        desc_layout.addWidget(next_desc)
        desc_layout.addWidget(next_count)
        desc_layout.addWidget(next_desc_2)
        desc_layout.addStretch()
        progress_layout = QHBoxLayout()
        progress = QProgressBar()
        progress.setObjectName("levelProgress")
        progress.setTextVisible(False)
        progress.setStyleSheet(
            """
            QProgressBar {
                min-height: 12px;
                border: none;
                border-radius: 6px;
                background: #e8e1dc;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: #eda235;
            }
            """
        )
        progress_text = QLabel("0 / 5")
        progress_text.setObjectName("progressText")
        progress_text.setStyleSheet("font-size: 16px; font-weight: 700;")
        progress_layout.addWidget(progress, 1)
        progress_layout.addWidget(progress_text)
        next_layout.addWidget(next_title)
        next_layout.addLayout(desc_layout)
        next_layout.addLayout(progress_layout)
        layout.addLayout(next_layout, 1)
        return frame

    def _create_achievement_row(self, achievement, unlocked: bool = True) -> QFrame:
        row = QFrame()
        row.setObjectName("achievementRow" if unlocked else "lockedRow")
        row.setStyleSheet(
            """
            QFrame {
                background: #fffefa;
                border: 1px solid #f0dfca;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            """
            if unlocked
            else """
            QFrame {
                background: #fffefd;
                border: 1px solid #eadfd3;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            """
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        name = QLabel(achievement.name)
        desc = QLabel(achievement.description)
        status = QLabel("已解锁" if unlocked else "待解锁")
        name.setMinimumWidth(126)
        name.setStyleSheet(
            "color: #242328; font-size: 15px; font-weight: 800;"
            if unlocked
            else "color: #4c4744; font-size: 15px; font-weight: 800;"
        )
        desc.setStyleSheet("color: #6f6761; font-size: 13px;")
        desc.setWordWrap(True)
        status.setAlignment(Qt.AlignCenter)
        status.setMinimumWidth(70)
        status.setStyleSheet(
            "color: #c91d25; font-size: 13px; font-weight: 800;"
            if unlocked
            else "color: #6f6761; font-size: 13px; font-weight: 700;"
        )

        layout.addWidget(name)
        layout.addWidget(desc, 1)
        layout.addStretch()
        layout.addWidget(status)
        return row

    def _create_empty_row(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(96)
        label.setStyleSheet(
            """
            color: #9c918a;
            background: #fffefa;
            border: 1px dashed #ead9c5;
            border-radius: 8px;
            font-size: 14px;
            """
        )
        return label

    def _prepare_scroll_areas(self) -> None:
        for name in ("unlockedScrollArea", "lockedScrollArea"):
            scroll = self.page.findChild(QScrollArea, name)
            if scroll is None:
                continue
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { background: #fffefd; border: none; }")
            scroll.viewport().setStyleSheet("background: #fffefd;")

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
