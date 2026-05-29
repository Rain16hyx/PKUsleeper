"""Main window controller and page wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from service import MainTracker
from ui_controllers.base import UiController, load_ui
from ui_controllers.page_controllers import (
    AchievementController,
    AnalysisController,
    GoalController,
    HomeController,
    PlanningController,
    RecordsController,
    SleepMapController,
    StaticPageController,
)
from ui_controllers.service_bridge import ServiceBridge


class MainWindowController:
    """Load MainMenu.ui, insert pages, and coordinate page controllers."""

    def __init__(self, tracker: MainTracker, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.tracker = tracker
        self.bridge = ServiceBridge(tracker)
        self.window = load_ui(self.project_root / "MainMenu.ui")
        self.stack = self.window.findChild(QStackedWidget, "stackedWidget")
        if self.stack is None:
            raise RuntimeError("MainMenu.ui must contain QStackedWidget named stackedWidget.")

        self.pages: dict[str, QWidget] = {}
        self.controllers: dict[str, UiController] = {}
        self.sidebar_buttons: dict[str, QPushButton] = {}

        self._clear_designer_placeholder_pages()
        self._load_pages()
        self._bind_sidebar()
        self.switch_page("home")

    def show(self) -> None:
        self.window.show()

    def switch_page(self, page_name: str) -> None:
        page = self.pages.get(page_name)
        if page is None:
            return

        self.stack.setCurrentWidget(page)
        self.tracker.shift_state(None)
        self._update_sidebar_checked(page_name)
        controller = self.controllers.get(page_name)
        if controller is not None:
            controller.refresh()

    def refresh_current_page(self) -> None:
        current = self.stack.currentWidget()
        for page_name, page in self.pages.items():
            if page is current:
                controller = self.controllers.get(page_name)
                if controller is not None:
                    controller.refresh()
                return

    def refresh_all_pages(self) -> None:
        for controller in self.controllers.values():
            controller.refresh()

    def _clear_designer_placeholder_pages(self) -> None:
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater()

    def _load_pages(self) -> None:
        page_specs = [
            ("home", "homepage.ui", HomeController),
            ("records", "records.ui", RecordsController),
            ("analysis", "analysis.ui", AnalysisController),
            ("planning", "planning.ui", PlanningController),
            ("sleepmap", "sleepmap.ui", SleepMapController),
            ("goal", "goal.ui", GoalController),
            ("achievement", "achievement.ui", AchievementController),
        ]

        for page_name, ui_file, controller_cls in page_specs:
            page = load_ui(self.project_root / "pages" / ui_file)
            self.pages[page_name] = page
            self.stack.addWidget(page)

            if controller_cls is HomeController:
                controller = controller_cls(
                    page,
                    self.bridge,
                    self.switch_page,
                    self.refresh_all_pages,
                )
            elif controller_cls is RecordsController:
                controller = controller_cls(page, self.bridge, self.switch_page)
            else:
                controller = controller_cls(page, self.bridge)
            controller.bind_events()
            self.controllers[page_name] = controller

        profile_page = self._create_placeholder_page("我的", "个人信息页面接口已预留。")
        self.pages["profile"] = profile_page
        self.stack.addWidget(profile_page)
        self.controllers["profile"] = StaticPageController(profile_page, self.bridge)

    def _bind_sidebar(self) -> None:
        mapping = {
            "pushButton": "home",
            "pushButton_2": "records",
            "pushButton_3": "analysis",
            "pushButton_4": "planning",
            "pushButton_5": "sleepmap",
            "pushButton_6": "goal",
            "pushButton_7": "achievement",
            "pushButton_8": "profile",
        }

        for button_name, page_name in mapping.items():
            button = self.window.findChild(QPushButton, button_name)
            if button is None:
                continue
            self.sidebar_buttons[page_name] = button
            button.clicked.connect(lambda _checked=False, name=page_name: self.switch_page(name))

    def _update_sidebar_checked(self, active_page: str) -> None:
        for page_name, button in self.sidebar_buttons.items():
            button.setChecked(page_name == active_page)

    @staticmethod
    def _create_placeholder_page(title: str, message: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(44, 34, 44, 34)
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(
            'font-family: "Microsoft YaHei UI"; font-size: 32px; '
            "font-weight: 800; color: #222226;"
        )
        message_label = QLabel(message)
        message_label.setObjectName("subtitleLabel")
        message_label.setStyleSheet(
            'font-family: "Microsoft YaHei UI"; font-size: 16px; color: #8a817a;'
        )
        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addStretch(1)
        return page
