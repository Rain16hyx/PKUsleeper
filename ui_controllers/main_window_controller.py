"""
主窗口控制中心：负责整个软件外壳的加载、左侧菜单栏的点击事件绑定，以及右侧页面的无缝切换。
"""

from __future__ import annotations
from pathlib import Path

# 导入 PySide6 核心组件：
# QLabel(文本标签), QPushButton(按钮), QStackedWidget(层叠页面容器), QVBoxLayout(垂直布局), QWidget(通用组件)
from PySide6.QtWidgets import QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

# 导入你们团队自己写的业务逻辑和页面控制器
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
    """负责加载 MainMenu.ui（主外壳），切入各个子页面，并协调它们的控制器"""

    def __init__(self, tracker: MainTracker, project_root: Path | None = None) -> None:
        # 1. 自动定位项目的根目录路径
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        
        # 2. 记住后端核心状态跟踪器（你们之前写的无UI纯代码服务核心）
        self.tracker = tracker
        
        # 3. 桥接器：把后端的服务包装一下，准备喂给各个 UI 页面使用
        self.bridge = ServiceBridge(tracker)
        
        # 4. 【核心点】加载主界面的“外壳”文件（也就是带有左侧边栏和右侧空白大框的总体界面）
        self.window = load_ui(self.project_root / "MainMenu.ui")
        
        # 5. 【核心点】在读入的外壳中，利用名字 "stackedWidget" 找到右侧的“舞台”（层叠页面容器）
        self.stack = self.window.findChild(QStackedWidget, "stackedWidget")
        if self.stack is None:
            raise RuntimeError("MainMenu.ui 必须包含一个名为 stackedWidget 的 QStackedWidget 控件。")

        # 用于在内存中存放所有子页面对象和它们的控制器的字典
        self.pages: dict[str, QWidget] = {}
        self.controllers: dict[str, UiController] = {}
        self.sidebar_buttons: dict[str, QPushButton] = {}

        # 6. 开始初始化大管家：
        self._clear_designer_placeholder_pages() # 擦干净舞台
        self._load_pages()                       # 把主页、分析页等一个个搬上舞台
        self._bind_sidebar()                     # 把左侧按钮和页面切换绑定起来
        self.switch_page("home")                 # 程序一启动，默认显示主页 ("home")

    def show(self) -> None:
        """对外公开的方法：正式把整个大窗口显示在屏幕上"""
        self.window.show()

    def switch_page(self, page_name: str) -> None:
        """核心业务函数：根据页面名字（如 'analysis'），无缝切换右侧内容"""
        page = self.pages.get(page_name)
        if page is None:
            return

        # 让层叠容器切换到当前选中的页面组件
        self.stack.setCurrentWidget(page)
        
        # 通知后端服务：当前界面状态发生了改变
        self.tracker.shift_state(None)
        
        # 让左侧对应的菜单按钮变成“被选中高亮”状态，其余熄灭
        self._update_sidebar_checked(page_name)
        
        # 【重要】切换页面后，自动触发该页面的“数据刷新”功能
        # 比如切到分析页，就立刻重新去本地读取 JSON 计算最新的平均睡眠时长！
        controller = self.controllers.get(page_name)
        if controller is not None:
            controller.refresh()

    def refresh_current_page(self) -> None:
        """刷新当前正在看的这一个页面"""
        current = self.stack.currentWidget()
        for page_name, page in self.pages.items():
            if page is current:
                controller = self.controllers.get(page_name)
                if controller is not None:
                    controller.refresh()
                return

    def refresh_all_pages(self) -> None:
        """一键刷新所有子页面（通常在刚存入新睡眠数据时调用）"""
        for controller in self.controllers.values():
            controller.refresh()

    def _clear_designer_placeholder_pages(self) -> None:
        """辅助函数：清空在 Qt Designer 软件里留下的测试空白页，确保舞台干净"""
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater() 

    def _load_pages(self) -> None:
        """辅助函数：批量把具体的子页面（主页、分析、打卡记录等）塞进右侧舞台"""
        # 定义页面清单：(页面代号, 界面设计文件, 专属页面管理员类)
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
            # 读取单独的子页面设计文件
            page = load_ui(self.project_root / "pages" / ui_file)
            self.pages[page_name] = page
            self.stack.addWidget(page) # 把页面塞给舞台，但此时处于大幕后，看不见

            # 根据每个页面的功能不同，实例化它们对应的管理员
            # 把页面组件、业务桥接器、切换页面方法传递给管理员
            if controller_cls is HomeController:
                controller = controller_cls(
                    page, self.bridge, self.switch_page, self.refresh_all_pages
                )
            elif controller_cls is RecordsController:
                controller = controller_cls(page, self.bridge, self.switch_page)
            else:
                controller = controller_cls(page, self.bridge)
                
            # 激活该页面内部的按钮点击、输入框等事件绑定
            controller.bind_events()
            # 登记在册，方便后续调用
            self.controllers[page_name] = controller

        # 为“我的（个人信息）”页面临时创建一个纯文本的占位页面
        profile_page = self._create_placeholder_page("我的", "个人信息页面接口已预留。")
        self.pages["profile"] = profile_page
        self.stack.addWidget(profile_page)
        self.controllers["profile"] = StaticPageController(profile_page, self.bridge)

    def _bind_sidebar(self) -> None:
        """辅助函数：把左侧边栏上的那一堆物理按钮，映射到右侧的页面代号上"""
        mapping = {
            "pushButton": "home",          # 点击第一个按钮切主页
            "pushButton_2": "records",      # 点击第二个按钮切记录页
            "pushButton_3": "analysis",     # 点击第三个按钮切你的数据分析页
            "pushButton_4": "planning",
            "pushButton_5": "sleepmap",
            "pushButton_6": "goal",
            "pushButton_7": "achievement",
            "pushButton_8": "profile",
        }

        for button_name, page_name in mapping.items():
            # 在外壳 UI 里根据名字搜寻按钮对象
            button = self.window.findChild(QPushButton, button_name)
            if button is None:
                continue
            self.sidebar_buttons[page_name] = button
            
            # 【核心点】信号与槽连接：只要按钮被 clicked（点击），
            # 就会触发执行 self.switch_page(page_name)
            button.clicked.connect(lambda _checked=False, name=page_name: self.switch_page(name))

    def _update_sidebar_checked(self, active_page: str) -> None:
        """辅助函数：更新按钮的高亮状态，被切中的设为 True，其余设为 False"""
        for page_name, button in self.sidebar_buttons.items():
            button.setChecked(page_name == active_page)

    @staticmethod
    def _create_placeholder_page(title: str, message: str) -> QWidget:
        """静态辅助函数：用于快速用纯代码拼出一个简单的带文字页面（未开发页面的替身）"""
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
        layout.addStretch(1) # 添加弹簧，把文字推到最上方
        return page