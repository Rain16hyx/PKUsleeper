"""Controllers for individual stacked pages."""

from __future__ import annotations

from datetime import datetime,timedelta
from typing import Callable

from PySide6.QtWidgets import QProgressBar

from models import SleepRecord,SleepType
from ui_controllers.base import UiController
from ui_controllers.service_bridge import ServiceBridge
from ui import SleepConfigDialog
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup,QWidget
from PySide6.QtCore import Qt
from utils.data_processing import SleepReportBuilder

import pyqtgraph as pg
import numpy as np

NavigateCallback = Callable[[str], None]
RefreshCallback = Callable[[], None]


class HomeController(UiController):
    def __init__(
        self,
        page,
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
        self.set_label_text("label_4", f"◎  今日目标： {data['today_goal_hours']} 小时")
        self.set_label_text("label_5", f"▤  当前状态： {data['current_status']}")
        self.set_label_text("label_6", f"♨  连续达成： {data['streak_days']} 天")

    def toggle_sleep(self) -> None:
        if self.bridge.get_home_snapshot()["is_sleeping"]:
            result = self.bridge.finish_sleep()
        else:
            #点击开始睡眠后，要设计让用户填写睡眠环境和睡眠类型的功能
            # 1. 实例化弹窗
            dialog = SleepConfigDialog(self.page)
            
            # 2. 阻塞运行弹窗。如果用户点了右上角叉号或者没选完，exec() 不会返回 Accepted，直接跳过不执行任何操作
            if dialog.exec() == QDialog.Accepted:
                # 3. 完美拿到用户在弹窗里选好的真枚举数据！
                chosen_type, chosen_env = dialog.get_result()
                
                # 4. 带着真数据，通知 Bridge 开启真正的后端记录
                result = self.bridge.start_sleep(sleep_type=chosen_type, environment=chosen_env)
            else:
                return # 用户取消或关闭了弹窗，静默退出

        if not result.ok:
            self.warning("睡眠记录", result.message)
        self.refresh_all()


class RecordsController(UiController):
    def __init__(
        self,
        page,
        bridge: ServiceBridge,
        navigate: NavigateCallback,
    ) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate

    def bind_events(self) -> None:
        for name in [
            "reportButton",
            "reportButton_2",
            "reportButton_3",
            "reportButton_4",
            "reportButton_5",
        ]:
            self.connect_button(name, lambda _checked=False: self.navigate("analysis"))
        self.connect_button("rangeButton", self.refresh)
        self.connect_button("rangeButton_2", self.refresh)

    def refresh(self) -> None:
        # 最近的 5 条记录
        records = self.bridge.get_recent_records(5)
        self.set_label_text("countLabel", f"共 {len(records)} 条记录")
        # 控制 5 行 UI 渲染
        for i in range(1, 6):
            suffix = "" if i == 1 else f"_{i}"
            # 如果索引小于真实记录的长度，说明有数据，正常渲染
            if i <= len(records):
                self._apply_record_to_row(records[i-1], suffix)
            else:
                # 💡 如果没有数据，把多余的假行文本清空
                self.set_label_text(f"dateText{suffix}", "--/--")
                self.set_label_text(f"durationText{suffix}", "-- 小时")
                self.set_label_text(f"timeText{suffix}", "--:-- - --:--")
                self.set_label_text(f"scoreBadge{suffix}", "-- 分")

    def _apply_record_to_row(self, record: SleepRecord, suffix: str) -> None:
        self.set_label_text(f"dateText{suffix}", record.started_at.strftime("%m/%d（%a）"))
        self.set_label_text(f"durationText{suffix}", f"{self._duration_hours(record):.1f} 小时")
        self.set_label_text(
            f"timeText{suffix}",
            f"{record.started_at:%H:%M} - {record.ended_at:%H:%M}",
        )
        self.set_label_text(f"scoreBadge{suffix}", f"{self._score_for(record)} 分")

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        return round((record.ended_at - record.started_at).total_seconds() / 3600, 1)

    @classmethod
    def _score_for(cls, record: SleepRecord) -> int:
        grader=SleepReportBuilder()
        return grader.calculate_sleep_quality(record)

class AnalysisController(UiController):
    def __init__(self, page, bridge, navigate) -> None:
        super().__init__(page, bridge)
        self.navigate = navigate
        self.current_days = 7 
        
        # 初始化图表控件容器
        self.duration_plot = None
        self.time_plot = None
        
        # 配置 pyqtgraph 全局样式为优雅的白底黑字
        pg.setConfigOption('background', '#fffefd')
        pg.setConfigOption('foreground', '#25252a')

    def bind_events(self) -> None:
        # 绑定 7天 / 30天 按钮切换
        self.connect_button("rangeButton", lambda: self.switch_range(7))
        self.connect_button("rangeButton_2", lambda: self.switch_range(30))
        
        # 动态初始化图表控件（
        self._inject_real_charts()

    def _inject_real_charts(self) -> None:
        """核心解耦：注入 PlotWidget"""
        # 1. 净化左侧时长图表框架
        left_frame = self.page.findChild(QWidget, "durationChartFrame")
        if left_frame and left_frame.layout():
            # 清理旧的假数据 Grid 布局
            grid = left_frame.findChild(QVBoxLayout, "durationChartLayout")
            if grid:
                # 动态创建一个 PyQtGraph 画布
                self.duration_plot = pg.PlotWidget()
                grid.addWidget(self.duration_plot)

        # 2. 净化右侧时间图表框架
        right_frame = self.page.findChild(QWidget, "timeChartFrame")
        if right_frame and right_frame.layout():
            grid_right = right_frame.findChild(QVBoxLayout, "timeChartLayout")
            if grid_right:
                self.time_plot = pg.PlotWidget()
                grid_right.addWidget(self.time_plot)

    def switch_range(self, days: int) -> None:
        if self.current_days == days:
            return
        self.current_days = days
        self.refresh()

    def refresh(self) -> None:
        # 从 Bridge 获取包含最近原始记录的面板数据
        raw_records = self.bridge.get_recent_records(self.current_days, sleep_type=SleepType.NIGHT)
        dashboard_data = self.bridge.get_report_dashboard(self.current_days)
        
        # 1. 刷新顶部的四个核心卡片文本
        self.set_label_text("statValue", f"{dashboard_data['avg_sleep_hours']:.1f}")
        self.set_label_text("statValue_2", dashboard_data["avg_sleep_time"])
        self.set_label_text("statValue_3", dashboard_data["avg_wake_time"])
        self.set_label_text("statValue_4", str(dashboard_data["goal_completion_rate"]))
        self.set_label_text("ringLabel_2", f"{dashboard_data['score']}\n分")
        self.set_label_text("ringLabel_3", f"{dashboard_data['done_days']}/{self.current_days}")

        # 2. 调度核心绘图引擎
        if self.current_days == 7:
            self._draw_7_days_charts(raw_records)
        else:
            self._draw_30_days_charts(raw_records)

    # ==================== 📈 7天看板：自适应高灵敏折线图 ====================
    def _draw_7_days_charts(self, records) -> None:
        self.duration_plot.clear()
        self.time_plot.clear()
        
        # 补全最近 7 天的时间线，如果没有数据则留空（完美对应空缺处理需求）
        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d")) for i, d in enumerate(date_list)]
        
        # 构建对齐的数据字典
        record_dict = {r.started_at.date(): r for r in records}
        
        durations = []
        sleep_times = []
        wake_times = []
        x_indices = []
        
        for i, d in enumerate(date_list):
            if d in record_dict:
                r = record_dict[d]
                durations.append((r.ended_at - r.started_at).total_seconds() / 3600)
                # 将时间映射为当天的分钟数进行绘图
                sleep_times.append(r.started_at.hour * 60 + r.started_at.minute)
                wake_times.append(r.ended_at.hour * 60 + r.ended_at.minute)
                x_indices.append(i)

        if not x_indices:
            return

        # --- 左图：时长自适应折线 ---
        self.duration_plot.getAxis('bottom').setTicks([x_ticks])
        # 🎯 核心黑魔法：动态调整纵轴比例。根据最大最小值自适应平铺，保证哪怕波动只有 0.2 小时也清晰可见！
        self.duration_plot.setYRange(max(0, min(durations) - 0.5), max(durations) + 0.5)
        self.duration_plot.plot(x_indices, durations, pen=pg.mkPen('#c2151d', width=3), symbol='o', symbolSize=8, symbolBrush='#c2151d')

        # --- 右图：入睡与起床双折线 ---
        self.time_plot.getAxis('bottom').setTicks([x_ticks])
        # 格式化纵轴为时间字符串
        y_time_ticks = [(m, f"{m//60:02d}:{m%60:02d}") for m in range(0, 1440, 120)]
        self.time_plot.getAxis('left').setTicks([y_time_ticks])
        
        all_time_values = sleep_times + wake_times
        self.time_plot.setYRange(max(0, min(all_time_values) - 60), min(1440, max(all_time_values) + 60))
        
        # 绘制两条折线
        self.time_plot.plot(x_indices, sleep_times, pen=pg.mkPen('#c2151d', width=2), symbol='x', symbolSize=6, symbolBrush='#c2151d', name='入睡')
        self.time_plot.plot(x_indices, wake_times, pen=pg.mkPen('#f0a12d', width=2), symbol='o', symbolSize=6, symbolBrush='#f0a12d', name='起床')

    # ==================== 📊 30天看板：长方形时段覆盖条形图 ====================
    def _draw_30_days_charts(self, records) -> None:
        self.duration_plot.clear()
        self.time_plot.clear()
        
        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d") if i % 5 == 0 else "") for i, d in enumerate(date_list)]
        
        record_dict = {r.started_at.date(): r for r in records}
        
        # --- 左图：30天睡眠时长柱状图 ---
        durations = [0.0] * 30
        for i, d in enumerate(date_list):
            if d in record_dict:
                r = record_dict[d]
                durations[i] = (r.ended_at - r.started_at).total_seconds() / 3600
                
        bg_item = pg.BarGraphItem(x=list(range(30)), height=durations, width=0.6, brush='#c2151d', pen=None)
        self.duration_plot.addItem(bg_item)
        self.duration_plot.getAxis('bottom').setTicks([x_ticks])
        self.duration_plot.setYRange(0, max(durations + [10]))

        # --- 右图：30天长方形睡眠时段图 (甘特区间柱状) ---
        self.time_plot.getAxis('bottom').setTicks([x_ticks])
        y_time_ticks = [(m, f"{m//60:02d}:{m%60:02d}") for m in range(0, 1440, 180)]
        self.time_plot.getAxis('left').setTicks([y_time_ticks])

        all_sleep_points = []
        for i, d in enumerate(date_list):
            if d in record_dict:
                r = record_dict[d]
                start_min = r.started_at.hour * 60 + r.started_at.minute
                end_min = r.ended_at.hour * 60 + r.ended_at.minute
                
                # 计算长方形的高度和起始底边
                duration_min = end_min - start_min
                if duration_min < 0: # 跨年/跨天保护逻辑
                    duration_min += 1440
                
                all_sleep_points.append((start_min, end_min))
                
                # 🎯 核心：在时间轴的 [start_min, start_min + duration_min] 区间铺设长方形条
                box = pg.BarGraphItem(x=[i], y0=[start_min], height=[duration_min], width=0.7, brush='#f0a12d', pen=None)
                self.time_plot.addItem(box)
        
        if all_sleep_points:
            flat_times = [p for pt in all_sleep_points for p in pt]
            self.time_plot.setYRange(max(0, min(flat_times) - 60), min(1440, max(flat_times) + 60))


class PlanningController(UiController):
    def bind_events(self) -> None:
        self.connect_button("pushButton", self._show_placeholder)
        self.connect_button("pushButton_2", self._show_placeholder)

    def refresh(self) -> None:
        data = self.bridge.get_planning_dashboard()
        self.set_label_text(
            "resultLine",
            f"☾  推荐夜间睡眠：\n    {data['night_sleep']}",
        )
        self.set_label_text("resultLine_2", f"☼  推荐午休：\n    {data['nap']}")
        self.set_label_text("resultLine_3", f"⌖  常用地点：\n    {data['places']}")

    def _show_placeholder(self) -> None:
        self.info("智能规划", "课表编辑和自动规划接口已预留，底层规则完成后可接入。")


class SleepMapController(UiController):
    def refresh(self) -> None:
        data = self.bridge.get_map_dashboard()
        self.set_label_text(
            "label_2",
            f"已解锁 {data['unlocked_count']} / {data['total_count']} 个地标",
        )
        self.set_label_text("recommendPlace", data["recommended_node"])


class GoalController(UiController):
    def bind_events(self) -> None:
        self.connect_button("saveButton", self._show_placeholder)
        self.connect_button("newGoalButton", self._show_placeholder)

    def refresh(self) -> None:
        data = self.bridge.get_goal_dashboard()
        self.set_label_text("goalValueLabel", f"{data['target_hours']:.1f}")
        self.set_label_text("weekTextStrong", f"{data['done_days']} / {data['total_days']} 天")
        self.set_label_text("percentLabel", f"{data['rate']}%")
        progress = self.page.findChild(QProgressBar, "progressBar")
        if progress is not None:
            progress.setValue(data["rate"])

    def _show_placeholder(self) -> None:
        self.info("睡眠目标", "目标编辑接口已预留，底层存储与规则完成后可接入。")


class AchievementController(UiController):
    def refresh(self) -> None:
        data = self.bridge.get_achievement_dashboard()
        self.set_label_text("statValue", str(data["unlocked_count"]))
        self.set_label_text("statValue_2", str(data["streak_days"]))
        self.set_label_text("statValue_3", str(data["points"]))
        self.set_label_text("nextCount", str(max(0, 5 - data["unlocked_count"])))


class StaticPageController(UiController):
    """Controller for pages that are intentionally display-only for now."""

    def refresh(self) -> None:
        now = datetime.now()
        self.set_label_text("subtitleLabel", f"当前时间：{now:%Y-%m-%d %H:%M}")
