"""睡眠数据存储模块"""

from __future__ import annotations
from pathlib import Path
from models import *
import json
from dataclasses import asdict 
from datetime import datetime



class SleepRecordRepository:
    """睡眠数据管理器"""

    def __init__(self, user_id: str, data_dir: Path | str) -> None:
        self.user_id = user_id
        self.data_dir = Path(data_dir)/user_id
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_file_path(self, record_id: str) -> Path:
        """根据睡眠记录ID获取对应的数据文件路径"""
        return self.data_dir / f"record_{record_id}.json"
    
    def save(self, record: SleepRecord) -> None:
        """保存睡眠数据到数据文件夹"""
        file_path = self.get_file_path(record.record_id)
        record_dict = asdict(record)
        #起止时间、期望入睡时间、睡眠类型、环境
        record_dict["started_at"] = record.started_at.isoformat() if record.started_at else None
        record_dict["ended_at"] = record.ended_at.isoformat() if record.ended_at else None
        record_dict["expected_start_time"] = record.expected_start_time.isoformat() if record.expected_start_time else None
        record_dict["sleep_type"] = record.sleep_type.value
        record_dict["environment"] = record.environment.value
        #中断
        if "interruptions" in record_dict:
            for item in record_dict['interruptions']:
                if item['started_at'] and isinstance(item['started_at'], datetime):
                    item['started_at'] = item['started_at'].isoformat()
                if item.get('ended_at') and isinstance(item['ended_at'], datetime):
                    item['ended_at'] = item['ended_at'].isoformat()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record_dict, f, ensure_ascii=False, indent=4)


    def get_by_id(self, record_id: str) -> SleepRecord | None:
        """从数据文件夹读取指定睡眠记录"""
        file_path=self.get_file_path(record_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path,"r",encoding="utf-8") as f:
                data=json.load(f)
        except json.JSONDecodeError:
            return None
        
        #还原时间
        data["started_at"] = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        data["ended_at"] = datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None
        data["expected_start_time"] = datetime.fromisoformat(data["expected_start_time"]) if data.get("expected_start_time") else None
        #还原中断数据
        if "interruptions" in data:
            restored_interruptions = []
            for item in data["interruptions"]:
                # 将字符串解析回 datetime
                item["started_at"] = datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None
                if item.get("ended_at"):
                    item["ended_at"] = datetime.fromisoformat(item["ended_at"])
                else:
                    item["ended_at"] = None
                # 核心：利用解包（**item）将字典重新变成 SleepInterruption 对象
                interruption_obj = SleepInterruption(**item)
                restored_interruptions.append(interruption_obj)
    
            data["interruptions"] = tuple(restored_interruptions)

        #还原睡眠类型、环境
        data["sleep_type"] = SleepType(data["sleep_type"])
        data["environment"] = SleepEnvironment(data["environment"])
        return SleepRecord(**data)

    #注意：可能包含不完整的睡眠数据！   
    def user_list(self, user_id: str) -> list[SleepRecord]:
        """从数据文件夹读取指定用户的所有睡眠记录"""
        records = []
        for file_path in self.data_dir.glob("record_*.json"):
            try:
                record_id=file_path.stem.replace("record_","")
                record = self.get_by_id(record_id)
                if record:
                    records.append(record)
            except Exception:
                continue
                    
        # 按入睡时间从早到晚排序
        records.sort(key=lambda x: x.started_at if x.started_at else datetime.min)
        return records 

    def delete(self, record_id: str) -> None:
        """从数据文件夹删除指定睡眠记录"""
        file_path = self.get_file_path(record_id)
        if file_path.exists():
            file_path.unlink() 