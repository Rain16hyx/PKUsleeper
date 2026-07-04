from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QRectF, QTime, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from pkusleeper.domain import SleepGoal
from pkusleeper.ui.base import UiController
from pkusleeper.ui.bridge import ServiceBridge


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


class RoundedBackgroundFilter(QObject):
    """为当前目标卡片绘制圆角背景图，避免 stylesheet 拉伸变形。"""

    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pixmap = QPixmap(str(image_path))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Paint or not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)

        painter = QPainter(watched)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(watched.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 13, 13)

        painter.fillPath(path, QColor("#fffdf9"))
        if not self.pixmap.isNull():
            painter.setClipPath(path)
            painter.drawPixmap(rect, self.pixmap, self._source_rect(rect))
            painter.setClipping(False)

        painter.setPen(QPen(QColor("#e5d9cc"), 1))
        painter.drawPath(path)
        return True

    def _source_rect(self, target: QRectF) -> QRectF:
        pixmap_width = self.pixmap.width()
        pixmap_height = self.pixmap.height()
        if pixmap_width <= 0 or pixmap_height <= 0 or target.height() <= 0:
            return QRectF()

        target_ratio = target.width() / target.height()
        pixmap_ratio = pixmap_width / pixmap_height
        if pixmap_ratio > target_ratio:
            source_width = pixmap_height * target_ratio
            source_x = (pixmap_width - source_width) * 0.5
            return QRectF(source_x, 0, source_width, pixmap_height)

        source_height = pixmap_width / target_ratio
        source_y = (pixmap_height - source_height) * 0.5
        return QRectF(0, source_y, pixmap_width, source_height)



class GoalController(UiController):
    DOT_NAMES = ["doneDot", "doneDot_2", "doneDot_3", "doneDot_4", "doneDot_5", "emptyDot", "emptyDot_2"]

    def bind_events(self) -> None:
        self._apply_current_goal_background()
        self._bind_clickable_row("settingRow", self._on_change_duration)
        self._bind_clickable_row("settingRow_2", self._on_change_start_time)
        self._bind_clickable_row("settingRow_3", self._on_change_wake_time)
        self._bind_clickable_row("settingRow_4", self._on_change_nap_duration)
        self.connect_button("saveButton", self._on_save_goal)
        self._ensure_completion_frame()

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
        self.set_label_text("toggleTrack", self._nap_text(getattr(goal, "nap_target_minutes", 30)))

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

    def _on_change_nap_duration(self) -> None:
        value, ok = QInputDialog.getInt(
            self.page,
            "设置午休目标",
            "请输入午休目标时长（分钟，0 表示不设置）：",
            self._nap_minutes_from_label(),
            0,
            120,
            5,
        )
        if ok:
            self.set_label_text("toggleTrack", self._nap_text(value))

    def _on_save_goal(self) -> None:
        try:
            hours = self._duration_from_label()
            parsed_time = self._start_datetime_from_label()
            new_goal = SleepGoal(
                target_value=hours,
                target_duration_minutes=int(hours * 60),
                expected_sleep_start_time=parsed_time,
                difficulty_level=1,
                nap_target_minutes=self._nap_minutes_from_label(),
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

    def _apply_current_goal_background(self) -> None:
        frame = self.page.findChild(QFrame, "currentGoalFrame")
        if frame is None:
            return

        background_path = Path(__file__).resolve().parents[2] / "assets" / "goal_current_bg.png"
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(
            """
            #currentGoalFrame {
                border: none;
                background: transparent;
            }
            """
        )
        background_filter = RoundedBackgroundFilter(background_path, frame)
        frame.installEventFilter(background_filter)
        self._current_goal_background_filter = background_filter

        layout = self.page.findChild(QVBoxLayout, "currentGoalLayout")
        if layout is not None:
            layout.setContentsMargins(34, 40, 34, 34)
            layout.setSpacing(70)
            layout.setStretch(0, 0)
            layout.setStretch(1, 1)

        icon = self.label("targetIcon")
        if icon is not None:
            icon.hide()

        content_layout = self.page.findChild(QHBoxLayout, "currentGoalContent")
        if content_layout is not None:
            content_layout.setContentsMargins(0, 0, 150, 0)
            content_layout.setSpacing(0)

        divider = self.page.findChild(QFrame, "line")
        if divider is not None:
            divider.hide()

        styles = {
            "cardTitle": "color: #242328; font-size: 20px; font-weight: 800;",
            "goalNameLabel": "color: #242328; font-size: 18px; font-weight: 800;",
            "goalValueLabel": "color: #c70812; font-size: 60px; font-weight: 900;",
            "goalUnitLabel": "color: #242328; font-size: 19px; font-weight: 700;",
            "recommendLabel": "color: #c70812; font-size: 16px; font-weight: 800;",
        }
        for name, style in styles.items():
            label = self.label(name)
            if label is not None:
                label.setStyleSheet(style)

        separator = self.page.findChild(QFrame, "line_2")
        if separator is not None:
            separator.setFixedHeight(1)
            separator.setStyleSheet("color: #d8d1cb; background: #d8d1cb;")

        goal_text_layout = self.page.findChild(QVBoxLayout, "goalTextLayout")
        if goal_text_layout is not None:
            goal_text_layout.setSpacing(18)
            if not hasattr(self, "_goal_text_stretch_added"):
                goal_text_layout.addStretch(1)
                self._goal_text_stretch_added = True

        if content_layout is not None and goal_text_layout is not None:
            content_layout.setAlignment(
                goal_text_layout,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )

        goal_value_layout = self.page.findChild(QHBoxLayout, "goalValueLayout")
        if goal_value_layout is not None:
            goal_value_layout.setSpacing(10)
            if not hasattr(self, "_goal_value_stretch_added"):
                goal_value_layout.addStretch(1)
                self._goal_value_stretch_added = True

    def _duration_from_label(self) -> float:
        label = self.label("settingValue")
        text = label.text() if label is not None else "8.0"
        match = re.search(r"\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 8.0

    def _nap_minutes_from_label(self) -> int:
        label = self.label("toggleTrack")
        text = label.text() if label is not None else "30"
        match = re.search(r"\d+", text)
        return int(match.group(0)) if match else 0

    @staticmethod
    def _nap_text(minutes: int) -> str:
        return "不设置" if minutes <= 0 else f"{minutes} 分钟"

    def _ensure_completion_frame(self) -> None:
        if self.page.findChild(QWidget, "completionFrame") is not None:
            return

        root_layout = self.page.findChild(QVBoxLayout, "verticalLayout")
        if root_layout is None:
            return

        frame = QFrame()
        frame.setObjectName("completionFrame")
        frame.setStyleSheet(
            """
            #completionFrame {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            #completionFrame QLabel {
                color: #242328;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
            }
            """
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(18)

        title = QLabel("完成情况")
        title.setStyleSheet("font-size: 20px; font-weight: 800;")
        layout.addWidget(title)

        progress_layout = QHBoxLayout()
        bar = QProgressBar()
        bar.setObjectName("progressBar")
        bar.setTextVisible(False)
        bar.setStyleSheet(
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
        percent = QLabel("0%")
        percent.setObjectName("percentLabel")
        percent.setStyleSheet("color: #b8151d; font-size: 17px; font-weight: 900;")
        progress_layout.addWidget(bar)
        progress_layout.addWidget(percent)
        layout.addLayout(progress_layout, 1)

        days_layout = QGridLayout()
        days_layout.setHorizontalSpacing(12)
        for idx, day_text in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"]):
            day = QLabel(day_text)
            day.setAlignment(Qt.AlignCenter)
            day.setStyleSheet("font-size: 14px; font-weight: 700;")
            dot = QLabel()
            dot.setObjectName(self.DOT_NAMES[idx])
            dot.setAlignment(Qt.AlignCenter)
            days_layout.addWidget(day, 0, idx)
            days_layout.addWidget(dot, 1, idx)
        layout.addLayout(days_layout)

        week_layout = QHBoxLayout()
        week_layout.addWidget(QLabel("本周完成"))
        strong = QLabel("0 / 7 天")
        strong.setObjectName("weekTextStrong")
        strong.setStyleSheet("color: #b8151d; font-size: 18px; font-weight: 900;")
        week_layout.addWidget(strong)
        layout.addLayout(week_layout)

        root_layout.addWidget(frame)

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

    @staticmethod
    def _time_text(value: datetime | None) -> str:
        return value.strftime("%H:%M") if value else "--:--"

    @staticmethod
    def _wake_time_text(start: datetime | None, duration_minutes: int) -> str:
        if start is None:
            return "--:--"
        return (start + timedelta(minutes=duration_minutes)).strftime("%H:%M")
