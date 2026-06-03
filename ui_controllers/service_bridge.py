"""Safe adapter between UI controllers and the current service layer.

The bridge intentionally keeps UI code independent from unfinished service
details. It calls MainTracker where stable methods exist, and returns simple
fallback data where lower-level features are still being implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from typing import Any
from uuid import uuid4
import pandas as pd
import re

from models import SleepEnvironment, SleepRecord, SleepType, SleepAchievement
from service import MainTracker
from storage import SleepRecordRepository
from utils.data_processing import StatisticDataAnalyzer,SleepReportBuilder

@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str = ""
    payload: Any | None = None


class ServiceBridge:
    """UI-facing facade with defensive fallbacks."""

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []
        self.has_planned:bool=False
        self.current_timetable_df: pd.DataFrame | None = None

    def get_home_snapshot(self) -> dict[str, Any]:
        snapshot = self._safe_call(self.tracker.get_ui_snapshot, default={})
        is_sleeping = bool(snapshot.get("is_sleeping", False))
        goal_hours = 8.0  
        try:
            goal = self.tracker.goal_manager.sleep_goal
            if not goal:
                goal = self.tracker.repository.load_current_goal()
            if goal and hasattr(goal, 'target_duration_minutes'):
                goal_hours = round(goal.target_duration_minutes / 60.0, 1)
        except Exception as e:
            print(f"动态获取睡眠目标失败，启用默认兜底值 (8.0h): {e}")

        # 如果当前正在睡觉，显示“正在熟睡中”；如果没有，且已经生成了智能课表方案，可以显示“方案运行中”，否则显示“待记录/就绪”
        if is_sleeping:
            current_status = "正在熟睡中"
        else:
            current_status = "方案运行中" if getattr(self, "has_planned", False) else "就绪"

        return {
            "is_sleeping": is_sleeping,
            "today_goal_hours": goal_hours,           
            "current_status": current_status,         
            "streak_days": self._estimate_streak_days(),
            "record_count": len(self.get_recent_records(9999)),
        }

    def start_sleep(self,
                    sleep_type:SleepType,
                    environment:SleepEnvironment,
                        ) -> ActionResult:
        try:
            if sleep_type==SleepType.NAP:
                expected_minutes=30
            else:
                goal = self.tracker.goal_manager.sleep_goal
                if goal and hasattr(goal, "target_duration_minutes"):
                    expected_minutes = goal.target_duration_minutes
                else:
                    expected_minutes = 480 
            self.tracker.start_sleeping(
                started_at=datetime.now(),
                expected_duration_minutes=expected_minutes,
                sleep_type=sleep_type,
                environment=environment,
            )
        except Exception as exc:  # noqa: BLE001 - keeps unfinished service safe for UI.
            return ActionResult(False, f"开始睡眠失败：{exc}")
        return ActionResult(True, "已开始记录本次睡眠")

    def finish_sleep(self) -> ActionResult:
        try:
            record = self.tracker.wake_up(datetime.now())
        except Exception as exc:  # noqa: BLE001
            fallback = self._finish_sleep_with_ui_fallback()
            if fallback is None:
                return ActionResult(False, f"结束睡眠失败：{exc}")
            return ActionResult(True, "底层记录接口尚未完成，已生成一条临时 UI 记录。", fallback)
        return ActionResult(True, "本次睡眠已记录", record)

    def get_recent_records(self, days: int = 7,sleep_type:SleepType|None=None) -> list[SleepRecord]:
        records = list(getattr(self.tracker, "all_records", []) or [])
        records.extend(self._fallback_records)
        if sleep_type is not None:
            records = [r for r in records if r.sleep_type == sleep_type]
        records.sort(key=lambda record: record.started_at, reverse=True)
        return records[:days]

    def get_records_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days)
        return {
            "records": records,
            "count": len(records),
        }

    def get_report_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days,sleep_type=SleepType.NIGHT)
        if not records:
            return {
                "avg_sleep_hours": 0.0,
                "avg_sleep_time": "--:--",
                "avg_wake_time": "--:--",
                "goal_completion_rate": 0,
                "score": 0,
            }
        goal = self.tracker.goal_manager.sleep_goal
        threshold_hours = (goal.target_duration_minutes / 60.0) if goal else 8.0

        durations = [self._duration_hours(record) for record in records]
        completed_days = sum(1 for value in durations if value >= threshold_hours)

        grader=SleepReportBuilder()
        avg_score = round(sum(grader.calculate_sleep_quality(r) for r in records) / len(records))
        
        return {
            "avg_sleep_hours": round(sum(durations) / len(durations), 1),
            "avg_sleep_time": self._average_time_text(
                [record.started_at for record in records]
            ),
            "avg_wake_time": self._average_time_text(
                [record.ended_at for record in records]
            ),
            "goal_completion_rate": round(completed_days / len(records) * 100),
            "score": min(100, avg_score),
        }

    def get_goal_dashboard(self) -> dict[str, Any]:
        # 1. 优先从内存获取当前的睡眠目标
        goal = self.tracker.goal_manager.sleep_goal
        
        # 2. 如果内存为空（如冷启动），主动去本地存储中捞取当前目标
        if not goal:
            goal = self.tracker.storage_manager.load_current_goal()
            self.tracker.goal_manager.sleep_goal = goal  

        # 3.统一将目标时长转换为【小时数】进行后续的比对与展示
        if goal and goal.target_duration_minutes: 
            expected_hours = goal.target_duration_minutes / 60.0
        else:
            expected_hours = 8.0  
            
        # 4. 获取最近几天的睡眠记录（这里会自动使用 record 身体里当时自带的快照进行后续历史比对）
        records = self.get_recent_records(7)
        
        # 5. 判定在这几天内，有多少天实际睡眠时间达到了【当时的目标小时数】
        done = 0
        if records:
            for record in records:
                if self._duration_hours(record) >= round(record.expected_duration_minutes/60, 1):
                    done += 1
        # 6. 计算达成率
        rate = round((done / 7) * 100) 
        return {
            "target_hours": expected_hours, 
            "done_days": done,
            "total_days": 7,
            "rate": rate,
        }

    def get_achievement_dashboard(self) -> dict[str, Any]:
        # goal=self.tracker.goal_manager.sleep_goal
        # if goal and getattr(goal, "expected_sleep_start_time", None):
        #     expected_start_time = goal.expected_sleep_start_time.time()
        # else:
        #     expected_start_time = time(23, 30)

        # if goal and getattr(goal, "target_duration_minutes", None):
        #     expected_duration = goal.target_duration_minutes / 60.0
        # else:
        #     expected_duration = 8.0
        # records = self.get_recent_records(9999,sleep_type=SleepType.NIGHT)
        # unlocked = 0
        # if records:
        #     unlocked += 1
        # if any(record.started_at.time() <= expected_start_time for record in records):
        #     unlocked += 1
        # if len(records) >= 3:
        #     unlocked += 1
        # if sum(1 for record in records if self._duration_hours(record) >= expected_duration) >= 5:
        #     unlocked += 1
        # return {
        #     "unlocked_count": unlocked,
        #     "streak_days": self._estimate_streak_days(),
        #     "points": unlocked * 50,
        # }
        records = self.get_recent_records(9999, sleep_type=SleepType.NIGHT)
        achievements: list[SleepAchievement] = getattr(self.tracker, "achievements", [])
        unlocked_count = sum(1 for a in achievements if any(a.fulfilled_by(r) for r in records))
        streak_days = self._estimate_streak_days()
        points = unlocked_count * 50
        return {
            "unlocked_count": unlocked_count, 
            "streak_days": streak_days, 
            "points": points, 
        }

    def get_map_dashboard(self) -> dict[str, Any]:
        count = len(self.get_recent_records(9999))
        unlocked = min(4, 1 + count // 2) if count else 0
        return {
            "unlocked_count": unlocked,
            "total_count": 4,
            "recommended_node": "图书馆" if unlocked >= 2 else "西门",
        }
    
    def upload_timetable(self, file_path: str) -> bool:
        """
        解析学校选课网导出的标准 Excel 课表（已支持旧版 .xls 并且强行剥离周六日）
        """
        try:
            # 1. 自动根据后缀选择引擎读取 xls / xlsx
            if file_path.endswith('.xls'):
                df = pd.read_excel(file_path, sheet_name=0, engine='xlrd')
            else:
                df = pd.read_excel(file_path, sheet_name=0)
            
            # 2. 清洗列名，去掉前后空格
            df.columns = [str(c).strip() for c in df.columns]
            
            # 清洗
            rename_dict = {
                "星期一": "周一", "星期二": "周二", "星期三": "周三", 
                "星期四": "周四", "星期五": "周五", "星期六": "周六", "星期日": "周日"
            }
            df.rename(columns=rename_dict, inplace=True)
            
            # 4. 只保留周一 ~ 周五
            keep_columns = ["节数", "周一", "周二", "周三", "周四", "周五"]
            # 过滤出表格中实际存在的有效工作日列，防闪退
            final_columns = [col for col in keep_columns if col in df.columns]
            df = df[final_columns]
            
            self.current_timetable_df = df
            self.has_planned = False  # 上传新课表，重置规划状态
            return True
            
        except Exception as e:
            print(f"解析课表 Excel 失败: {e}")
            return False

    def _parse_cell_content(self, cell_value: Any) -> dict[str, str] | None:
        """
        专门处理两块内容间无空格、中英括号混杂的紧凑文本。
        """
        if pd.isna(cell_value) or str(cell_value).strip() == "":
            return None
            
        raw_text = str(cell_value).strip()
        
        if '(' not in raw_text:
            return None
            
        try:
            # 1. 切出课程名称
            course_name = raw_text.split('(', 1)[0].strip()
            
            # 2. 剥离并切出上课地点
            right_part = raw_text.split('(', 1)[1]
            
            if ')(' in right_part:
                location = right_part.split(')(', 1)[0].strip()
            else:
                location = right_part.split(')', 1)[0].strip()
                
            if not course_name:
                return None
                
            return {
                "name": course_name,
                "location": location if location else "暂无上课教室数据"
            }
            
        except Exception as e:
            print(f"⚠️ 解析单元格时遇到异常跳过: {e}")
            return None

    def calculate_planning(self) -> dict[str, Any]:
        """
        智能规划算法
        """
        if self.current_timetable_df is None:
            return {}

        df = self.current_timetable_df
        
        # 1. 获取睡眠目标基准
        goal = None
        # 尝试通过 goal_manager 获取
        if hasattr(self.tracker, 'goal_manager') and self.tracker.goal_manager:
            goal = self.tracker.goal_manager.sleep_goal
        # 如果 manager 里没有，且 repository 存在，尝试从仓库加载
        if not goal and hasattr(self.tracker, 'repository') and self.tracker.repository:
            try:
                goal = self.tracker.repository.load_current_goal()
            except Exception as e:
                print(f"⚠️  从 repository 加载目标失败: {e}")
        if goal:
            target_hours = (goal.target_duration_minutes / 60.0)
            expected_start = goal.expected_sleep_start_time
        else:
            target_hours = 8.0
            expected_start = datetime.strptime("23:30", "%H:%M")

        # 2. 工作日早八判定 (周一到周五第 0 行)
        has_early_eight = False
        work_days = ["周一", "周二", "周三", "周四", "周五"]
        available_work_days = [day for day in work_days if day in df.columns]
        
        for day in available_work_days:
            if len(df) > 0:
                cell_data = df.at[0, day]
                if self._parse_cell_content(cell_data):
                    has_early_eight = True
                    break

        # 3. 规划夜间睡眠
        if has_early_eight:
            wake_time = datetime.strptime("07:00", "%H:%M")
            sleep_time = wake_time - timedelta(hours=target_hours)
        else:
            sleep_time = expected_start
            wake_time = sleep_time + timedelta(hours=target_hours)

        night_sleep_str = f"{sleep_time.strftime('%H:%M')} - {wake_time.strftime('%H:%M')}"

        # 4. 判定午休星期与上课地点收集（仅在周一到周五内闭环计算）
        recommend_nap_days = []
        unique_places = set()
        
        for day in available_work_days:
            # 检查第 4 节（Index 3）和第 5 节（Index 4）
            has_class_4 = self._parse_cell_content(df.at[3, day]) is not None if len(df) > 3 else False
            has_class_5 = self._parse_cell_content(df.at[4, day]) is not None if len(df) > 4 else False
            
            if not has_class_4 and not has_class_5:
                recommend_nap_days.append(day)
            
            # 遍历全天 12 节课，收集有效的上课地点
            for row_idx in range(len(df)):
                course = self._parse_cell_content(df.at[row_idx, day])
                if course:
                    loc = course["location"]
                    if loc and "暂无" not in loc and "数据" not in loc and "II" not in loc:
                        unique_places.add(loc)

        # 5. 组装最终建议
        nap_str = "/".join(recommend_nap_days) + " 13:00-13:30" if recommend_nap_days else "本周无合适午休空档"
        places_str = "、".join(list(unique_places)) if unique_places else "宿舍"

        self.has_planned = True

        return {
            "night_sleep": night_sleep_str,
            "nap": nap_str,
            "places": places_str,
        }
    
        
    def get_planning_dashboard(self) -> dict[str, Any]:
        if self.has_planned:
            return self.calculate_planning()
        return {
            "night_sleep": "请点击一键规划获取建议",
            "nap": "请点击一键规划获取建议",
            "places": "--",
        }

    def _estimate_streak_days(self) -> int:
        records = self.get_recent_records(9999)
        return min(7, sum(1 for record in records if self._duration_hours(record) >= 7.0))

    def _finish_sleep_with_ui_fallback(self) -> SleepRecord | None:
        session = getattr(self.tracker, "active_session", None)
        if session is None:
            return None

        ended_at = datetime.now()
        kwargs = {
            "record_id": uuid4().hex,
            "user_id": session.user_id,
            "started_at": session.started_at,
            "ended_at": ended_at,
            "expected_duration_minutes": session.expected_duration_minutes,
            "sleep_type": session.sleep_type,
            "environment": session.environment,
            "interruptions": tuple(session.interruptions),
        }
        try:
            record = SleepRecord(expected_start_time=session.started_at, **kwargs)
        except TypeError:
            record = SleepRecord(**kwargs)

        self._fallback_records.append(record)
        sleep_manager = getattr(self.tracker, "sleep_manager", None)
        if sleep_manager is not None:
            sleep_manager.current_state = None
            sleep_manager.active_session = None
        return record

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        minutes = (record.ended_at - record.started_at).total_seconds() / 60
        return round(minutes / 60, 1)

    @staticmethod
    def _average_time_text(values: list[datetime]) -> str:
        if not values:
            return "--:--"
        minutes = [value.hour * 60 + value.minute for value in values]
        avg = round(sum(minutes) / len(minutes))
        return f"{avg // 60 % 24:02d}:{avg % 60:02d}"

    @staticmethod
    def _safe_call(callback: object, default: Any) -> Any:
        try:
            return callback()  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            return default
