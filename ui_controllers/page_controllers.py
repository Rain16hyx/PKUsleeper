"""Controllers for individual stacked pages."""

from __future__ import annotations

from datetime import datetime,timedelta
from typing import Callable

from PySide6.QtWidgets import QFileDialog,QInputDialog,QTimeEdit,QDialog,QVBoxLayout, QDialogButtonBox,QPushButton, QGridLayout,QWidget,QLabel,QHBoxLayout,QFrame,QMessageBox
from PySide6.QtCore import QTime,Qt

from models import SleepRecord,SleepType,SleepGoal
from ui_controllers.base import UiController
from ui_controllers.service_bridge import ServiceBridge
from ui import SleepConfigDialog,TimeAxisItem
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
    def __init__(self, page, bridge) -> None:
        super().__init__(page, bridge)
        self.current_days = 7 
        
        # 初始化图表控件容器
        self.duration_plot = None
        self.time_plot = None
        
        # 配置 pyqtgraph 全局样式为优雅的白底黑字（完美契合 .ui 暖白色调 #fffdf9）
        pg.setConfigOption('background', '#fffefd')
        pg.setConfigOption('foreground', '#25252a')
        pg.setConfigOption('antialias', True)  # 开启抗锯齿，使线条更柔和高级

    def bind_events(self) -> None:
        # 绑定 7天 / 30天 按钮切换
        self.connect_button("rangeButton", lambda: self.switch_range(7))
        self.connect_button("rangeButton_2", lambda: self.switch_range(30))
        
        # 动态初始化图表控件
        self._inject_real_charts()
        
        # 绑定后立即主动刷新一次，展示初始 7 天数据
        self.refresh()

    def _inject_real_charts(self) -> None:
        """核心解耦与注入：通过 page 准确获取 Layout 并注入 PlotWidget"""
        left_frame = self.page.findChild(QWidget, "durationChartFrame")
        if left_frame and left_frame.layout():
            layout = left_frame.layout()
            self.duration_plot = pg.PlotWidget()
            self.duration_plot.showGrid(x=False, y=True, alpha=0.15)
            layout.insertWidget(1, self.duration_plot, stretch=1)

        right_frame = self.page.findChild(QWidget, "timeChartFrame")
        if right_frame and right_frame.layout():
            layout_right = right_frame.layout()
            
            time_axis = TimeAxisItem(orientation='left')
            self.time_plot = pg.PlotWidget(axisItems={'left': time_axis})
            self.time_plot.showGrid(x=False, y=True, alpha=0.15)
            
            # 7天时每120分钟（2小时）一个主刻度；30天时通过动态范围自适应
            self.time_plot.getAxis('left').setTickSpacing(120, 60) 
            
            layout_right.addWidget(self.time_plot, stretch=1)

    def switch_range(self, days: int) -> None:
        if self.current_days == days:
            return
        self.current_days = days
        
        # 🎨 增加视觉联动反馈：切换按钮激活样式表
        btn7 = self.page.findChild(QWidget, "rangeButton")
        btn30 = self.page.findChild(QWidget, "rangeButton_2")
        if btn7 and btn30:
            if days == 7:
                btn7.setStyleSheet("border-color: #d71920; color: #d71920;")
                btn30.setStyleSheet("border-color: #ead9c5; color: #4a4441;")
            else:
                btn30.setStyleSheet("border-color: #d71920; color: #d71920;")
                btn7.setStyleSheet("border-color: #ead9c5; color: #4a4441;")
                
        self.refresh()

    def refresh(self) -> None:
        # 健壮性保护：如果图表未成功注入，放弃渲染
        if not self.duration_plot or not self.time_plot:
            return

        # 从 Bridge 获取原始睡眠记录及看板统计指标
        raw_records = self.bridge.get_recent_records(self.current_days, sleep_type=SleepType.NIGHT)
        dashboard_data = self.bridge.get_report_dashboard(self.current_days)
        
        # 动态刷新顶部的四个核心卡片文本
        self.set_label_text("statValue", f"{dashboard_data.get('avg_sleep_hours', 0.0):.1f}")
        self.set_label_text("statValue_2", dashboard_data.get("avg_sleep_time", "00:00"))
        self.set_label_text("statValue_3", dashboard_data.get("avg_wake_time", "00:00"))
        self.set_label_text("statValue_4", str(dashboard_data.get("goal_completion_rate", 0)))
        self.set_label_text("ringLabel_2", f"{dashboard_data.get('score', 0)}\n分")
        self.set_label_text("ringLabel_3", f"{dashboard_data.get('done_days', 0)}/{self.current_days}")
        #左下角达标标准
        goal_hours = 8.0
        try:
            goal = self.bridge.tracker.goal_manager.sleep_goal
            if not goal:
                goal = self.bridge.tracker.repository.load_current_goal()
            if goal and hasattr(goal, 'target_duration_minutes'):
                goal_hours = round(goal.target_duration_minutes / 60.0, 1)
        except Exception:
            pass
        self.set_label_text("qualityHint", f"达标标准：睡眠时长 ≥ {goal_hours} 小时")
        # 调度绘图引擎
        if self.current_days == 7:
            self._draw_7_days_charts(raw_records)
        else:
            self._draw_30_days_charts(raw_records)

    # ==================== 📈 7天看板：自适应高灵敏折线图 ====================
    def _draw_7_days_charts(self, records) -> None:
        self.duration_plot.getPlotItem().clear()
        self.time_plot.getPlotItem().clear()
        
        self.duration_plot.getViewBox().enableAutoRange()
        self.time_plot.getViewBox().enableAutoRange()

        today = datetime.now().date()
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        x_ticks = [(i, d.strftime("%m/%d")) for i, d in enumerate(date_list)]
        
        record_dict = {r.started_at.date(): r for r in records}
        
        durations = []
        sleep_times = []
        wake_times = []
        x_indices = []
        
        for i, d in enumerate(date_list):
            if d in record_dict:
                r = record_dict[d]
                durations.append((r.ended_at - r.started_at).total_seconds() / 3600)
                # 统一映射为当天的总分钟数
                sleep_times.append(r.started_at.hour * 60 + r.started_at.minute)
                wake_times.append(r.ended_at.hour * 60 + r.ended_at.minute)
                x_indices.append(i)

        # 补全空数据兜底，防止图表因无记录而报错
        if not x_indices:
            return

        # --- 左图：时长自适应折线 ---
        self.duration_plot.getAxis('bottom').setTicks([x_ticks])
        self.duration_plot.setXRange(-0.5, 6.5, padding=0)
        self.duration_plot.setYRange(max(0, min(durations) - 0.5), max(durations) + 0.5)
        self.duration_plot.plot(x_indices, durations, pen=pg.mkPen('#c2151d', width=3), symbol='o', symbolSize=8, symbolBrush='#c2151d')

        # --- 右图：入睡与起床时间双折线 ---
        self.time_plot.getAxis('bottom').setTicks([x_ticks])
        self.time_plot.getAxis('left').setTicks(None)
        self.time_plot.getAxis('left').setTickSpacing(120, 60)
        self.time_plot.setXRange(-0.5, 6.5, padding=0)
        
        all_time_values = sleep_times + wake_times
        self.time_plot.setYRange(max(0, min(all_time_values) - 60), min(1440, max(all_time_values) + 60))
        
        # 绘制两条标志性的线（暖红入睡，暖橙起床）
        self.time_plot.plot(x_indices, sleep_times, pen=pg.mkPen('#c2151d', width=2), symbol='x', symbolSize=7, symbolBrush='#c2151d')
        self.time_plot.plot(x_indices, wake_times, pen=pg.mkPen('#f0a12d', width=2), symbol='o', symbolSize=7, symbolBrush='#f0a12d')

    # ==================== 📊 30天看板：长方形时段覆盖条形图 ====================
    def _draw_30_days_charts(self, records) -> None:
        self.duration_plot.getPlotItem().clear()
        self.time_plot.getPlotItem().clear()
        
        self.duration_plot.getViewBox().enableAutoRange()
        self.time_plot.getViewBox().enableAutoRange()

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
        self.duration_plot.setXRange(-0.5, 29.5, padding=0)
        self.duration_plot.setYRange(0, max(durations + [10]))

        # --- 右图：30天长方形睡眠时段图（高阶甘特区间柱状） ---
        self.time_plot.getAxis('bottom').setTicks([x_ticks])
        self.time_plot.getAxis('left').setTicks(None)
        self.time_plot.getAxis('left').setTickSpacing(180, 90)
        self.time_plot.setXRange(-0.5, 29.5, padding=0)
        
        all_sleep_points = []
        for i, d in enumerate(date_list):
            if d in record_dict:
                r = record_dict[d]
                start_min = r.started_at.hour * 60 + r.started_at.minute
                end_min = r.ended_at.hour * 60 + r.ended_at.minute
                
                duration_min = end_min - start_min
                if duration_min < 0:  # 跨天处理保护
                    duration_min += 1440
                
                all_sleep_points.append((start_min, end_min))
                
                # 在画布对应的天数 [i] 位置，绘制从 start_min 拔地而起、高度为 duration_min 的长方形时段块
                box = pg.BarGraphItem(x=[i], y0=[start_min], height=[duration_min], width=0.7, brush='#f0a12d', pen=None)
                self.time_plot.addItem(box)
        
        if all_sleep_points:
            flat_times = [p for pt in all_sleep_points for p in pt]
            self.time_plot.setYRange(max(0, min(flat_times) - 60), min(1440, max(flat_times) + 60))
        else:
            self.time_plot.setYRange(0, 1440)


class PlanningController(UiController):
    def bind_events(self) -> None:
        """
        绑定页面按钮点击事件
        """
        self.connect_button("pushButton", self._on_upload_timetable)
        self.connect_button("pushButton_2", self._on_trigger_plan)
        
        # 🎯 初始化时直接绘制干净的 12 节课 × 5 天的空虚线框网格
        self._init_blank_timetable()

    def refresh(self) -> None:
        """
        刷新右侧文件展示区域的建议数据
        """
        # 从 Bridge 捞取动态状态数据
        data = self.bridge.get_planning_dashboard()
        
        # 将建议信息渲染到右侧对应的 Label 上
        self.set_label_text("resultLine", f"☾  推荐夜间睡眠：\n    {data.get('night_sleep', '--')}")
        self.set_label_text("resultLine_2", f"☼  推荐午休：\n    {data.get('nap', '--')}")
        self.set_label_text("resultLine_3", f"⌖  常用地点：\n    {data.get('places', '--')}")

    # ==================== 🛠️ 核心交互槽函数 ====================

    def _on_upload_timetable(self) -> None:
        """
        处理 Excel 课表上传
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.page,
            "选择选课网课表文件",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        
        if file_path:
            success = self.bridge.upload_timetable(file_path)
            if success:
                # 🎯 核心动作：上传成功后，立刻调用渲染预览函数，将真数据画在左侧网格上！
                self._render_timetable_preview()
                
                QMessageBox.information(self.page, "通知", "课表导入成功！工作日数据已渲染，请点击【一键规划】生成睡眠新方案。")
                self.refresh()
            else:
                QMessageBox.warning(self.page, "错误", "课表解析失败，请检查 Excel 是否为标准旧版 .xls 或 .xlsx 格式。")

    def _on_trigger_plan(self) -> None:
        """
        响应‘一键规划’按钮点击
        """
        if self.bridge.current_timetable_df is None:
            QMessageBox.warning(self.page, "提示", "请先点击【编辑课表】上传您的专属课表文件！")
            return
            
        # 触发后端状态改变与智能计算
        self.bridge.has_planned = True
        
        # 刷新界面展示推荐结果
        self.refresh()
        QMessageBox.information(self.page, "规划成功", "已成功根据本周课表刚性需求与睡眠目标，为您智能生成最佳作息方案！")

    # ==================== 🎨 UI 自适应动态重绘引擎 ====================

    def _get_grid_layout(self) -> QGridLayout | None:
        """ 安全获取 UI 图纸上的 gridLayout """
        return self.page.findChild(QGridLayout, "gridLayout")

    def _init_blank_timetable(self) -> None:
        """ 
        在一开局或者每次更新课表时，在空网格中重绘纵轴 12 节课、横轴周一到周五
        """
        grid_layout = self._get_grid_layout()
        if not grid_layout: return
        
        # 强力推平之前画过的旧卡片，防止重复叠加导致界面错乱
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        
        # 1. 动态绘制横向星期表头（严格落实指示：只画周一到周五）
        weekdays = ["周一", "周二", "周三", "周四", "周五"]
        for col_idx, day_text in enumerate(weekdays, start=1):
            lbl = QLabel(day_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #26252a; padding: 4px;")
            grid_layout.addWidget(lbl, 0, col_idx)
            
        # 2. 动态绘制纵向 12 节课的“节数轴”和虚线框背景卡片
        for row_idx in range(1, 13):
            # 第 0 列：绘制课节标尺
            time_lbl = QLabel(f"第 {row_idx} 节")
            time_lbl.setAlignment(Qt.AlignCenter)
            time_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #555555; padding-right: 6px;")
            grid_layout.addWidget(time_lbl, row_idx, 0)
            
            # 第 1 到 5 列：全盘铺设优雅的空白占位虚线框
            for col_idx in range(1, 6):
                empty_box = QLabel("")
                empty_box.setStyleSheet("""
                    border: 1px dashed #eee2d8; 
                    background: #fffdfa; 
                    border-radius: 5px; 
                    min-height: 42px;
                """)
                grid_layout.addWidget(empty_box, row_idx, col_idx)

    def _render_timetable_preview(self) -> None:
        """
        真正实现数据驱动！将选课网导出的标准课表文字填入网格中渲染
        """
        df = self.bridge.current_timetable_df
        grid_layout = self._get_grid_layout()
        
        if df is None or not grid_layout: 
            return
            
        # 1. 先重置一张极其干净的 12x5 的底图表
        self._init_blank_timetable()
        
        # 2. 按星期列进行扫描和卡片覆盖
        # 这里的映射完全对接你在 ServiceBridge 中重命名后的 ['周一', '周二', '周三', '周四', '周五']
        work_days = ["周一", "周二", "周3", "周四", "周五"] # 保持与后端列清洗结果一致
        work_days = ["周一", "周二", "周三", "周四", "周五"]
        
        for col_idx, day_name in enumerate(work_days, start=1):
            if day_name not in df.columns:
                continue
                
            # 扫描这一天的 1 ~ 12 节课
            for row_idx in range(1, 13):
                df_row_index = row_idx - 1 # DataFrame 索引从 0 到 11
                if df_row_index >= len(df): 
                    break
                    
                cell_value = df.at[df_row_index, day_name]
                # 调用后端清洗函数，安全拿到课程名和地点
                course_info = self.bridge._parse_cell_content(cell_value)
                
                # 🎯 如果这节有课，动态生成原装经典温暖色卡片覆盖在占位框上面
                if course_info:
                    card_text = f"{course_info['name']}\n@{course_info['location']}"
                    course_card = QLabel(card_text)
                    course_card.setAlignment(Qt.AlignCenter)
                    
                    # 完美继承并强化你们 UI 中高颜值的 courseCell 样式
                    course_card.setStyleSheet("""
                        border: 1px solid #f0d9c8;
                        border-radius: 6px;
                        background: #fff0e7;
                        color: #29282c;
                        font-size: 11px;
                        font-weight: 600;
                        padding: 4px;
                    """)
                    
                    # 强行塞入网格，优雅覆盖原有的空虚线控件
                    grid_layout.addWidget(course_card, row_idx, col_idx)

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
        #注意这个点击的地方有bug，点不了
        self.connect_button("settingRow", self._on_change_duration)
        self.connect_button("settingRow_2", self._on_change_start_time)
        self.connect_button("saveButton", self._on_save_goal)

    def refresh(self) -> None:
        """
        界面初始化或数据更新时触发：负责将后端真数据同步到前端各种 Label 上
        """
        # 从大总管 tracker 的 goal_manager 拿到当前内存中生效的核心目标
        goal = self.bridge.tracker.goal_manager.sleep_goal
        
        # 如果内存里没有目标（比如刚开机），直接通过我们刚刚改造的存储层去硬盘里捞出来挂载到内存
        if not goal:
            goal = self.bridge.tracker.repository.load_current_goal()
            self.bridge.tracker.goal_manager.sleep_goal = goal

        # 1. 刷新左侧【当前目标】大卡片
        hours = goal.target_duration_minutes / 60.0
        self.set_label_text("goalValueLabel", f"{hours:.1f}")
        
        # 2. 动态读取并拼接左侧卡片的推荐作息文本以及右侧设置预览文本
        if goal.expected_sleep_start_time:
            start_str = goal.expected_sleep_start_time.strftime("%H:%M")
            self.set_label_text("recommendLabel", f"☾  预期作息：{start_str} 开始入睡")
            self.set_label_text("settingValue_2", start_str)
        else:
            self.set_label_text("recommendLabel", "☾  暂未设置预期入睡时间")
            self.set_label_text("settingValue_2", "--:--")

        # 3. 刷新右侧【目标设置】表单中的当前预览时长
        self.set_label_text("settingValue", f"{hours:.1f} 小时")
        
        # 4. 刷新下方的【完成情况】周进度条
        dashboard_data = self.bridge.get_goal_dashboard()
        self.set_label_text("weekTextStrong", f"{dashboard_data['done_days']} / {dashboard_data['total_days']} 天")
        self.set_label_text("percentLabel", f"{dashboard_data['rate']}%")
        
        # 联动更新 PySide6 原生进度条的空间刻度
        progress_bar = self.page.findChild(object, "progressBar")
        if progress_bar:
            progress_bar.setValue(dashboard_data['rate'])

    # ==================== 🛠️ 交互响应事件（槽函数） ====================
    
    def _on_change_duration(self) -> None:
        """当用户点击‘目标睡眠时长’整行时，弹出悬浮窗让用户选数字"""
        goal = self.bridge.tracker.goal_manager.sleep_goal
        current_val = (goal.target_duration_minutes / 60.0) if goal else 8.0

        # 弹出 PySide6 原生标准输入对话框
        val, ok = QInputDialog.getDouble(
            self.page, "修改睡眠目标", "请输入目标睡眠时长（小时）：", 
            current_val, 4.0, 12.0, 1
        )
        if ok:
            # 实时将临时的选择渲染到右侧预览 Label 上
            self.set_label_text("settingValue", f"{val:.1f} 小时")

    def _on_change_start_time(self) -> None:
        """当用户点击‘目标入睡时间’整行时，弹出一个时间选择器对话框"""
        goal = self.bridge.tracker.goal_manager.sleep_goal
        
        dialog = QDialog(self.page)
        dialog.setWindowTitle("设置入睡时间")
        layout = QVBoxLayout(dialog)
        
        time_edit = QTimeEdit(dialog)
        time_edit.setDisplayFormat("HH:mm")
        
        # 设初始值
        if goal and goal.expected_sleep_start_time:
            q_time = QTime(goal.expected_sleep_start_time.hour, goal.expected_sleep_start_time.minute)
            time_edit.setTime(q_time)
        else:
            time_edit.setTime(QTime(23, 30))
            
        layout.addWidget(time_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            selected_time = time_edit.time().toString("HH:mm")
            # 实时将临时的选择渲染到右侧预览 Label 上
            self.set_label_text("settingValue_2", selected_time)

    def _on_save_goal(self) -> None:
        """点击右下角‘保存设置’按钮时的核心逻辑"""
        try:
            # 1. 从界面两个预览 Label 上，反向捞取刚才用户用弹窗选好的最终文本
            duration_text = self.page.findChild(object, "settingValue").text()
            time_text = self.page.findChild(object, "settingValue_2").text()
            
            # 2. 解析清洗数据
            hours = float(duration_text.replace(" 小时", ""))
            duration_minutes = int(hours * 60)
            parsed_time = datetime.strptime(time_text, "%H:%M")
            
            # 3. 组装成全新的真核心目标模型对象
            new_goal = SleepGoal(
                target_value=hours,
                target_duration_minutes=duration_minutes,
                expected_sleep_start_time=parsed_time,
                difficulty_level=1
            )
            
            # 4. 🧠 内存保存：更新大总管状态机
            self.bridge.tracker.goal_manager.sleep_goal = new_goal
            
            # 5. 🧠 硬盘持久化：调用我们刚刚在 storage 里面写好的持久化接口
            if self.bridge.tracker.repository:
                self.bridge.tracker.repository.save_current_goal(new_goal)

            self.info("通知", "睡眠目标已成功保存！")
            self.refresh()
            
        except Exception as e:
            self.warning("错误", f"保存当前睡眠目标失败: {e}")


class AchievementController(UiController):

    def refresh(self) -> None:
        data = self.bridge.get_achievement_dashboard()
        self.set_label_text(
            "statValue",
            str(data["unlocked_count"])
        )
        self.set_label_text(
            "statValue_2",
            str(data["streak_days"])
        )
        self.set_label_text(
            "statValue_3",
            str(data["points"])
        )
        self.set_label_text(
            "nextCount",
            str(max(0, 5 - data["unlocked_count"]))
        )
        achievement_data = (
            self.bridge.tracker
            .achievement_manager
            .load_user_achievements()
        )
        unlocked = achievement_data["unlocked"]
        locked = achievement_data["locked"]
        unlocked_layout = self.page.findChild(
            QVBoxLayout,
            "unlockedAchievementsLayout"
        )
        locked_layout = self.page.findChild(
            QVBoxLayout,
            "lockedAchievementsLayout"
        )
        if unlocked_layout is None:
            return
        if locked_layout is None:
            return
        while unlocked_layout.count():
            item = unlocked_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        while locked_layout.count():
            item = locked_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for achievement in unlocked:
            unlocked_layout.addWidget(
                self._create_achievement_row(
                    achievement,
                    True
                )
            )
        for achievement in locked:
            locked_layout.addWidget(
                self._create_achievement_row(
                    achievement,
                    False
                )
            )
        unlocked_layout.addStretch()
        locked_layout.addStretch()

    def _create_achievement_row(
        self,
        achievement,
        unlocked=True
    ):

        row = QFrame()

        row.setObjectName(
            "achievementRow"
            if unlocked
            else "lockedRow"
        )

        layout = QHBoxLayout(row)

        layout.setContentsMargins(
            12,
            8,
            12,
            8
        )

        name = QLabel(achievement.name)

        desc = QLabel(achievement.description)

        status = QLabel(
            "已解锁"
            if unlocked
            else "待解锁"
        )

        name.setMinimumWidth(120)

        desc.setWordWrap(True)

        layout.addWidget(name)

        layout.addWidget(desc)

        layout.addStretch()

        layout.addWidget(status)

        return row
class StaticPageController(UiController):
    """Controller for pages that are intentionally display-only for now."""

    def refresh(self) -> None:
        now = datetime.now()
        self.set_label_text("subtitleLabel", f"当前时间：{now:%Y-%m-%d %H:%M}")
