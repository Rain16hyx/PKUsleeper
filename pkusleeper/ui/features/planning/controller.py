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
