from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pkusleeper.domain.sleep import SleepRecord


@dataclass(slots=True)
class Node:
    node_id: str
    name: str
    description: str
    demands: dict[str, Any]

    def unlocked_by(self, record: SleepRecord) -> bool:
        """判断该记录是否满足地图节点解锁条件。"""
        min_hours = self.demands.get("min_duration_hours")
        if min_hours is not None:
            duration_hours = (record.ended_at - record.started_at).total_seconds() / 3600
            if duration_hours < min_hours:
                return False

        return True
