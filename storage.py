"""睡眠数据存储模块"""

from __future__ import annotations

from pathlib import Path

from models import SleepRecord


class SleepRecordRepository:
    """睡眠数据管理器"""

    def __init__(self, user_id: str, data_dir: Path | str) -> None:
        self.user_id = user_id
        self.data_dir = Path(data_dir)

    def save(self, record: SleepRecord) -> None:
        """保存睡眠数据到数据文件夹"""
        raise NotImplementedError

    def get_by_id(self, record_id: str) -> SleepRecord | None:
        """从数据文件夹读取指定睡眠记录"""
        raise NotImplementedError

    def user_list(self, user_id: str) -> list[SleepRecord]:
        """从数据文件夹读取指定用户的所有睡眠记录"""
        raise NotImplementedError

    def delete(self, record_id: str) -> None:
        """从数据文件夹删除指定睡眠记录"""
        raise NotImplementedError
