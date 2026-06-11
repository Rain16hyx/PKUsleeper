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


from pkusleeper.ui.features.reports.charts import ReportChartMixin


class ReportController(ReportChartMixin, UiController):
    def __init__(self, page: QWidget, bridge: ServiceBridge) -> None:
        super().__init__(page, bridge)
        self.current_days = 7
        self.duration_plot: pg.PlotWidget | None = None
        self.time_plot: pg.PlotWidget | None = None
        pg.setConfigOption("background", "#fffefd")
        pg.setConfigOption("foreground", "#25252a")
        pg.setConfigOption("antialias", True)


    def bind_events(self) -> None:
        self.connect_button("rangeButton", lambda: self.switch_range(7))
        self.connect_button("rangeButton_2", lambda: self.switch_range(30))
        self._inject_real_charts()
        self._ensure_report_bottom()
        self.refresh()


    def _inject_real_charts(self) -> None:
        left_frame = self.page.findChild(QWidget, "durationChartFrame")
        if left_frame and left_frame.layout() and self.duration_plot is None:
            self.duration_plot = pg.PlotWidget()
            self.duration_plot.showGrid(x=False, y=True, alpha=0.15)
            left_frame.layout().insertWidget(1, self.duration_plot, stretch=1)

        right_frame = self.page.findChild(QWidget, "timeChartFrame")
        if right_frame and right_frame.layout() and self.time_plot is None:
            time_axis = TimeAxisItem(orientation="left")
            self.time_plot = pg.PlotWidget(axisItems={"left": time_axis})
            self.time_plot.showGrid(x=False, y=True, alpha=0.15)
            right_frame.layout().addWidget(self.time_plot, stretch=1)


    def switch_range(self, days: int) -> None:
        self.current_days = days
        self._update_range_style()
        self.refresh()


    def refresh(self) -> None:
        if self.duration_plot is None or self.time_plot is None:
            return

        raw_records = self.bridge.get_recent_records(self.current_days, sleep_type=SleepType.NIGHT)
        dashboard = self.bridge.get_report_dashboard(self.current_days)

        self.set_label_text("statValue", f"{dashboard.get('avg_sleep_hours', 0.0):.1f}")
        self.set_label_text("statValue_2", dashboard.get("avg_sleep_time", "--:--"))
        self.set_label_text("statValue_3", dashboard.get("avg_wake_time", "--:--"))
        self.set_label_text("statValue_4", str(dashboard.get("goal_completion_rate", 0)))
        self.set_label_text("ringLabel", f"{dashboard.get('record_days', 0)} 天")
        self.set_label_text("ringLabel_2", f"{dashboard.get('score', 0)}\n分")
        self.set_label_text("ringLabel_3", f"{dashboard.get('completed_days', 0)}/{self.current_days}")
        self.set_label_text("qualityHint", f"达标标准：睡眠时长不少于 {self._goal_hours():.1f} 小时")
        self._render_summary(dashboard.get("summary", []))

        if self.current_days == 7:
            self._draw_7_days_charts(raw_records)
        else:
            self._draw_30_days_charts(raw_records)


    def _ensure_report_bottom(self) -> None:
        if self.page.findChild(QWidget, "qualityFrame") is not None:
            return

        root_layout = self.page.findChild(QVBoxLayout, "verticalLayout")
        if root_layout is None:
            return

        bottom = QFrame()
        bottom.setObjectName("bottomReportFrame")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(16)
        bottom_layout.addWidget(self._create_quality_frame(), 1)
        bottom_layout.addWidget(self._create_summary_frame(), 1)
        root_layout.addWidget(bottom)


    def _create_quality_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("qualityFrame")
        frame.setStyleSheet(
            """
            #qualityFrame {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            #qualityFrame QLabel {
                color: #242328;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title = QLabel("睡眠质量分析")
        title.setObjectName("chartTitle_3")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        rings = QHBoxLayout()
        rings.setSpacing(18)
        for title_text, label_name in [
            ("记录天数", "ringLabel"),
            ("平均评分", "ringLabel_2"),
            ("达标天数", "ringLabel_3"),
        ]:
            column = QVBoxLayout()
            label_title = QLabel(title_text)
            label_title.setAlignment(Qt.AlignCenter)
            label_title.setStyleSheet("font-size: 15px; font-weight: 800;")
            value = QLabel("--")
            value.setObjectName(label_name)
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet(
                """
                min-width: 82px;
                min-height: 82px;
                border-radius: 41px;
                border: 8px solid #f0a12d;
                background: #fffefd;
                color: #b8151d;
                font-size: 24px;
                font-weight: 900;
                """
            )
            if label_name == "ringLabel":
                value.setStyleSheet(value.styleSheet().replace("#f0a12d", "#c2151d"))
            elif label_name == "ringLabel_3":
                value.setStyleSheet(value.styleSheet().replace("#f0a12d", "#e8e1dc"))
            column.addWidget(label_title)
            column.addWidget(value)
            rings.addLayout(column)
        layout.addLayout(rings)

        hint = QLabel("达标标准：睡眠时长不少于 7.0 小时")
        hint.setObjectName("qualityHint")
        hint.setStyleSheet("color: #8a817a; font-size: 13px;")
        layout.addWidget(hint)
        return frame


    def _create_summary_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("summaryFrame")
        frame.setStyleSheet(
            """
            #summaryFrame {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            #summaryFrame QLabel {
                color: #242328;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title = QLabel("本期总结")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        for idx in range(1, 4):
            row = QFrame()
            row.setStyleSheet("background: #fffefa; border: 1px solid #ead9c5; border-radius: 8px;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(10)
            icon = QLabel(["✓", "☾", "☀"][idx - 1])
            icon.setAlignment(Qt.AlignCenter)
            icon.setStyleSheet(
                "min-width: 30px; min-height: 30px; border-radius: 15px; "
                "background: #fff4e2; color: #eba73b; font-size: 18px; font-weight: 900;"
            )
            title_label = QLabel()
            title_label.setObjectName("summaryTitle" if idx == 1 else f"summaryTitle_{idx}")
            title_label.setMinimumWidth(110)
            title_label.setStyleSheet("font-size: 15px; font-weight: 800;")
            text_label = QLabel()
            text_label.setObjectName("summaryText" if idx == 1 else f"summaryText_{idx}")
            text_label.setWordWrap(True)
            text_label.setStyleSheet("color: #7f7771; font-size: 13px;")
            row_layout.addWidget(icon)
            row_layout.addWidget(title_label)
            row_layout.addWidget(text_label, 1)
            layout.addWidget(row)
        return frame


    def _render_summary(self, summary: list[tuple[str, str]]) -> None:
        defaults = [
            ("记录覆盖", "暂无记录。"),
            ("时长表现", "完成打卡后生成分析。"),
            ("目标完成", "暂无达标数据。"),
        ]
        rows = summary[:3] if summary else defaults
        rows += defaults[len(rows) :]

        for idx, (title, text) in enumerate(rows[:3], start=1):
            suffix = "" if idx == 1 else f"_{idx}"
            self.set_label_text(f"summaryTitle{suffix}", title)
            self.set_label_text(f"summaryText{suffix}", text)


    def _update_range_style(self) -> None:
        btn7 = self.button("rangeButton")
        btn30 = self.button("rangeButton_2")
        if btn7 is None or btn30 is None:
            return
        active = "border-color: #d71920; color: #d71920;"
        idle = "border-color: #ead9c5; color: #4a4441;"
        btn7.setStyleSheet(active if self.current_days == 7 else idle)
        btn30.setStyleSheet(active if self.current_days == 30 else idle)


    def _goal_hours(self) -> float:
        goal = self.bridge.tracker.goal_manager.sleep_goal
        if goal is None and self.bridge.tracker.repository is not None:
            goal = self.bridge.tracker.repository.load_current_goal()
        return round((goal.target_duration_minutes if goal else 480) / 60, 1)
