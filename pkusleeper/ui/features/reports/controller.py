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
        self._render_stat_changes(dashboard.get("changes", {}))
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
        root_layout = self.page.findChild(QVBoxLayout, "verticalLayout")
        if root_layout is None:
            return

        bottom = self.page.findChild(QFrame, "bottomReportFrame")
        if bottom is None:
            bottom = QFrame()
            bottom.setObjectName("bottomReportFrame")
            bottom_layout = QHBoxLayout(bottom)
            bottom_layout.setContentsMargins(0, 0, 0, 0)
            bottom_layout.setSpacing(16)
            bottom_layout.addWidget(self._create_quality_frame(), 1)
            bottom_layout.addWidget(self._create_summary_frame(), 1)
            root_layout.addWidget(bottom, 1)

        self._configure_report_layout()


    def _configure_report_layout(self) -> None:
        root_layout = self.page.findChild(QVBoxLayout, "verticalLayout")
        if root_layout is not None:
            root_layout.setSpacing(14)
            for index, stretch in enumerate((0, 0, 0, 1, 1)):
                if index < root_layout.count():
                    root_layout.setStretch(index, stretch)

        for name in ("durationChartFrame", "timeChartFrame"):
            frame = self.page.findChild(QFrame, name)
            if frame is not None:
                frame.setMinimumHeight(176)
                frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bottom = self.page.findChild(QFrame, "bottomReportFrame")
        if bottom is not None:
            bottom.setMinimumHeight(212)
            bottom.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


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
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)

        title = QLabel("睡眠质量分析")
        title.setObjectName("chartTitle_3")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        rings = QHBoxLayout()
        rings.setSpacing(14)
        for title_text, label_name in [
            ("记录天数", "ringLabel"),
            ("平均评分", "ringLabel_2"),
            ("达标天数", "ringLabel_3"),
        ]:
            column = QVBoxLayout()
            column.setSpacing(6)
            label_title = QLabel(title_text)
            label_title.setAlignment(Qt.AlignCenter)
            label_title.setStyleSheet("font-size: 14px; font-weight: 800;")
            value = QLabel("--")
            value.setObjectName(label_name)
            value.setFixedSize(86, 86)
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet(
                """
                border-radius: 43px;
                border: 7px solid #f0a12d;
                background: #fffefd;
                color: #b8151d;
                font-size: 23px;
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
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a817a; font-size: 12px;")
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
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        title = QLabel("本期总结")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(title)

        for idx in range(1, 4):
            row = QFrame()
            row.setMinimumHeight(42)
            row.setStyleSheet("background: #fffefa; border: 1px solid #ead9c5; border-radius: 8px;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(8)
            icon = QLabel(["✓", "☾", "☀"][idx - 1])
            icon.setAlignment(Qt.AlignCenter)
            icon.setFixedSize(28, 28)
            icon.setStyleSheet(
                "border-radius: 14px; background: #fff4e2; color: #eba73b; "
                "font-size: 17px; font-weight: 900;"
            )
            title_label = QLabel()
            title_label.setObjectName("summaryTitle" if idx == 1 else f"summaryTitle_{idx}")
            title_label.setFixedWidth(92)
            title_label.setStyleSheet("font-size: 14px; font-weight: 800;")
            text_label = QLabel()
            text_label.setObjectName("summaryText" if idx == 1 else f"summaryText_{idx}")
            text_label.setWordWrap(True)
            text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            text_label.setStyleSheet("color: #7f7771; font-size: 12px;")
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


    def _render_stat_changes(self, changes: dict[str, dict[str, object]]) -> None:
        label_map = [
            ("statChange", "avg_sleep_hours"),
            ("statChange_2", "avg_sleep_time"),
            ("statChange_3", "avg_wake_time"),
            ("statChange_4", "goal_completion_rate"),
        ]
        for label_name, key in label_map:
            label = self.label(label_name)
            if label is None:
                continue

            change = changes.get(key, {"available": False})
            text, color = self._format_change(change)
            label.setText(text)
            label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700;")


    def _format_change(self, change: dict[str, object]) -> tuple[str, str]:
        if not change.get("available"):
            return "暂无上期数据", "#9c918a"

        delta = change.get("delta", 0)
        if not isinstance(delta, (int, float)) or delta == 0:
            return "较上期  持平", "#9c918a"

        direction = "↑" if delta > 0 else "↓"
        color = "#e34b17" if delta > 0 else "#459346"
        sign = "+" if delta > 0 else "-"
        abs_delta = abs(delta)
        kind = change.get("kind")

        if kind == "hours":
            return f"较上期  {sign}{abs_delta:.1f} 小时 {direction}", color
        if kind == "time":
            minutes = int(abs_delta)
            return f"较上期  {sign}{minutes // 60:02d}:{minutes % 60:02d} {direction}", color
        if kind == "percent":
            return f"较上期  {sign}{int(abs_delta)}% {direction}", color
        return "较上期  持平", "#9c918a"


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
