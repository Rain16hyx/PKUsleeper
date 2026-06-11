from __future__ import annotations

from typing import Any

from pkusleeper.domain import Node, SleepRecord
from pkusleeper.states.base import State


class MappingState(State):
    """地图节点的展示和解锁状态。"""

    def __init__(
        self,
        all_available_nodes: list[Node] | None = None,
        unlocked_nodes: list[Node] | None = None,
    ) -> None:
        self.all_available_nodes = all_available_nodes if all_available_nodes else []
        self.unlocked_nodes = unlocked_nodes if unlocked_nodes else []

    def name(self) -> str:
        return "mapping"

    def load_map_nodes(self) -> dict[str, Any]:
        unlocked_ids = {node.node_id for node in self.unlocked_nodes}
        locked_nodes = [
            node
            for node in self.all_available_nodes
            if node.node_id not in unlocked_ids
        ]
        total_count = len(self.all_available_nodes)
        unlocked_count = len(self.unlocked_nodes)

        return {
            "total_count": total_count,
            "unlocked_count": unlocked_count,
            "unlocked_nodes": self.unlocked_nodes,
            "locked_nodes": locked_nodes,
            "completion_rate": unlocked_count / total_count if total_count else 0.0,
        }

    def evaluate_new_unlocks(self, latest_record: SleepRecord | None) -> list[Node]:
        if latest_record is None:
            return []

        unlocked_ids = {node.node_id for node in self.unlocked_nodes}
        newly_unlocked: list[Node] = []

        for node in self.all_available_nodes:
            if node.node_id in unlocked_ids:
                continue
            if node.unlocked_by(latest_record):
                newly_unlocked.append(node)

        return newly_unlocked

    def view_node_details(self, node_id: str) -> dict[str, Any]:
        target_node = next(
            (node for node in self.all_available_nodes if node.node_id == node_id),
            None,
        )
        if target_node is None:
            raise ValueError(f"Cannot find map node: {node_id}")

        is_unlocked = any(node.node_id == node_id for node in self.unlocked_nodes)
        return {
            "node": target_node,
            "is_unlocked": is_unlocked,
            "unlock_hints": target_node.demands.get("hint_text", "保持健康作息即可逐步解锁节点。"),
            "lore_description": target_node.description if is_unlocked else "",
        }

    def get_unlocked_nodes_list(self) -> list[Node]:
        return self.unlocked_nodes
