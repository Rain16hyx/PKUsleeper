from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

import pandas as pd

from pkusleeper.domain import SleepAchievement, SleepEnvironment, SleepRecord, SleepType
from pkusleeper.reports import SleepReportBuilder
from pkusleeper.ui.bridge.result import ActionResult


class PlanningBridgeMixin:
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
