"""各个堆叠页面的控制器。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable
import re

import pyqtgraph as pg
from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
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
        record_dict = {r.started_at.date(): r for r in records}

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
        record_dict = {r.started_at.date(): r for r in records}

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
        self._init_blank_timetable()

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
        if self.bridge.current_timetable_df is None:
            QMessageBox.warning(self.page, "提示", "请先上传课表文件。")
            return

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

        weekdays = ["周一", "周二", "周三", "周四", "周五"]
        for col_idx, day_text in enumerate(weekdays, start=1):
            label = QLabel(day_text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 13px; font-weight: bold; color: #26252a; padding: 4px;")
            grid_layout.addWidget(label, 0, col_idx)

        for row_idx in range(1, 13):
            time_label = QLabel(f"第 {row_idx} 节")
            time_label.setAlignment(Qt.AlignCenter)
            time_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #555555; padding-right: 6px;")
            grid_layout.addWidget(time_label, row_idx, 0)

            for col_idx in range(1, 6):
                empty_box = QLabel("")
                empty_box.setStyleSheet(
                    """
                    border: 1px dashed #eee2d8;
                    background: #fffdfa;
                    border-radius: 5px;
                    min-height: 42px;
                    """
                )
                grid_layout.addWidget(empty_box, row_idx, col_idx)

    def _render_timetable_preview(self) -> None:
        df = self.bridge.current_timetable_df
        grid_layout = self._get_grid_layout()
        if df is None or grid_layout is None:
            return

        self._init_blank_timetable()
        work_days = ["周一", "周二", "周三", "周四", "周五"]

        for col_idx, day_name in enumerate(work_days, start=1):
            if day_name not in df.columns:
                continue

            for row_idx in range(1, 13):
                df_row_index = row_idx - 1
                if df_row_index >= len(df):
                    break

                cell_value = df.iloc[df_row_index][day_name]
                course_info = self.bridge._parse_cell_content(cell_value)
                if course_info is None:
                    continue

                card_text = f"{course_info['name']}\n@{course_info['location']}"
                course_card = QLabel(card_text)
                course_card.setAlignment(Qt.AlignCenter)
                course_card.setWordWrap(True)
                course_card.setStyleSheet(
                    """
                    border: 1px solid #f0d9c8;
                    border-radius: 6px;
                    background: #fff0e7;
                    color: #29282c;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px;
                    """
                )
                grid_layout.addWidget(course_card, row_idx, col_idx)

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
    def refresh(self) -> None:
        data = self.bridge.get_map_dashboard()
        self.set_label_text("label_2", f"已解锁 {data['unlocked_count']} / {data['total_count']} 个地标")
        self.set_label_text("recommendPlace", data["recommended_node"])


class GoalController(UiController):
    DOT_NAMES = ["doneDot", "doneDot_2", "doneDot_3", "doneDot_4", "doneDot_5", "emptyDot", "emptyDot_2"]

    def bind_events(self) -> None:
        self._bind_clickable_row("settingRow", self._on_change_duration)
        self._bind_clickable_row("settingRow_2", self._on_change_start_time)
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

    def _on_change_start_time(self) -> None:
        dialog = QDialog(self.page)
        dialog.setWindowTitle("设置入睡时间")
        layout = QVBoxLayout(dialog)

        time_edit = QTimeEdit(dialog)
        time_edit.setDisplayFormat("HH:mm")
        current_text = self.label("settingValue_2").text() if self.label("settingValue_2") else "23:30"
        time_edit.setTime(QTime.fromString(current_text, "HH:mm") if current_text != "--:--" else QTime(23, 30))
        layout.addWidget(time_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            self.set_label_text("settingValue_2", time_edit.time().toString("HH:mm"))
            self._refresh_wake_preview()

    def _on_save_goal(self) -> None:
        try:
            hours = self._duration_from_label()
            time_label = self.label("settingValue_2")
            time_text = time_label.text() if time_label is not None else "23:30"
            parsed_time = datetime.strptime(time_text, "%H:%M")
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

        def handler(_event, fn=callback):
            fn()

        widgets = [row, *row.findChildren(QWidget)]
        for widget in widgets:
            widget.setCursor(Qt.PointingHandCursor)
            widget.mousePressEvent = handler  # type: ignore[method-assign]

    def _duration_from_label(self) -> float:
        label = self.label("settingValue")
        text = label.text() if label is not None else "8.0"
        match = re.search(r"\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 8.0

    def _refresh_wake_preview(self) -> None:
        time_label = self.label("settingValue_2")
        start_text = time_label.text() if time_label is not None else "23:30"
        start_dt = datetime.strptime(start_text, "%H:%M")
        duration_minutes = int(self._duration_from_label() * 60)
        self.set_label_text("settingValue_3", self._wake_time_text(start_dt, duration_minutes))

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
        self.set_label_text("nextCount", str(max(0, 5 - data["unlocked_count"])))

        achievement_data = self.bridge.get_achievement_lists()
        unlocked_layout = self.page.findChild(QVBoxLayout, "unlockedAchievementsLayout")
        locked_layout = self.page.findChild(QVBoxLayout, "lockedAchievementsLayout")
        if unlocked_layout is None or locked_layout is None:
            return

        self._clear_layout(unlocked_layout)
        self._clear_layout(locked_layout)

        for achievement in achievement_data["unlocked"]:
            unlocked_layout.addWidget(self._create_achievement_row(achievement, True))
        for achievement in achievement_data["locked"]:
            locked_layout.addWidget(self._create_achievement_row(achievement, False))

        unlocked_layout.addStretch()
        locked_layout.addStretch()

    def _create_achievement_row(self, achievement, unlocked: bool = True) -> QFrame:
        row = QFrame()
        row.setObjectName("achievementRow" if unlocked else "lockedRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)

        name = QLabel(achievement.name)
        desc = QLabel(achievement.description)
        status = QLabel("已解锁" if unlocked else "待解锁")
        name.setMinimumWidth(120)
        desc.setWordWrap(True)

        layout.addWidget(name)
        layout.addWidget(desc)
        layout.addStretch()
        layout.addWidget(status)
        return row

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class StaticPageController(UiController):
    """暂未实现的静态页面。"""

    def refresh(self) -> None:
        now = datetime.now()
        self.set_label_text("subtitleLabel", f"当前时间：{now:%Y-%m-%d %H:%M}")
