"""各个堆叠页面的控制器。"""

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

from models import SleepGoal, SleepRecord, SleepType
from ui import SleepConfigDialog, TimeAxisItem
from ui_controllers.base import UiController
from ui_controllers.service_bridge import ServiceBridge
from utils.data_processing import SleepReportBuilder

NavigateCallback = Callable[[str], None]
RefreshCallback = Callable[[], None]


class ClickableRowFilter(QObject):
    """让 Designer 加载出的行控件可靠响应点击。"""

    def __init__(self, callback: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.callback = callback

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and hasattr(event, "button")
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.callback()
            return True
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


class AnalysisController(UiController):
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

    def _draw_7_days_charts(self, records: list[SleepRecord]) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        self._reset_plots()

        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d")) for i, d in enumerate(date_list)]
        record_dict = {self.bridge.record_date(r): r for r in records}

        durations: list[float] = []
        sleep_times: list[int] = []
        wake_times: list[int] = []
        x_indices: list[int] = []

        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is None:
                continue
            durations.append((record.ended_at - record.started_at).total_seconds() / 3600)
            sleep_times.append(self._minutes_for_sleep_start(record.started_at))
            wake_times.append(record.ended_at.hour * 60 + record.ended_at.minute)
            x_indices.append(idx)

        self.duration_plot.getAxis("bottom").setTicks([x_ticks])
        self.time_plot.getAxis("bottom").setTicks([x_ticks])
        self.duration_plot.setXRange(-0.5, 6.5, padding=0)
        self.time_plot.setXRange(-0.5, 6.5, padding=0)

        if not x_indices:
            self.duration_plot.setYRange(0, 10)
            self.time_plot.setYRange(18 * 60, 32 * 60)
            return

        self.duration_plot.setYRange(0, max(max(durations) + 0.8, 10))
        self.duration_plot.plot(
            x_indices,
            durations,
            pen=pg.mkPen("#c2151d", width=3),
            symbol="o",
            symbolSize=8,
            symbolBrush="#c2151d",
        )

        all_time_values = sleep_times + wake_times
        self.time_plot.setYRange(min(all_time_values) - 60, max(all_time_values) + 60)
        self.time_plot.plot(
            x_indices,
            sleep_times,
            pen=pg.mkPen("#c2151d", width=2),
            symbol="x",
            symbolSize=7,
            symbolBrush="#c2151d",
        )
        self.time_plot.plot(
            x_indices,
            wake_times,
            pen=pg.mkPen("#f0a12d", width=2),
            symbol="o",
            symbolSize=7,
            symbolBrush="#f0a12d",
        )

    def _draw_30_days_charts(self, records: list[SleepRecord]) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        self._reset_plots()

        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d") if i % 5 == 0 else "") for i, d in enumerate(date_list)]
        record_dict = {self.bridge.record_date(r): r for r in records}

        durations = [0.0] * 30
        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is not None:
                durations[idx] = (record.ended_at - record.started_at).total_seconds() / 3600

        self.duration_plot.addItem(
            pg.BarGraphItem(
                x=list(range(30)),
                height=durations,
                width=0.62,
                brush="#c2151d",
                pen=None,
            )
        )
        self.duration_plot.getAxis("bottom").setTicks([x_ticks])
        self.duration_plot.setXRange(-0.5, 29.5, padding=0)
        self.duration_plot.setYRange(0, max(max(durations) + 1, 10))

        all_ranges: list[int] = []
        for idx, day in enumerate(date_list):
            record = record_dict.get(day)
            if record is None:
                continue
            start_min = self._minutes_for_sleep_start(record.started_at)
            end_min = record.ended_at.hour * 60 + record.ended_at.minute
            if end_min < start_min:
                end_min += 1440
            duration_min = max(1, end_min - start_min)
            all_ranges.extend([start_min, end_min])
            self.time_plot.addItem(
                pg.BarGraphItem(
                    x=[idx],
                    y0=[start_min],
                    height=[duration_min],
                    width=0.72,
                    brush="#f0a12d",
                    pen=None,
                )
            )

        self.time_plot.getAxis("bottom").setTicks([x_ticks])
        self.time_plot.setXRange(-0.5, 29.5, padding=0)
        if all_ranges:
            self.time_plot.setYRange(min(all_ranges) - 60, max(all_ranges) + 60)
        else:
            self.time_plot.setYRange(18 * 60, 32 * 60)

    def _reset_plots(self) -> None:
        assert self.duration_plot is not None
        assert self.time_plot is not None
        for plot in (self.duration_plot, self.time_plot):
            plot.clear()
            item = plot.getPlotItem()
            item.clear()
            item.enableAutoRange(False)
            plot.getAxis("left").setTicks(None)
            plot.getAxis("bottom").setTicks(None)

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
            label = self.label(f"summaryText{suffix}")
            if label is not None:
                label.setWordWrap(True)

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

    @staticmethod
    def _minutes_for_sleep_start(value: datetime) -> int:
        minutes = value.hour * 60 + value.minute
        return minutes + 1440 if minutes < 12 * 60 else minutes


class PlanningController(UiController):
    def bind_events(self) -> None:
        self.connect_button("pushButton", self._on_upload_timetable)
        self.connect_button("pushButton_2", self._on_trigger_plan)
        self._style_result_labels()
        self.bridge.ensure_timetable()
        self._render_timetable_preview()

    def refresh(self) -> None:
        data = self.bridge.get_planning_dashboard()
        self.set_label_text("resultLine", f"推荐夜间睡眠\n{data.get('night_sleep', '--')}")
        self.set_label_text("resultLine_2", f"推荐午休\n{data.get('nap', '--')}")
        self.set_label_text("resultLine_3", f"常用地点\n{data.get('places', '--')}")

    def _on_upload_timetable(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.page,
            "选择选课网课表文件",
            "",
            "Excel Files (*.xlsx *.xls)",
        )

        if not file_path:
            return

        if self.bridge.upload_timetable(file_path):
            self._render_timetable_preview()
            QMessageBox.information(self.page, "通知", "课表导入成功，请点击“一键规划”生成方案。")
            self.refresh()
        else:
            QMessageBox.warning(self.page, "错误", "课表解析失败，请检查 Excel 格式。")

    def _on_trigger_plan(self) -> None:
        self.bridge.ensure_timetable()
        self.bridge.has_planned = True
        self.refresh()
        QMessageBox.information(self.page, "规划成功", "已根据课表和睡眠目标生成作息方案。")

    def _get_grid_layout(self) -> QGridLayout | None:
        return self.page.findChild(QGridLayout, "gridLayout")

    def _init_blank_timetable(self) -> None:
        grid_layout = self._get_grid_layout()
        if grid_layout is None:
            return

        while grid_layout.count():
            item = grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_timetable_preview(self) -> None:
        df = self.bridge.ensure_timetable()
        grid_layout = self._get_grid_layout()
        if df is None or grid_layout is None:
            return

        self._init_blank_timetable()
        work_days = ["周一", "周二", "周三", "周四", "周五"]

        for col_idx, day_text in enumerate(work_days, start=1):
            label = QLabel(day_text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 13px; font-weight: bold; color: #26252a; padding: 4px;")
            grid_layout.addWidget(label, 0, col_idx)

        for col_idx, day_name in enumerate(work_days, start=1):
            for row_idx in range(1, 13):
                df_row_index = row_idx - 1
                if col_idx == 1:
                    time_label = QLabel(f"第 {row_idx} 节")
                    time_label.setAlignment(Qt.AlignCenter)
                    time_label.setStyleSheet(
                        "font-size: 12px; font-weight: bold; color: #555555; padding-right: 6px;"
                    )
                    grid_layout.addWidget(time_label, row_idx, 0)

                cell_value = str(df.at[df_row_index, day_name]).strip()
                course_cell = self._create_timetable_cell(df_row_index, day_name, cell_value)
                grid_layout.addWidget(course_cell, row_idx, col_idx)

    def _create_timetable_cell(self, row_index: int, day_name: str, cell_value: str) -> QLabel:
        course_info = self.bridge._parse_cell_content(cell_value)
        if course_info:
            cell_text = f"{course_info['name']}\n@{course_info['location']}"
            style = """
                border: 1px solid #f0d9c8;
                border-radius: 6px;
                background: #fff0e7;
                color: #29282c;
                font-size: 11px;
                font-weight: 600;
                padding: 4px;
            """
        elif cell_value:
            cell_text = cell_value
            style = """
                border: 1px solid #f0d9c8;
                border-radius: 6px;
                background: #fff5ee;
                color: #29282c;
                font-size: 11px;
                font-weight: 600;
                padding: 4px;
            """
        else:
            cell_text = "点击编辑"
            style = """
                border: 1px dashed #eee2d8;
                background: #fffdfa;
                color: #b8aaa0;
                border-radius: 5px;
                font-size: 11px;
                padding: 4px;
            """

        cell = QLabel(cell_text)
        cell.setAlignment(Qt.AlignCenter)
        cell.setWordWrap(True)
        cell.setMinimumHeight(42)
        cell.setCursor(Qt.PointingHandCursor)
        cell.setStyleSheet(style)

        def open_editor(_event, row=row_index, day=day_name):
            self._edit_timetable_cell(row, day)

        cell.mousePressEvent = open_editor  # type: ignore[method-assign]
        return cell

    def _edit_timetable_cell(self, row_index: int, day_name: str) -> None:
        df = self.bridge.ensure_timetable()
        current_value = str(df.at[row_index, day_name]).strip()
        text, ok = QInputDialog.getMultiLineText(
            self.page,
            f"编辑 {day_name} 第 {row_index + 1} 节",
            "课程信息（留空表示无课；推荐格式：课程名（地点））：",
            current_value,
        )
        if not ok:
            return

        self.bridge.set_timetable_cell(row_index, day_name, text)
        self._render_timetable_preview()
        self.refresh()

    def _style_result_labels(self) -> None:
        for name in ("resultLine", "resultLine_2", "resultLine_3"):
            label = self.label(name)
            if label is None:
                continue
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setMinimumHeight(72)
            label.setStyleSheet(
                """
                color: #2e2b2d;
                font-size: 14px;
                font-weight: 600;
                line-height: 150%;
                padding: 8px 4px;
                """
            )


class SleepMapController(UiController):
    NODE_BUTTONS = {
        "west": "pushButton",
        "library": "pushButton_4",
        "tower": "pushButton_2",
        "lake": "pushButton_5",
    }

    NODE_BUTTON_BASE_STYLE = (
        "min-width: 78px; max-width: 96px; min-height: 30px; max-height: 30px; "
        "border-radius: 8px; font-size: 14px; font-weight: 800; padding: 0 10px;"
    )
    NODE_BUTTON_STYLES = {
        "recommended": (
            NODE_BUTTON_BASE_STYLE +
            "border: 1px solid #b8151d; "
            "background: #b8151d; color: #ffffff;"
        ),
        "unlocked": (
            NODE_BUTTON_BASE_STYLE +
            "border: 1px solid #d8bda1; "
            "background: #fffefd; color: #9a121a;"
        ),
        "locked": (
            NODE_BUTTON_BASE_STYLE +
            "border: 1px solid #e8c07f; "
            "background: #f3cf92; color: #744c12;"
        ),
    }
    NODE_BUTTON_TEXT = {
        "recommended": "推荐",
        "unlocked": "已解锁",
        "locked": "待解锁",
    }

    def bind_events(self) -> None:
        for node_id, button_name in self.NODE_BUTTONS.items():
            button = self.button(button_name)
            if button is None:
                continue
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, current_node=node_id: self._show_node_condition(current_node)
            )

    def refresh(self) -> None:
        data = self.bridge.get_map_dashboard()
        self.set_label_text("label_2", f"已解锁 {data['unlocked_count']} / {data['total_count']} 个地标")
        self.set_label_text("recommendPlace", data["recommended_node"])
        self.set_label_text("recommendDesc", f"下一节点条件：{data.get('recommended_condition', '--')}")
        self._node_data = {node["node_id"]: node for node in data.get("nodes", [])}

        for node in data.get("nodes", []):
            self._render_node_button(node)

    def _render_node_button(self, node: dict[str, object]) -> None:
        node_id = str(node["node_id"])
        button_name = self.NODE_BUTTONS.get(node_id)
        if button_name is None:
            return

        button = self.button(button_name)
        if button is None:
            return

        state = self._node_state(node)
        button.setText(self.NODE_BUTTON_TEXT[state])
        button.setStyleSheet(self.NODE_BUTTON_STYLES[state])

    @staticmethod
    def _node_state(node: dict[str, object]) -> str:
        if node.get("recommended"):
            return "recommended"
        if node.get("unlocked"):
            return "unlocked"
        return "locked"

    def _show_node_condition(self, node_id: str) -> None:
        node_data = getattr(self, "_node_data", None)
        if not node_data:
            data = self.bridge.get_map_dashboard()
            node_data = {node["node_id"]: node for node in data.get("nodes", [])}
            self._node_data = node_data

        node = node_data.get(node_id)
        if node is None:
            return

        status = {
            "recommended": "当前推荐",
            "unlocked": "已解锁",
            "locked": "待解锁",
        }[self._node_state(node)]

        QMessageBox.information(
            self.page,
            str(node["name"]),
            f"解锁条件：{node['condition']}\n当前状态：{status}",
        )


class GoalController(UiController):
    DOT_NAMES = ["doneDot", "doneDot_2", "doneDot_3", "doneDot_4", "doneDot_5", "emptyDot", "emptyDot_2"]

    def bind_events(self) -> None:
        self._bind_clickable_row("settingRow", self._on_change_duration)
        self._bind_clickable_row("settingRow_2", self._on_change_start_time)
        self._bind_clickable_row("settingRow_3", self._on_change_wake_time)
        self.connect_button("saveButton", self._on_save_goal)

    def refresh(self) -> None:
        goal = self.bridge._load_goal()
        hours = goal.target_duration_minutes / 60.0
        start_str = self._time_text(goal.expected_sleep_start_time)
        wake_str = self._wake_time_text(goal.expected_sleep_start_time, goal.target_duration_minutes)

        self.set_label_text("goalNameLabel", "每日睡眠目标")
        self.set_label_text("goalValueLabel", f"{hours:.1f}")
        self.set_label_text("goalUnitLabel", "小时")
        self.set_label_text("recommendLabel", f"推荐作息：{start_str} - {wake_str}")
        self.set_label_text("settingValue", f"{hours:.1f} 小时")
        self.set_label_text("settingValue_2", start_str)
        self.set_label_text("settingValue_3", wake_str)

        dashboard = self.bridge.get_goal_dashboard()
        self.set_label_text("weekTextStrong", f"{dashboard['done_days']} / {dashboard['total_days']} 天")
        self.set_label_text("percentLabel", f"{dashboard['rate']}%")

        progress_bar = self.page.findChild(QProgressBar, "progressBar")
        if progress_bar is not None:
            progress_bar.setValue(dashboard["rate"])
        self._update_week_dots(dashboard.get("weekly_completion", [False] * 7))

    def _on_change_duration(self) -> None:
        current_val = self._duration_from_label()
        value, ok = QInputDialog.getDouble(
            self.page,
            "修改睡眠目标",
            "请输入目标睡眠时长（小时）：",
            current_val,
            4.0,
            12.0,
            1,
        )
        if ok:
            self.set_label_text("settingValue", f"{value:.1f} 小时")
            self._refresh_wake_preview()
            self._sync_current_goal_preview()

    def _on_change_start_time(self) -> None:
        selected = self._pick_time("设置入睡时间", "settingValue_2", QTime(23, 30))
        if selected is None:
            return
        self.set_label_text("settingValue_2", selected)
        self._refresh_wake_preview()
        self._sync_current_goal_preview()

    def _on_change_wake_time(self) -> None:
        selected = self._pick_time("设置起床时间", "settingValue_3", QTime(7, 30))
        if selected is None:
            return
        self.set_label_text("settingValue_3", selected)
        self._refresh_duration_from_wake()
        self._sync_current_goal_preview()

    def _on_save_goal(self) -> None:
        try:
            hours = self._duration_from_label()
            parsed_time = self._start_datetime_from_label()
            new_goal = SleepGoal(
                target_value=hours,
                target_duration_minutes=int(hours * 60),
                expected_sleep_start_time=parsed_time,
                difficulty_level=1,
            )

            self.bridge.tracker.goal_manager.sleep_goal = new_goal
            repository = self.bridge.tracker.repository
            if repository is not None:
                repository.save_current_goal(new_goal)

            self.info("通知", "睡眠目标已保存。")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self.warning("错误", f"保存当前睡眠目标失败：{exc}")

    def _bind_clickable_row(self, row_name: str, callback: Callable[[], None]) -> None:
        row = self.page.findChild(QWidget, row_name)
        if row is None:
            return

        if not hasattr(self, "_row_click_filters"):
            self._row_click_filters = []
        click_filter = ClickableRowFilter(callback, row)
        widgets = [row, *row.findChildren(QWidget)]
        for widget in widgets:
            widget.setCursor(Qt.PointingHandCursor)
            widget.installEventFilter(click_filter)
        self._row_click_filters.append(click_filter)

    def _duration_from_label(self) -> float:
        label = self.label("settingValue")
        text = label.text() if label is not None else "8.0"
        match = re.search(r"\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 8.0

    def _refresh_wake_preview(self) -> None:
        start_dt = self._start_datetime_from_label()
        duration_minutes = int(self._duration_from_label() * 60)
        self.set_label_text("settingValue_3", self._wake_time_text(start_dt, duration_minutes))

    def _refresh_duration_from_wake(self) -> None:
        start_dt = self._start_datetime_from_label()
        wake_dt = self._wake_datetime_from_label(start_dt)
        minutes = int((wake_dt - start_dt).total_seconds() / 60)
        minutes = max(240, min(minutes, 12 * 60))
        self.set_label_text("settingValue", f"{minutes / 60:.1f} 小时")

    def _sync_current_goal_preview(self) -> None:
        hours = self._duration_from_label()
        start_dt = self._start_datetime_from_label()
        wake_text = self.label("settingValue_3").text() if self.label("settingValue_3") else "--:--"
        self.set_label_text("goalNameLabel", "每日睡眠目标")
        self.set_label_text("goalValueLabel", f"{hours:.1f}")
        self.set_label_text("goalUnitLabel", "小时")
        self.set_label_text("recommendLabel", f"推荐作息：{start_dt:%H:%M} - {wake_text}")

    def _pick_time(self, title: str, label_name: str, fallback: QTime) -> str | None:
        dialog = QDialog(self.page)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        time_edit = QTimeEdit(dialog)
        time_edit.setDisplayFormat("HH:mm")
        current_label = self.label(label_name)
        current_text = current_label.text() if current_label is not None else fallback.toString("HH:mm")
        current_time = QTime.fromString(current_text, "HH:mm")
        time_edit.setTime(current_time if current_time.isValid() else fallback)
        layout.addWidget(time_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            return time_edit.time().toString("HH:mm")
        return None

    def _start_datetime_from_label(self) -> datetime:
        label = self.label("settingValue_2")
        text = label.text() if label is not None else "23:30"
        return datetime.strptime(text, "%H:%M")

    def _wake_datetime_from_label(self, start_dt: datetime) -> datetime:
        label = self.label("settingValue_3")
        text = label.text() if label is not None else self._wake_time_text(start_dt, int(self._duration_from_label() * 60))
        wake_dt = datetime.strptime(text, "%H:%M")
        if wake_dt <= start_dt:
            wake_dt += timedelta(days=1)
        return wake_dt

    def _update_week_dots(self, completion: list[bool]) -> None:
        lit_style = (
            "min-width: 42px; min-height: 42px; border-radius: 21px; "
            "background: #b8151d; color: #ffffff; font-size: 24px; font-weight: 900;"
        )
        empty_style = (
            "min-width: 42px; min-height: 42px; border: 1px dashed #cdb9aa; "
            "border-radius: 21px; background: #fffefd; color: #cdb9aa;"
        )
        for idx, name in enumerate(self.DOT_NAMES):
            label = self.label(name)
            if label is None:
                continue
            done = idx < len(completion) and completion[idx]
            label.setText("✓" if done else "")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(lit_style if done else empty_style)

    @staticmethod
    def _time_text(value: datetime | None) -> str:
        return value.strftime("%H:%M") if value else "--:--"

    @staticmethod
    def _wake_time_text(start: datetime | None, duration_minutes: int) -> str:
        if start is None:
            return "--:--"
        return (start + timedelta(minutes=duration_minutes)).strftime("%H:%M")


class AchievementController(UiController):
    def refresh(self) -> None:
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
