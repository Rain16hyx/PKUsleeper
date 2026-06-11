from __future__ import annotations

from typing import Any

from pkusleeper.domain import Node, SleepRecord
from pkusleeper.states import MappingState


class SleepMapManager:
    """睡眠地图节点解锁服务。"""

    def __init__(self) -> None:
        self.all_available_nodes: list[Node] = []
        self.unlocked_nodes: list[Node] = []

    def as_state(self) -> MappingState:
        return MappingState(self.all_available_nodes, self.unlocked_nodes)

    def load_map_nodes(self) -> dict[str, Any]:
        return self.as_state().load_map_nodes()

    def evaluate(self, record: SleepRecord | None) -> list[Node]:
        return self.as_state().evaluate_new_unlocks(record)

    def update(self, newly_unlocked: list[Node]) -> None:
        for node in newly_unlocked:
            if node not in self.unlocked_nodes:
                self.unlocked_nodes.append(node)

    def view_node_details(self, node_id: str) -> dict[str, Any]:
        return self.as_state().view_node_details(node_id)
