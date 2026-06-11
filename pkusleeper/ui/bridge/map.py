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


class MapBridgeMixin:
    def get_map_dashboard(self) -> dict[str, Any]:
        count = len(self.get_recent_records(9999))
        auto_unlocked = min(len(self.MAP_NODES), 1 + count // 2) if count else 0
        dev_map = self._load_developer_state().get("map", {})
        manual_nodes = set(dev_map.get("unlocked_node_ids", []) or [])
        total_count = int(dev_map.get("total_count") or len(self.MAP_NODES))
        total_count = max(total_count, len(self.MAP_NODES), 1)

        if dev_map.get("unlocked_count") is None:
            unlocked_count = auto_unlocked
        else:
            unlocked_count = int(dev_map.get("unlocked_count") or 0)
        unlocked_count = max(0, min(unlocked_count, len(self.MAP_NODES)))

        unlocked_ids = {
            node["node_id"]
            for node in self.MAP_NODES[:unlocked_count]
        }
        unlocked_ids.update(
            node["node_id"]
            for node in self.MAP_NODES
            if node["node_id"] in manual_nodes or node["name"] in manual_nodes
        )

        recommended_node = dev_map.get("recommended_node") or ""
        if not recommended_node:
            next_node = next(
                (node for node in self.MAP_NODES if node["node_id"] not in unlocked_ids),
                self.MAP_NODES[-1],
            )
            recommended_node = next_node["name"]

        nodes = []
        for node in self.MAP_NODES:
            is_recommended = recommended_node in (node["node_id"], node["name"])
            nodes.append(
                {
                    **node,
                    "unlocked": node["node_id"] in unlocked_ids,
                    "recommended": is_recommended,
                }
            )

        recommended_info = next(
            (node for node in nodes if node["recommended"]),
            nodes[-1],
        )

        return {
            "unlocked_count": min(max(unlocked_count, len(unlocked_ids)), total_count),
            "total_count": total_count,
            "recommended_node": recommended_info["name"],
            "recommended_condition": recommended_info["condition"],
            "nodes": nodes,
        }
