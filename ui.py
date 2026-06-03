from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
from PySide6.QtCore import Qt
from models import SleepType, SleepEnvironment
import pyqtgraph as pg

class SleepConfigDialog(QDialog):
    """自定义睡眠配置弹窗：按键单选 + 动态校验亮起"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("开启本次睡眠")
        self.setFixedSize(360, 240)
        # 设置和主页一致的红白色系优雅样式
        self.setStyleSheet("""
            QDialog { background-color: #fffdf9; }
            QLabel { color: #25252a; font-size: 14px; font-weight: 600; }
            QPushButton { 
                border: 1px solid #e4d8cb; border-radius: 6px; 
                background: #fffefa; color: #29272a; min-height: 32px; font-size: 13px;
            }
            QPushButton:hover { background: #fff8ed; border-color: #cfb99c; }
            QPushButton:checked { 
                background-color: #aa121a; color: white; border-color: #aa121a; font-weight: bold; 
            }
            #okButton { 
                background-color: #aa121a; color: white; border: none; border-radius: 8px;
                font-size: 15px; font-weight: bold; min-height: 40px;
            }
            #okButton:disabled { background-color: #e5d9cc; color: #8a817a; }
            #okButton:hover:enabled { background-color: #d72a31; }
        """)

        # 核心布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 1. 第一行：睡眠类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("睡眠类型："))
        self.btn_night = QPushButton("夜间睡眠")
        self.btn_nap = QPushButton("高效午休")
        for btn in (self.btn_night, self.btn_nap):
            btn.setCheckable(True)
            type_layout.addWidget(btn)
        
        # 利用 QButtonGroup 强制两个按键互斥（单选）
        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.btn_night)
        self.type_group.addButton(self.btn_nap)
        main_layout.addLayout(type_layout)

        # 2. 第二行：睡眠环境
        env_layout = QHBoxLayout()
        env_layout.addWidget(QLabel("睡眠环境："))
        self.btn_dorm = QPushButton("燕园宿舍")
        self.btn_home = QPushButton("温馨家中")
        for btn in (self.btn_dorm, self.btn_home):
            btn.setCheckable(True)
            env_layout.addWidget(btn)
            
        self.env_group = QButtonGroup(self)
        self.env_group.addButton(self.btn_dorm)
        self.env_group.addButton(self.btn_home)
        main_layout.addLayout(env_layout)

        # 3. 第三行：确定按钮
        self.btn_ok = QPushButton("确定开始")
        self.btn_ok.setObjectName("okButton")
        self.btn_ok.setEnabled(False) # 初始灰色不可点
        main_layout.addWidget(self.btn_ok)

        # 绑定状态校验信号
        self.type_group.buttonToggled.connect(self.validate_selection)
        self.env_group.buttonToggled.connect(self.validate_selection)
        self.btn_ok.clicked.connect(self.accept) # 点击确定关闭窗口并返回 QDialog.Accepted

    def validate_selection(self) -> None:
        """动态校验：只有两个组都有选中的按钮时，确定键才亮起"""
        has_type = self.type_group.checkedButton() is not None
        has_env = self.env_group.checkedButton() is not None
        self.btn_ok.setEnabled(has_type and has_env)

    def get_result(self) -> tuple[SleepType, SleepEnvironment]:
        """供外部提取最终数据的接口"""
        sleep_type = SleepType.NIGHT if self.btn_night.isChecked() else SleepType.NAP
        environment = SleepEnvironment.DORMITORY if self.btn_dorm.isChecked() else SleepEnvironment.HOME
        return sleep_type, environment

#时间轴刻度
class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            val = int(v) % 1440
            if val < 0:
                val += 1440
            hours = val // 60
            minutes = val % 60
            strings.append(f"{hours:02d}:{minutes:02d}")
        return strings