from __future__ import annotations

from typing import Any

from pkusleeper.domain import SleepEnvironment, SleepRecord, SleepType


class MapBridgeMixin:
    MAP_REQUIREMENTS = {
        "required_records": ("record_count", "累计记录", "条"),
        "night_records": ("night_count", "夜间睡眠", "次"),
        "nap_records": ("nap_count", "午休记录", "次"),
        "long_nights": ("long_night_count", "7小时以上夜间睡眠", "次"),
        "dorm_nights": ("dorm_night_count", "宿舍夜间睡眠", "次"),
        "goal_days": ("goal_day_count", "完成睡眠目标", "天"),
        "streak_days": ("streak_days", "连续达标", "天"),
        "min_total_hours": ("total_hours", "累计睡眠", "小时"),
    }

    def get_map_dashboard(self) -> dict[str, Any]:
        records = self.get_recent_records(9999)
        stats = self._build_map_stats(records)
        dev_map = self._load_developer_state().get("map", {})
        manual_nodes = set(dev_map.get("unlocked_node_ids", []) or [])
        total_count = int(dev_map.get("total_count") or len(self.MAP_NODES))
        total_count = max(total_count, len(self.MAP_NODES), 1)

        if dev_map.get("unlocked_count") is None:
            auto_unlocked_ids = self._auto_unlocked_map_nodes(stats)
        else:
            unlocked_count = int(dev_map.get("unlocked_count") or 0)
            unlocked_count = max(0, min(unlocked_count, len(self.MAP_NODES)))
            auto_unlocked_ids = {
                node["node_id"]
                for node in self.MAP_NODES[:unlocked_count]
            }

        unlocked_ids = set(auto_unlocked_ids)
        unlocked_ids.update(
            node["node_id"]
            for node in self.MAP_NODES
            if (
                node["node_id"] in manual_nodes
                or node["name"] in manual_nodes
                or node.get("short_name") in manual_nodes
            )
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
            is_recommended = recommended_node in (
                node["node_id"],
                node["name"],
                node.get("short_name"),
            )
            nodes.append(
                {
                    **node,
                    "condition": self._map_condition_text(node),
                    "progress": self._map_progress_text(node, stats),
                    "intro": node.get("intro", "介绍待补充。"),
                    "unlocked": node["node_id"] in unlocked_ids,
                    "recommended": is_recommended,
                }
            )

        recommended_info = next(
            (node for node in nodes if node["recommended"]),
            nodes[-1],
        )

        return {
            "unlocked_count": min(len(unlocked_ids), total_count),
            "total_count": total_count,
            "recommended_node": recommended_info["name"],
            "recommended_condition": recommended_info["condition"],
            "nodes": nodes,
        }


    def _auto_unlocked_map_nodes(self, stats: dict[str, float]) -> set[str]:
        unlocked_ids: set[str] = set()
        for node in self.MAP_NODES:
            if not self._map_node_requirements_met(node, stats):
                break
            unlocked_ids.add(str(node["node_id"]))
        return unlocked_ids


    def _build_map_stats(self, records: list[SleepRecord]) -> dict[str, float]:
        goal = self._load_goal()
        night_records = [record for record in records if record.sleep_type == SleepType.NIGHT]
        nap_records = [record for record in records if record.sleep_type == SleepType.NAP]

        long_nights = [
            record
            for record in night_records
            if self._duration_hours(record) >= 7.0
        ]
        dorm_nights = [
            record
            for record in night_records
            if record.environment == SleepEnvironment.DORMITORY
        ]

        goal_days = set()
        for record in night_records:
            target_minutes = record.expected_duration_minutes or goal.target_duration_minutes
            if self._duration_hours(record) >= target_minutes / 60:
                goal_days.add(self.record_date(record))

        return {
            "record_count": len(records),
            "night_count": len(night_records),
            "nap_count": len(nap_records),
            "long_night_count": len(long_nights),
            "dorm_night_count": len(dorm_nights),
            "goal_day_count": len(goal_days),
            "streak_days": self._estimate_streak_days(),
            "total_hours": round(sum(self._duration_hours(record) for record in records), 1),
        }


    def _map_node_requirements_met(
        self,
        node: dict[str, Any],
        stats: dict[str, float],
    ) -> bool:
        for requirement_key, target in self._map_requirements(node):
            stat_key, _label, _unit = self.MAP_REQUIREMENTS[requirement_key]
            if stats.get(stat_key, 0) < target:
                return False
        return True


    def _map_condition_text(self, node: dict[str, Any]) -> str:
        parts = []
        for requirement_key, target in self._map_requirements(node):
            _stat_key, label, unit = self.MAP_REQUIREMENTS[requirement_key]
            parts.append(f"{label} {self._format_map_number(target)} {unit}")
        return "；".join(parts)


    def _map_progress_text(
        self,
        node: dict[str, Any],
        stats: dict[str, float],
    ) -> str:
        parts = []
        for requirement_key, target in self._map_requirements(node):
            stat_key, label, unit = self.MAP_REQUIREMENTS[requirement_key]
            current = min(stats.get(stat_key, 0), float(target))
            parts.append(
                f"{label} {self._format_map_number(current)} / "
                f"{self._format_map_number(target)} {unit}"
            )
        return "，".join(parts)


    def _map_requirements(self, node: dict[str, Any]) -> list[tuple[str, float]]:
        requirements = []
        for requirement_key in self.MAP_REQUIREMENTS:
            if requirement_key in node:
                requirements.append((requirement_key, float(node[requirement_key])))
        return requirements


    @staticmethod
    def _format_map_number(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.1f}"
