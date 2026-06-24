"""睡眠数据和调试状态的本地存储。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from pkusleeper.domain import (
    SleepEnvironment,
    SleepGoal,
    SleepInterruption,
    SleepRecord,
    SleepType,
)


class SleepRecordRepository:
    """管理单个用户的本地 JSON 数据。"""

    def __init__(self, user_id: str, data_dir: Path | str) -> None:
        self.user_id = user_id
        self.data_dir = Path(data_dir) / user_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.goal_file_path = self.data_dir / "sleep_goal.json"
        self.dev_state_file_path = self.data_dir / "dev_state.json"

    def get_file_path(self, record_id: str) -> Path:
        return self.data_dir / f"record_{record_id}.json"

    def save(self, record: SleepRecord) -> None:
        record_dict = asdict(record)
        record_dict["started_at"] = self._datetime_to_text(record.started_at)
        record_dict["ended_at"] = self._datetime_to_text(record.ended_at)
        record_dict["expected_start_time"] = self._datetime_to_text(record.expected_start_time)
        record_dict["sleep_type"] = record.sleep_type.value
        record_dict["environment"] = record.environment.value

        for item in record_dict.get("interruptions", []):
            item["started_at"] = self._datetime_to_text(item.get("started_at"))
            item["ended_at"] = self._datetime_to_text(item.get("ended_at"))

        with open(self.get_file_path(record.record_id), "w", encoding="utf-8") as f:
            json.dump(record_dict, f, ensure_ascii=False, indent=4)

    def get_by_id(self, record_id: str) -> SleepRecord | None:
        file_path = self.get_file_path(record_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return None

        data["started_at"] = self._text_to_datetime(data.get("started_at"))
        data["ended_at"] = self._text_to_datetime(data.get("ended_at"))
        data["expected_start_time"] = self._text_to_datetime(data.get("expected_start_time"))
        data["sleep_type"] = SleepType(data["sleep_type"])
        data["environment"] = SleepEnvironment(data["environment"])

        restored_interruptions = []
        for item in data.get("interruptions", []):
            item["started_at"] = self._text_to_datetime(item.get("started_at"))
            item["ended_at"] = self._text_to_datetime(item.get("ended_at"))
            restored_interruptions.append(SleepInterruption(**item))
        data["interruptions"] = tuple(restored_interruptions)

        return SleepRecord(**data)

    def user_list(self, user_id: str) -> list[SleepRecord]:
        records = []
        for file_path in self.data_dir.glob("record_*.json"):
            try:
                record_id = file_path.stem.replace("record_", "")
                record = self.get_by_id(record_id)
                if record:
                    records.append(record)
            except Exception:
                continue

        records.sort(key=lambda record: record.started_at if record.started_at else datetime.min)
        return records

    def delete(self, record_id: str) -> None:
        file_path = self.get_file_path(record_id)
        if file_path.exists():
            file_path.unlink()

    def clear_records(self) -> int:
        count = 0
        for file_path in self.data_dir.glob("record_*.json"):
            file_path.unlink()
            count += 1
        return count

    def load_current_goal(self) -> SleepGoal:
        if not self.goal_file_path.exists():
            return self._default_goal()

        try:
            with open(self.goal_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            start_time = datetime.strptime(data["expected_sleep_start_time"], "%H:%M")
            return SleepGoal(
                target_value=data.get("target_value", 8.0),
                target_duration_minutes=data.get("target_duration_minutes", 480),
                expected_sleep_start_time=start_time,
                difficulty_level=data.get("difficulty_level", 1),
                nap_target_minutes=data.get("nap_target_minutes", 30),
            )
        except Exception as exc:
            print(f"用户 {self.user_id} 读取当前睡眠目标失败，降级使用默认值: {exc}")
            return self._default_goal()

    def save_current_goal(self, goal: SleepGoal) -> None:
        if not goal:
            return

        payload = {
            "target_value": goal.target_value,
            "target_duration_minutes": goal.target_duration_minutes,
            "expected_sleep_start_time": goal.expected_sleep_start_time.strftime("%H:%M")
            if goal.expected_sleep_start_time
            else "",
            "difficulty_level": goal.difficulty_level,
            "nap_target_minutes": getattr(goal, "nap_target_minutes", 30),
        }

        try:
            with open(self.goal_file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
        except Exception as exc:
            print(f"用户 {self.user_id} 持久化当前睡眠目标失败: {exc}")

    def load_developer_state(self) -> dict[str, Any]:
        state = self._default_developer_state()
        if not self.dev_state_file_path.exists():
            return state

        try:
            with open(self.dev_state_file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return state

        if isinstance(raw, dict):
            self._merge_state(state, raw)
        return state

    def save_developer_state(self, state: dict[str, Any]) -> None:
        normalized = self._default_developer_state()
        self._merge_state(normalized, state)
        with open(self.dev_state_file_path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=4)

    def reset_developer_state(self) -> None:
        if self.dev_state_file_path.exists():
            self.dev_state_file_path.unlink()

    @staticmethod
    def _default_goal() -> SleepGoal:
        return SleepGoal(
            target_value=8.0,
            target_duration_minutes=480,
            expected_sleep_start_time=datetime.strptime("23:30", "%H:%M"),
            difficulty_level=1,
        )

    @staticmethod
    def _default_developer_state() -> dict[str, Any]:
        return {
            "achievement": {
                "unlocked_ids": [],
                "locked_ids": [],
            },
            "map": {
                "unlocked_node_ids": [],
                "unlocked_count": None,
                "total_count": 8,
                "recommended_node": None,
            },
        }

    @staticmethod
    def _merge_state(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(target.get(key), dict) and isinstance(value, dict):
                target[key].update(value)
            else:
                target[key] = value

    @staticmethod
    def _datetime_to_text(value: Any) -> str | None:
        return value.isoformat() if isinstance(value, datetime) else value

    @staticmethod
    def _text_to_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None
