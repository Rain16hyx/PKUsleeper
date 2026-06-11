"""主窗口控制中心。"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pkusleeper.services import MainTracker
from pkusleeper.ui.base import UiController, load_ui
from pkusleeper.ui.bridge import ServiceBridge
from pkusleeper.ui.features.achievements.controller import AchievementController
from pkusleeper.ui.features.goals.controller import GoalController
from pkusleeper.ui.features.home.controller import HomeController
from pkusleeper.ui.features.map.controller import MapController
from pkusleeper.ui.features.planning.controller import PlanningController
from pkusleeper.ui.features.profile.controller import ProfileController
from pkusleeper.ui.features.records.controller import RecordsController
from pkusleeper.ui.features.reports.controller import ReportController


class MainWindowController:
    """负责加载 main_menu.ui（主外壳），切入各个子页面，并协调它们的控制器"""

    PAGE_SPECS = (
        ("home", Path("features/home/home.ui"), HomeController),
        ("records", Path("features/records/records.ui"), RecordsController),
        ("analysis", Path("features/reports/report.ui"), ReportController),
        ("planning", Path("features/planning/planning.ui"), PlanningController),
        ("sleepmap", Path("features/map/map.ui"), MapController),
        ("goal", Path("features/goals/goal.ui"), GoalController),
        ("achievement", Path("features/achievements/achievement.ui"), AchievementController),
    )

    SIDEBAR_MAPPING = {
        "pushButton": "home",
        "pushButton_2": "records",
        "pushButton_3": "analysis",
        "pushButton_4": "planning",
        "pushButton_5": "sleepmap",
        "pushButton_6": "goal",
        "pushButton_7": "achievement",
        "pushButton_8": "profile",
    }

    def __init__(self, tracker: MainTracker, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.ui_root = Path(__file__).resolve().parents[1]
        self.tracker = tracker
        self.bridge = ServiceBridge(tracker)
        self.window = load_ui(Path(__file__).with_name("main_menu.ui"))
        self.stack = self.window.findChild(QStackedWidget, "stackedWidget")
        if self.stack is None:
            raise RuntimeError("main_menu.ui 必须包含一个名为 stackedWidget 的 QStackedWidget 控件。")

        self.pages: dict[str, QWidget] = {}
        self.controllers: dict[str, UiController] = {}
        self.sidebar_buttons: dict[str, QPushButton] = {}

        self._clear_designer_placeholder_pages()
        self._load_pages()
        self._bind_sidebar()
        self._start_header_timer()
        self.switch_page("home")

    def show(self) -> None:
        self.window.show()

    def switch_page(self, page_name: str) -> None:
        """切换右侧内容页，并刷新当前页数据。"""
        page = self.pages.get(page_name)
        if page is None:
            return

        self.stack.setCurrentWidget(page)
        self.tracker.shift_state(None)
        self._update_sidebar_checked(page_name)

        controller = self.controllers.get(page_name)
        if controller is not None:
            controller.refresh_common_header()
            controller.refresh()

    def refresh_current_page(self) -> None:
        """刷新当前正在看的这一个页面"""
        current = self.stack.currentWidget()
        for page_name, page in self.pages.items():
            if page is current:
                controller = self.controllers.get(page_name)
                if controller is not None:
                    controller.refresh_common_header()
                    controller.refresh()
                return

    def refresh_all_pages(self) -> None:
        """一键刷新所有子页面（通常在刚存入新睡眠数据时调用）"""
        for controller in self.controllers.values():
            controller.refresh_common_header()
            controller.refresh()

    def refresh_all_headers(self) -> None:
        """刷新所有页面顶部的公共日期栏。"""
        for controller in self.controllers.values():
            controller.refresh_common_header()

    def _clear_designer_placeholder_pages(self) -> None:
        """清空 Qt Designer 里留下的占位页。"""
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater() 

    def _load_pages(self) -> None:
        """加载子页面并创建对应控制器。"""
        for page_name, ui_file, controller_cls in self.PAGE_SPECS:
            page = load_ui(self.ui_root / ui_file)
            self.pages[page_name] = page
            self.stack.addWidget(page)

            if controller_cls is HomeController:
                controller = controller_cls(
                    page, self.bridge, self.switch_page, self.refresh_all_pages
                )
            elif controller_cls is RecordsController:
                controller = controller_cls(page, self.bridge, self.switch_page)
            else:
                controller = controller_cls(page, self.bridge)

            controller.bind_events()
            controller.refresh_common_header()
            self.controllers[page_name] = controller
            self._bind_settings_button(page)

        profile_page = self._create_profile_page()
        self.pages["profile"] = profile_page
        self.stack.addWidget(profile_page)
        profile_controller = ProfileController(profile_page, self.bridge)
        profile_controller.bind_events()
        profile_controller.refresh()
        self.controllers["profile"] = profile_controller

    def _start_header_timer(self) -> None:
        self.header_timer = QTimer(self.window)
        self.header_timer.timeout.connect(self.refresh_all_headers)
        self.header_timer.start(60_000)

    def _bind_sidebar(self) -> None:
        """绑定左侧边栏按钮。"""
        for button_name, page_name in self.SIDEBAR_MAPPING.items():
            button = self.window.findChild(QPushButton, button_name)
            if button is None:
                continue
            self.sidebar_buttons[page_name] = button
            button.clicked.connect(lambda _checked=False, name=page_name: self.switch_page(name))

    def _bind_settings_button(self, page: QWidget) -> None:
        button = page.findChild(QPushButton, "settingsButton")
        if button is not None:
            button.clicked.connect(lambda _checked=False: self.switch_page("profile"))

    def _update_sidebar_checked(self, active_page: str) -> None:
        for page_name, button in self.sidebar_buttons.items():
            button.setChecked(page_name == active_page)

    def _create_profile_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(44, 34, 44, 34)
        layout.setSpacing(22)
        
        title_label = QLabel("我的")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(
            'font-family: "Microsoft YaHei UI"; font-size: 32px; '
            "font-weight: 800; color: #222226;"
        )

        message_label = QLabel("个人设置")
        message_label.setObjectName("subtitleLabel")
        message_label.setStyleSheet(
            'font-family: "Microsoft YaHei UI"; font-size: 16px; color: #8a817a;'
        )

        card = QFrame()
        card.setObjectName("profileCard")
        card.setStyleSheet(
            """
            #profileCard {
                background: #fffefd;
                border: 1px solid #e5d9cc;
                border-radius: 13px;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(16)

        card_title = QLabel("用户名")
        card_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #242328;")

        row = QHBoxLayout()
        row.setSpacing(16)

        username_value = QLabel("PKU student")
        username_value.setObjectName("usernameValue")
        username_value.setStyleSheet("font-size: 26px; font-weight: 900; color: #b8151d;")

        edit_button = QPushButton("编辑用户名")
        edit_button.setObjectName("editUsernameButton")
        edit_button.setStyleSheet(
            """
            #editUsernameButton {
                min-height: 38px;
                padding: 0 18px;
                border: 1px solid #c91d25;
                border-radius: 7px;
                background: #fffefd;
                color: #c91d25;
                font-size: 15px;
                font-weight: 800;
            }
            #editUsernameButton:hover {
                background: #fff2ee;
            }
            """
        )

        row.addWidget(username_value)
        row.addStretch(1)
        row.addWidget(edit_button)

        profile_hint = QLabel()
        profile_hint.setObjectName("profileHint")
        profile_hint.setWordWrap(True)
        profile_hint.setStyleSheet("font-size: 14px; color: #8a817a;")

        card_layout.addWidget(card_title)
        card_layout.addLayout(row)
        card_layout.addWidget(profile_hint)

        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addWidget(card)
        layout.addStretch(1)
        return page
