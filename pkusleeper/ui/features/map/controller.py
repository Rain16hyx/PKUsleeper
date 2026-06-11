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


class MapController(UiController):
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
            "border: 1px solid #b8151d; background: #b8151d; color: #ffffff;"
        ),
        "unlocked": (
            NODE_BUTTON_BASE_STYLE +
            "border: 1px solid #d8bda1; background: #fffefd; color: #9a121a;"
        ),
        "locked": (
            NODE_BUTTON_BASE_STYLE +
            "border: 1px solid #e8c07f; background: #f3cf92; color: #744c12;"
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
