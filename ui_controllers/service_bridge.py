"""UI 控制器与服务层之间的安全桥接。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

import pandas as pd

from models import SleepAchievement, SleepEnvironment, SleepRecord, SleepType
from service import MainTracker
from utils.data_processing import SleepReportBuilder


@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str = ""
    payload: Any | None = None


class ServiceBridge:
    """给 UI 使用的门面，尽量屏蔽尚未完成的底层细节。"""

    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]
    ALL_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self, tracker: MainTracker) -> None:
        self.tracker = tracker
        self._fallback_records: list[SleepRecord] = []
        self.has_planned = False
        self.current_timetable_df: pd.DataFrame | None = None
        self._last_report_summary: str | None = None

    def get_home_snapshot(self) -> dict[str, Any]:
        snapshot = self._safe_call(self.tracker.get_ui_snapshot, default={})
        is_sleeping = bool(snapshot.get("is_sleeping", False))
        goal = self._load_goal()
        goal_hours = self._goal_hours(goal)

        if is_sleeping:
            current_status = "正在睡眠中"
        elif self.has_planned:
            current_status = "方案运行中"
        else:
            current_status = "就绪"

        return {
            "is_sleeping": is_sleeping,
            "today_goal_hours": goal_hours,
            "current_status": current_status,
            "streak_days": self._estimate_streak_days(),
            "record_count": len(self.get_recent_records(9999)),
        }

    def start_sleep(
        self,
        sleep_type: SleepType,
        environment: SleepEnvironment,
    ) -> ActionResult:
        try:
            goal = self._load_goal()
            expected_minutes = 30 if sleep_type == SleepType.NAP else int(goal.target_duration_minutes)
            state = self.tracker.start_sleeping(
                started_at=datetime.now(),
                expected_duration_minutes=expected_minutes,
                sleep_type=sleep_type,
                environment=environment,
            )
            state.session.metadata["expected_start_time"] = goal.expected_sleep_start_time
        except Exception as exc:  # noqa: BLE001
            return ActionResult(False, f"开始睡眠失败：{exc}")
        return ActionResult(True, "已开始记录本次睡眠")

    def finish_sleep(self) -> ActionResult:
        try:
            record = self.tracker.wake_up(datetime.now())
        except Exception as exc:  # noqa: BLE001
            fallback = self._finish_sleep_with_ui_fallback()
            if fallback is None:
                return ActionResult(False, f"结束睡眠失败：{exc}")
            record = fallback

        self._last_report_summary = self._build_single_record_report(record)
        return ActionResult(True, "本次睡眠已记录", record)

    def get_recent_records(
        self,
        days: int = 7,
        sleep_type: SleepType | None = None,
    ) -> list[SleepRecord]:
        records = self._collect_records()

        if sleep_type is not None:
            records = [r for r in records if r.sleep_type == sleep_type]

        if days < 9999:
            start_date = date.today() - timedelta(days=days - 1)
            records = [r for r in records if self.record_date(r) >= start_date]

        records.sort(key=lambda record: record.started_at, reverse=True)
        return records

    def get_records_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days)
        return {"records": records, "count": len(records), "days": days}

    def get_report_dashboard(self, days: int = 7) -> dict[str, Any]:
        records = self.get_recent_records(days, sleep_type=SleepType.NIGHT)
        goal = self._load_goal()
        threshold_hours = self._goal_hours(goal)

        if not records:
            return {
                "avg_sleep_hours": 0.0,
                "avg_sleep_time": "--:--",
                "avg_wake_time": "--:--",
                "goal_completion_rate": 0,
                "score": 0,
                "record_days": 0,
                "completed_days": 0,
                "summary": self._empty_summary(days),
            }

        durations = [self._duration_hours(record) for record in records]
        completed_days = sum(1 for value in durations if value >= threshold_hours)
        grader = SleepReportBuilder()
        scores = [grader.calculate_sleep_quality(r) for r in records]
        avg_score = round(sum(scores) / len(scores))

        summary = self._build_period_summary(records, durations, completed_days, days)
        return {
            "avg_sleep_hours": round(sum(durations) / len(durations), 1),
            "avg_sleep_time": self._average_time_text([r.started_at for r in records], night_start=True),
            "avg_wake_time": self._average_time_text([r.ended_at for r in records]),
            "goal_completion_rate": round(completed_days / len(records) * 100),
            "score": min(100, avg_score),
            "record_days": len(records),
            "completed_days": completed_days,
            "summary": summary,
        }

    def get_goal_dashboard(self) -> dict[str, Any]:
        goal = self._load_goal()
        target_hours = self._goal_hours(goal)
        week_start = date.today() - timedelta(days=date.today().weekday())
        weekly_completion = [False] * 7

        for record in self.get_recent_records(14, sleep_type=SleepType.NIGHT):
            record_date = self.record_date(record)
            if week_start <= record_date <= week_start + timedelta(days=6):
                expected = (record.expected_duration_minutes or goal.target_duration_minutes) / 60
                weekly_completion[record_date.weekday()] = self._duration_hours(record) >= expected

        done = sum(weekly_completion)
        return {
            "target_hours": target_hours,
            "done_days": done,
            "total_days": 7,
            "rate": round(done / 7 * 100),
            "weekly_completion": weekly_completion,
        }

    def get_achievement_dashboard(self) -> dict[str, Any]:
        achievement_lists = self.get_achievement_lists()
        unlocked_count = len(achievement_lists["unlocked"])
        return {
            "unlocked_count": unlocked_count,
            "streak_days": self._estimate_streak_days(),
            "points": unlocked_count * 50,
        }

    def get_achievement_lists(self) -> dict[str, list[SleepAchievement]]:
        records = self.get_recent_records(9999)
        manager = getattr(self.tracker, "achievement_manager", None)
        achievements: list[SleepAchievement] = getattr(manager, "all_achievements", []) if manager else []
        dev_achievement = self._load_developer_state().get("achievement", {})

        auto_unlocked = {
            achievement.achievement_id
            for achievement in achievements
            if self._achievement_fulfilled_by_records(achievement, records)
        }
        manual_unlocked = set(dev_achievement.get("unlocked_ids", []))
        manual_locked = set(dev_achievement.get("locked_ids", []))
        unlocked_ids = (auto_unlocked | manual_unlocked) - manual_locked

        unlocked = [
            achievement
            for achievement in achievements
            if achievement.achievement_id in unlocked_ids
        ]
        locked = [
            achievement
            for achievement in achievements
            if achievement.achievement_id not in unlocked_ids
        ]
        return {"unlocked": unlocked, "locked": locked}

    def _achievement_fulfilled_by_records(
        self,
        achievement: SleepAchievement,
        records: list[SleepRecord],
    ) -> bool:
        demands = achievement.demands
        aggregate_keys = {
            "min_records",
            "min_night_records",
            "min_nap_records",
            "min_goal_records",
            "min_streak_days",
            "min_unique_days",
            "min_average_duration_hours",
        }
        if not aggregate_keys.intersection(demands):
            return any(achievement.fulfilled_by(record) for record in records)

        night_records = [r for r in records if r.sleep_type == SleepType.NIGHT]
        nap_records = [r for r in records if r.sleep_type == SleepType.NAP]

        if len(records) < demands.get("min_records", 0):
            return False
        if len(night_records) < demands.get("min_night_records", 0):
            return False
        if len(nap_records) < demands.get("min_nap_records", 0):
            return False

        min_unique_days = demands.get("min_unique_days")
        if min_unique_days is not None:
            unique_days = {self.record_date(record) for record in records}
            if len(unique_days) < min_unique_days:
                return False

        min_goal_records = demands.get("min_goal_records")
        if min_goal_records is not None:
            goal_records = [
                record
                for record in records
                if self._duration_hours(record) * 60 >= (record.expected_duration_minutes or 480)
            ]
            if len(goal_records) < min_goal_records:
                return False

        min_streak_days = demands.get("min_streak_days")
        if min_streak_days is not None and self._estimate_streak_days() < min_streak_days:
            return False

        min_average = demands.get("min_average_duration_hours")
        if min_average is not None:
            if not night_records:
                return False
            average = sum(self._duration_hours(record) for record in night_records) / len(night_records)
            if average < min_average:
                return False

        return True

    def get_map_dashboard(self) -> dict[str, Any]:
        count = len(self.get_recent_records(9999))
        auto_unlocked = min(4, 1 + count // 2) if count else 0
        dev_map = self._load_developer_state().get("map", {})
        manual_nodes = dev_map.get("unlocked_node_ids", []) or []
        total_count = int(dev_map.get("total_count") or 4)
        total_count = max(total_count, len(manual_nodes), 1)

        if dev_map.get("unlocked_count") is None:
            unlocked = max(auto_unlocked, len(manual_nodes))
        else:
            unlocked = int(dev_map.get("unlocked_count") or 0)
        unlocked = max(0, min(unlocked, total_count))

        recommended_node = dev_map.get("recommended_node")
        if not recommended_node:
            recommended_node = "图书馆" if unlocked >= 2 else "西门"

        return {
            "unlocked_count": unlocked,
            "total_count": total_count,
            "recommended_node": recommended_node,
        }

    def upload_timetable(self, file_path: str) -> bool:
        try:
            suffix = Path(file_path).suffix.lower()
            if suffix == ".xls":
                df = pd.read_excel(file_path, sheet_name=0, engine="xlrd")
            else:
                df = pd.read_excel(file_path, sheet_name=0)

            df.columns = [str(c).strip() for c in df.columns]
            df = self._normalize_timetable_columns(df)
            keep_columns = ["节数", *self.WEEKDAYS]
            final_columns = [col for col in keep_columns if col in df.columns]
            self.current_timetable_df = df[final_columns] if final_columns else df
            self.has_planned = False
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"解析课表 Excel 失败：{exc}")
            return False

    def ensure_timetable(self) -> pd.DataFrame:
        """确保存在 12 节 x 5 天的课表数据，供手动编辑使用。"""
        if self.current_timetable_df is None:
            self.current_timetable_df = pd.DataFrame(
                "",
                index=range(12),
                columns=self.WEEKDAYS,
            )
            return self.current_timetable_df

        df = self.current_timetable_df.copy().reset_index(drop=True)
        for day in self.WEEKDAYS:
            if day not in df.columns:
                df[day] = ""
        while len(df) < 12:
            df.loc[len(df)] = {day: "" for day in df.columns}
        df = df.fillna("")
        self.current_timetable_df = df[[*self.WEEKDAYS]].head(12).reset_index(drop=True)
        return self.current_timetable_df

    def set_timetable_cell(self, row_index: int, day_name: str, value: str) -> None:
        if day_name not in self.WEEKDAYS or not 0 <= row_index < 12:
            raise ValueError("课表位置超出可编辑范围。")
        df = self.ensure_timetable()
        df.at[row_index, day_name] = value.strip()
        self.has_planned = False

    def _parse_cell_content(self, cell_value: Any) -> dict[str, str] | None:
        """解析选课网单元格，兼容课程名里自带括号的情况。"""
        if pd.isna(cell_value):
            return None

        raw_text = str(cell_value).strip()
        if not raw_text:
            return None

        line = next((part.strip() for part in re.split(r"[\r\n]+", raw_text) if part.strip()), "")
        if not line:
            return None

        groups = list(self._iter_parenthesized_groups(line))
        if not groups:
            return {"name": line, "location": "暂无上课地点数据"}

        location_group = None
        for group in groups:
            if self._looks_like_location(group["text"]):
                location_group = group
                break

        if location_group is None:
            first = groups[0]
            if not self._looks_like_course_suffix(first["text"]):
                location_group = first

        if location_group is None:
            return {"name": line, "location": "暂无上课地点数据"}

        name = line[: location_group["start"]].strip()
        name = re.sub(r"\s+", " ", name).strip(" -")
        return {
            "name": name or line[: location_group["start"]].strip() or "未命名课程",
            "location": location_group["text"].strip() or "暂无上课地点数据",
        }

    def calculate_planning(self) -> dict[str, Any]:
        if self.current_timetable_df is None:
            return {}

        df = self.current_timetable_df
        goal = self._load_goal()
        target_hours = self._goal_hours(goal)
        expected_start = goal.expected_sleep_start_time or datetime.strptime("23:30", "%H:%M")
        available_days = [day for day in self.WEEKDAYS if day in df.columns]

        has_early_class = any(
            len(df) > 0 and self._parse_cell_content(df.at[0, day])
            for day in available_days
        )

        if has_early_class:
            wake_time = datetime.strptime("07:00", "%H:%M")
            sleep_time = wake_time - timedelta(hours=target_hours)
        else:
            sleep_time = expected_start
            wake_time = sleep_time + timedelta(hours=target_hours)

        recommend_nap_days: list[str] = []
        unique_places: set[str] = set()

        for day in available_days:
            has_class_4 = len(df) > 3 and self._parse_cell_content(df.at[3, day]) is not None
            has_class_5 = len(df) > 4 and self._parse_cell_content(df.at[4, day]) is not None
            if not has_class_4 and not has_class_5:
                recommend_nap_days.append(day)

            for row_idx in range(len(df)):
                course = self._parse_cell_content(df.at[row_idx, day])
                if course:
                    loc = course["location"]
                    if loc and "暂无" not in loc and "数据" not in loc:
                        unique_places.add(loc)

        self.has_planned = True
        return {
            "night_sleep": f"{sleep_time:%H:%M} - {wake_time:%H:%M}",
            "nap": f"{'/'.join(recommend_nap_days)} 13:00-13:30"
            if recommend_nap_days
            else "本周暂无合适午休空档",
            "places": "、".join(sorted(unique_places)) if unique_places else "宿舍",
        }

    def get_planning_dashboard(self) -> dict[str, Any]:
        if self.has_planned:
            return self.calculate_planning()
        return {
            "night_sleep": "请点击一键规划获取建议",
            "nap": "请点击一键规划获取建议",
            "places": "--",
        }

    def _collect_records(self) -> list[SleepRecord]:
        records: list[SleepRecord] = []
        records.extend(getattr(self.tracker, "all_records", []) or [])
        records.extend(self._fallback_records)

        repository = getattr(self.tracker, "repository", None)
        if repository is not None:
            try:
                records.extend(repository.user_list(getattr(self.tracker, "user_id", "")))
            except Exception as exc:  # noqa: BLE001
                print(f"读取历史睡眠记录失败：{exc}")

        unique: dict[str, SleepRecord] = {}
        for record in records:
            if record.started_at and record.ended_at:
                unique[record.record_id] = record
        return list(unique.values())

    def _load_goal(self):
        goal = None
        goal_manager = getattr(self.tracker, "goal_manager", None)
        if goal_manager is not None:
            goal = goal_manager.sleep_goal

        if goal is None:
            repository = getattr(self.tracker, "repository", None)
            if repository is not None:
                goal = repository.load_current_goal()
                if goal_manager is not None:
                    goal_manager.sleep_goal = goal

        if goal is None:
            from models import SleepGoal

            goal = SleepGoal(
                target_value=8.0,
                target_duration_minutes=480,
                expected_sleep_start_time=datetime.strptime("23:30", "%H:%M"),
                difficulty_level=1,
            )
        return goal

    def _load_developer_state(self) -> dict[str, Any]:
        repository = getattr(self.tracker, "repository", None)
        if repository is not None and hasattr(repository, "load_developer_state"):
            return repository.load_developer_state()
        return {
            "achievement": {"unlocked_ids": [], "locked_ids": []},
            "map": {
                "unlocked_node_ids": [],
                "unlocked_count": None,
                "total_count": 4,
                "recommended_node": None,
            },
        }

    @staticmethod
    def _goal_hours(goal: Any) -> float:
        minutes = getattr(goal, "target_duration_minutes", None) or 480
        return round(minutes / 60.0, 1)

    def _build_single_record_report(self, record: SleepRecord) -> str:
        try:
            report = self.tracker.generate_sleep_report(record)
            return report.summary or ""
        except Exception:  # noqa: BLE001
            hours = self._duration_hours(record)
            return f"本次睡眠 {hours:.1f} 小时，记录已保存。"

    def _build_period_summary(
        self,
        records: list[SleepRecord],
        durations: list[float],
        completed_days: int,
        days: int,
    ) -> list[tuple[str, str]]:
        avg_duration = round(sum(durations) / len(durations), 1)
        rate = round(completed_days / len(records) * 100)

        if avg_duration >= 8:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，睡眠时长比较充足。"
        elif avg_duration >= 7:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，整体接近目标。"
        else:
            duration_text = f"平均睡眠 {avg_duration:.1f} 小时，建议优先补足夜间睡眠。"

        if rate >= 80:
            goal_text = f"本期达标率 {rate}%，目标完成情况很好。"
        elif rate >= 50:
            goal_text = f"本期达标率 {rate}%，仍有提升空间。"
        else:
            goal_text = f"本期达标率 {rate}%，可以先从固定入睡时间开始。"

        record_text = f"最近 {days} 天内有 {len(records)} 条夜间睡眠记录。"
        return [("记录覆盖", record_text), ("时长表现", duration_text), ("目标完成", goal_text)]

    @staticmethod
    def _empty_summary(days: int) -> list[tuple[str, str]]:
        return [
            ("记录覆盖", f"最近 {days} 天暂无夜间睡眠记录。"),
            ("时长表现", "完成一次睡眠打卡后即可生成趋势分析。"),
            ("目标完成", "暂无数据时，本周完成圆点保持未点亮。"),
        ]

    def _estimate_streak_days(self) -> int:
        records = self.get_recent_records(9999, sleep_type=SleepType.NIGHT)
        completed_dates = {
            self.record_date(record)
            for record in records
            if self._duration_hours(record) >= 7.0
        }
        streak = 0
        cursor = date.today()
        while cursor in completed_dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def _finish_sleep_with_ui_fallback(self) -> SleepRecord | None:
        session = getattr(self.tracker, "active_session", None)
        if session is None:
            return None

        ended_at = datetime.now()
        expected_start = session.metadata.get("expected_start_time", session.started_at)
        record = SleepRecord(
            record_id=uuid4().hex,
            user_id=session.user_id,
            started_at=session.started_at,
            ended_at=ended_at,
            expected_duration_minutes=session.expected_duration_minutes,
            expected_start_time=expected_start,
            sleep_type=session.sleep_type,
            environment=session.environment,
            interruptions=tuple(session.interruptions),
        )
        self._fallback_records.append(record)

        repository = getattr(self.tracker, "repository", None)
        if repository is not None:
            repository.save(record)

        sleep_manager = getattr(self.tracker, "sleep_manager", None)
        if sleep_manager is not None:
            sleep_manager.current_state = None
            sleep_manager.active_session = None
            sleep_manager.latest_record = record
            sleep_manager.all_records.append(record)
        return record

    @staticmethod
    def _duration_hours(record: SleepRecord) -> float:
        minutes = (record.ended_at - record.started_at).total_seconds() / 60
        return round(minutes / 60, 1)

    @staticmethod
    def record_date(record: SleepRecord) -> date:
        """夜间睡眠按醒来日期统计，避免跨午夜记录偏到前一天。"""
        if record.sleep_type == SleepType.NIGHT and record.ended_at:
            return record.ended_at.date()
        return record.started_at.date()

    @staticmethod
    def _average_time_text(values: list[datetime], night_start: bool = False) -> str:
        if not values:
            return "--:--"
        minutes = []
        for value in values:
            total = value.hour * 60 + value.minute
            if night_start and total < 12 * 60:
                total += 24 * 60
            minutes.append(total)
        avg = round(sum(minutes) / len(minutes)) % (24 * 60)
        return f"{avg // 60:02d}:{avg % 60:02d}"

    @staticmethod
    def _normalize_timetable_columns(df: pd.DataFrame) -> pd.DataFrame:
        rename_dict = {
            "节次": "节数",
            "节数": "节数",
            "星期一": "周一",
            "星期二": "周二",
            "星期三": "周三",
            "星期四": "周四",
            "星期五": "周五",
            "星期六": "周六",
            "星期日": "周日",
            "星期天": "周日",
            "周一": "周一",
            "周二": "周二",
            "周三": "周三",
            "周四": "周四",
            "周五": "周五",
            "周六": "周六",
            "周日": "周日",
        }
        return df.rename(columns={col: rename_dict.get(str(col).strip(), col) for col in df.columns})

    @staticmethod
    def _iter_parenthesized_groups(text: str):
        stack: list[tuple[str, int]] = []
        pairs = {")": "(", "）": "（"}
        for idx, char in enumerate(text):
            if char in "(（":
                stack.append((char, idx))
            elif char in ")）" and stack and stack[-1][0] == pairs[char]:
                _, start = stack.pop()
                if not stack:
                    yield {"text": text[start + 1 : idx], "start": start, "end": idx + 1}

    @staticmethod
    def _looks_like_location(text: str) -> bool:
        value = text.strip()
        if not value:
            return False
        location_words = (
            "楼",
            "馆",
            "院",
            "室",
            "厅",
            "场",
            "中心",
            "教",
            "校区",
            "实验",
            "理教",
            "二教",
            "三教",
            "四教",
            "文史",
            "地学",
            "逸夫",
        )
        return any(word in value for word in location_words) or bool(re.search(r"\d{3,4}", value))

    @staticmethod
    def _looks_like_course_suffix(text: str) -> bool:
        value = text.strip().upper()
        return bool(re.fullmatch(r"[IVXLCDM]+|[A-Z]|[A-Z]+[0-9]*", value))

    @staticmethod
    def _safe_call(callback: object, default: Any) -> Any:
        try:
            return callback()  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            return default
