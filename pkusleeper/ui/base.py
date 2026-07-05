"""PySide6 页面控制器的共享辅助工具。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from collections.abc import Callable
from typing import TypeVar

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QWidget

T = TypeVar("T", bound=QWidget)


def load_ui(path: Path) -> QWidget:
    """加载 Qt Designer 的 .ui 文件并返回根控件。"""
    file = QFile(str(path))
    if not file.open(QFile.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Cannot open UI file: {path}")

    loader = QUiLoader()
    widget = loader.load(file)
    file.close()

    if widget is None:
        raise RuntimeError(f"Failed to load UI file {path}: {loader.errorString()}")
    return widget


class UiController:
    """页面控制器基类。"""

    def __init__(self, page: QWidget, bridge: object) -> None:
        self.page = page
        self.bridge = bridge

    def bind_events(self) -> None:
        """绑定页面级信号，子类可按需重写。"""

    def refresh(self) -> None:
        """刷新展示数据，子类可按需重写。"""

    def refresh_common_header(self) -> None:
        """刷新所有页面共用的顶部日期栏。"""
        today = date.today()
        self.set_button_text("dateButton", f"▣  {today.year}年{today.month}月{today.day}日")

    def child(self, widget_type: type[T], name: str) -> T | None:
        return self.page.findChild(widget_type, name)

    def label(self, name: str) -> QLabel | None:
        return self.child(QLabel, name)

    def button(self, name: str) -> QPushButton | None:
        return self.child(QPushButton, name)

    def set_label_text(self, name: str, text: str) -> None:
        label = self.label(name)
        if label is not None:
            label.setText(text)

    def set_button_text(self, name: str, text: str) -> None:
        button = self.button(name)
        if button is not None:
            button.setText(text)

    def connect_button(self, name: str, callback: Callable[[], None]) -> None:
        button = self.button(name)
        if button is not None:
            button.clicked.connect(lambda _checked=False: callback())

    def info(self, title: str, message: str) -> None:
        QMessageBox.information(self.page, title, message)

    def warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self.page, title, message)
