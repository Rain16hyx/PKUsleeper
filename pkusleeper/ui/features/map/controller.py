from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pkusleeper.ui.base import UiController
from pkusleeper.ui.bridge import ServiceBridge


class MapCanvasFilter(QObject):
    def __init__(self, callback: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.callback = callback

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.callback()
        return super().eventFilter(watched, event)


class LandmarkMarker(QFrame):
    def __init__(self, node_id: str, clicked: Callable[[str], None], parent: QWidget) -> None:
        super().__init__(parent)
        self.node_id = node_id
        self.clicked = clicked
        self.setObjectName("landmarkMarker")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("landmarkName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lock_label = QLabel(self)
        self.lock_label.setObjectName("landmarkLock")
        self.lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_label.setFixedSize(26, 26)

        layout.addWidget(self.name_label)
        layout.addWidget(self.lock_label)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked(self.node_id)
        super().mousePressEvent(event)

    def update_state(self, node: dict[str, object], state: str) -> None:
        unlocked = bool(node.get("unlocked"))
        recommended = bool(node.get("recommended"))
        short_name = str(node.get("short_name") or node.get("name") or "")
        self.name_label.setText(short_name)
        self.lock_label.setText("🔓" if unlocked else "🔒")
        self.setToolTip(self._build_tooltip(node, state))

        accent_border = "border: 1px solid #b8151d;" if recommended else "border: 1px solid #d9c5a9;"
        name_background = "#fffefd" if unlocked else "#fff7e8"
        name_color = "#951017" if unlocked else "#75562d"
        lock_background = "#b8151d" if unlocked else "#e8c07f"
        lock_color = "#ffffff" if unlocked else "#6f4714"
        self.setStyleSheet(
            f"""
            QFrame#landmarkMarker {{
                background: transparent;
                border: none;
            }}
            QLabel#landmarkName {{
                min-width: 58px;
                min-height: 26px;
                padding: 0 8px;
                {accent_border}
                border-radius: 6px;
                background: {name_background};
                color: {name_color};
                font-size: 13px;
                font-weight: 800;
            }}
            QLabel#landmarkLock {{
                border: 1px solid rgba(120, 78, 30, 0.22);
                border-radius: 13px;
                background: {lock_background};
                color: {lock_color};
                font-size: 12px;
                font-weight: 900;
            }}
            """
        )
        self.adjustSize()

    @staticmethod
    def _build_tooltip(node: dict[str, object], state: str) -> str:
        return (
            f"<b>{node.get('name', '')}</b><br>"
            f"解锁要求：{node.get('condition', '--')}<br>"
            f"达成情况：{node.get('progress', '--')}<br>"
            f"当前状态：{state}<br>"
            f"地标介绍：{node.get('intro', '介绍待补充。')}"
        )


class MapController(UiController):
    MAP_IMAGE = "PKU_map.jpg"
    MAP_VERTICAL_PADDING = 34
    NODE_POSITIONS = {
        "red_building": (0.205, 0.168),
        "west": (0.074, 0.392),
        "stone_boat": (0.538, 0.397),
        "tower": (0.747, 0.440),
        "history": (0.192, 0.504),
        "library": (0.530, 0.632),
        "hall": (0.535, 0.742),
        "field": (0.792, 0.918),
    }
    STATE_TEXT = {
        "recommended": "当前推荐",
        "unlocked": "已解锁",
        "locked": "待解锁",
    }

    def __init__(self, page: QWidget, bridge: ServiceBridge) -> None:
        super().__init__(page, bridge)
        self._map_canvas: QFrame | None = None
        self._scroll_area: QScrollArea | None = None
        self._map_content: QWidget | None = None
        self._map_label: QLabel | None = None
        self._map_pixmap: QPixmap | None = None
        self._map_filter: MapCanvasFilter | None = None
        self._markers: dict[str, LandmarkMarker] = {}
        self._node_data: dict[str, dict[str, object]] = {}

    def bind_events(self) -> None:
        self._prepare_map_canvas()

    def refresh(self) -> None:
        data = self.bridge.get_map_dashboard()
        self._node_data = {str(node["node_id"]): node for node in data.get("nodes", [])}
        self._update_markers()
        self._update_map_canvas()

    def _prepare_map_canvas(self) -> None:
        if self._map_canvas is not None:
            return

        self._hide_summary()
        map_canvas = self.page.findChild(QFrame, "mapCanvas")
        if map_canvas is None:
            return

        self._map_canvas = map_canvas
        self._clear_legacy_layout(map_canvas.layout())
        map_canvas.setStyleSheet(
            """
            QFrame#mapCanvas {
                background: #fbf1df;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            """
        )

        image_path = Path(__file__).resolve().parents[2] / "assets" / self.MAP_IMAGE
        self._map_pixmap = QPixmap(str(image_path))
        if self._map_pixmap.isNull():
            self._map_pixmap = None

        self._scroll_area = QScrollArea(map_canvas)
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 10px;
                background: rgba(255, 250, 240, 0.72);
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(181, 130, 72, 0.58);
                border-radius: 5px;
                min-height: 36px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )

        self._map_content = QWidget()
        self._map_content.setObjectName("mapContent")
        self._map_content.setStyleSheet("#mapContent { background: #fbf1df; }")
        self._scroll_area.setWidget(self._map_content)

        self._map_label = QLabel(self._map_content)
        self._map_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._map_label.lower()

        for node_id in self.NODE_POSITIONS:
            marker = LandmarkMarker(node_id, self._show_node_condition, self._map_content)
            marker.hide()
            self._markers[node_id] = marker

        self._map_filter = MapCanvasFilter(self._update_map_canvas, map_canvas)
        map_canvas.installEventFilter(self._map_filter)
        self._update_map_canvas()

    def _hide_summary(self) -> None:
        for name in ("label_2", "hintLabel"):
            widget = self.label(name)
            if widget is not None:
                widget.hide()
        map_panel = self.page.findChild(QFrame, "mapPanel")
        if map_panel is not None and map_panel.layout() is not None:
            map_panel.layout().setContentsMargins(12, 12, 12, 12)
            map_panel.layout().setSpacing(0)

    def _clear_legacy_layout(self, layout) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_legacy_layout(child_layout)

    def _update_map_canvas(self) -> None:
        if (
            self._map_canvas is None
            or self._scroll_area is None
            or self._map_content is None
            or self._map_label is None
            or self._map_pixmap is None
        ):
            return

        self._scroll_area.setGeometry(0, 0, self._map_canvas.width(), self._map_canvas.height())
        viewport_width = max(1, self._scroll_area.width())
        estimated_height = int(
            viewport_width * self._map_pixmap.height() / self._map_pixmap.width()
        ) + self.MAP_VERTICAL_PADDING * 2
        if estimated_height > self._scroll_area.height():
            viewport_width = max(
                1,
                viewport_width - self._scroll_area.verticalScrollBar().sizeHint().width(),
            )
        scaled = self._map_pixmap.scaledToWidth(
            viewport_width,
            Qt.TransformationMode.SmoothTransformation,
        )
        content_height = scaled.height() + self.MAP_VERTICAL_PADDING * 2
        self._map_content.setFixedSize(viewport_width, content_height)
        self._map_label.setGeometry(0, self.MAP_VERTICAL_PADDING, viewport_width, scaled.height())
        self._map_label.setPixmap(scaled)
        self._map_label.lower()

        for node_id, marker in self._markers.items():
            position = self.NODE_POSITIONS[node_id]
            marker.adjustSize()
            x = int(position[0] * viewport_width) - marker.width() // 2
            y = self.MAP_VERTICAL_PADDING + int(position[1] * scaled.height()) - marker.height() // 2
            marker.move(
                max(4, min(x, viewport_width - marker.width() - 4)),
                max(4, min(y, content_height - marker.height() - 4)),
            )
            marker.raise_()

    def _update_markers(self) -> None:
        for node_id, marker in self._markers.items():
            node = self._node_data.get(node_id)
            if node is None:
                marker.hide()
                continue
            state = self._node_state(node)
            marker.update_state(node, self.STATE_TEXT[state])
            marker.show()

    @staticmethod
    def _node_state(node: dict[str, object]) -> str:
        if node.get("recommended") and not node.get("unlocked"):
            return "recommended"
        if node.get("unlocked"):
            return "unlocked"
        return "locked"

    def _show_node_condition(self, node_id: str) -> None:
        node = self._node_data.get(node_id)
        if node is None:
            data = self.bridge.get_map_dashboard()
            self._node_data = {str(item["node_id"]): item for item in data.get("nodes", [])}
            node = self._node_data.get(node_id)
        if node is None:
            return

        state = self.STATE_TEXT[self._node_state(node)]
        QMessageBox.information(
            self.page,
            str(node["name"]),
            (
                f"解锁要求：{node.get('condition', '--')}\n"
                f"达成情况：{node.get('progress', '--')}\n"
                f"当前状态：{state}\n"
                f"地标介绍：{node.get('intro', '介绍待补充。')}"
            ),
        )
