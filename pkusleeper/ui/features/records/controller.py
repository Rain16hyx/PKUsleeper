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


class RecordsController(UiController):
    def __init__(
        self,
        page: QWidget,
        bridge: ServiceBridge,
        navigate: NavigateCallback,
    ) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate
        self.current_days = 7
        self.scroll_area: QScrollArea | None = None
        self.records_container: QWidget | None = None
        self.records_layout: QVBoxLayout | None = None

    def bind_events(self) -> None:
        self.connect_button("rangeButton", lambda: self.switch_range(7))
        self.connect_button("rangeButton_2", lambda: self.switch_range(30))
        self._prepare_dynamic_list()

    def switch_range(self, days: int) -> None:
        self.current_days = days
        self._update_range_style()
        self.refresh()

    def refresh(self) -> None:
        dashboard = self.bridge.get_records_dashboard(self.current_days)
        records = dashboard["records"]
        self.set_label_text("countLabel", f"共 {dashboard['count']} 条记录（近 {self.current_days} 天）")
        self._render_records(records)

    def _prepare_dynamic_list(self) -> None:
        for name in self._static_row_names():
            row = self.page.findChild(QWidget, name)
            if row is not None:
                row.hide()

        for name in [
            "reportButton",
            "reportButton_2",
            "reportButton_3",
            "reportButton_4",
            "reportButton_5",
            "pageButton",
            "pageButton_2",
            "pageButton_3",
        ]:
            widget = self.page.findChild(QWidget, name)
            if widget is not None:
                widget.hide()

        self.set_label_text("headerLabel_6", "")
        records_frame = self.page.findChild(QFrame, "recordsFrame")
        if records_frame is None or records_frame.layout() is None:
            return

        self.scroll_area = QScrollArea(records_frame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.records_container = QWidget()
        self.records_layout = QVBoxLayout(self.records_container)
        self.records_layout.setContentsMargins(0, 0, 0, 0)
        self.records_layout.setSpacing(10)
        self.scroll_area.setWidget(self.records_container)

        layout = records_frame.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(2, self.scroll_area, stretch=1)

    def _render_records(self, records: list[SleepRecord]) -> None:
        if self.records_layout is None:
            return

        while self.records_layout.count():
            item = self.records_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not records:
            empty = QLabel(f"近 {self.current_days} 天暂无睡眠记录")
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(120)
            empty.setStyleSheet("color: #8a817a; font-size: 15px; font-weight: 700;")
            self.records_layout.addWidget(empty)
            self.records_layout.addStretch(1)
            return

        for record in records:
            self.records_layout.addWidget(self._create_record_row(record))
        self.records_layout.addStretch(1)

    def _create_record_row(self, record: SleepRecord) -> QFrame:
        row = QFrame()
        row.setObjectName("dynamicRecordRow")
        row.setStyleSheet(
            """
            #dynamicRecordRow {
                background: #fffefa;
                border: 1px solid #eaded3;
                border-radius: 9px;
            }
            QLabel {
                color: #242328;
                font-size: 15px;
                font-weight: 700;
            }
            #scoreBadgeDynamic {
                min-width: 48px;
                min-height: 48px;
                border: 2px solid #f0a12d;
                border-radius: 24px;
                background: #fffefd;
                font-size: 14px;
                font-weight: 800;
            }
            """
        )
        layout = QGridLayout(row)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setHorizontalSpacing(24)

        icon = QLabel("☾")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("color: #f0a12d; font-size: 28px;")

        score = QLabel(f"{self._score_for(record)} 分")
        score.setObjectName("scoreBadgeDynamic")
        score.setAlignment(Qt.AlignCenter)

        labels = [
            icon,
            QLabel(record.started_at.strftime("%m/%d（%a）")),
            QLabel(f"{self._duration_hours(record):.1f} 小时"),
            QLabel(f"{record.started_at:%H:%M} - {record.ended_at:%H:%M}"),
            score,
        ]

        stretches = [0, 2, 2, 3, 1]
        for col, (label, stretch) in enumerate(zip(labels, stretches, strict=True)):
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            layout.addWidget(label, 0, col)
            layout.setColumnStretch(col, stretch)
        return row

    def _update_range_style(self) -> None:
        btn7 = self.button("rangeButton")
        btn30 = self.button("rangeButton_2")
        if btn7 is None or btn30 is None:
            return
        active = "border-color: #d71920; color: #d71920;"
        idle = "border-color: #ead9c5; color: #4a4441;"
        btn7.setStyleSheet(active if self.current_days == 7 else idle)
        btn30.setStyleSheet(active if self.current_days == 30 else idle)

    @staticmethod
    def _static_row_names() -> list[str]:
        return ["recordRow", "recordRow_2", "recordRow_3", "recordRow_4", "recordRow_5"]

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        return round((record.ended_at - record.started_at).total_seconds() / 3600, 1)

    @staticmethod
    def _score_for(record: SleepRecord) -> int:
        grader = SleepReportBuilder()
        return round(grader.calculate_sleep_quality(record))
