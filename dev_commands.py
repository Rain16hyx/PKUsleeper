"""PKUSleeper 开发者调试命令。

示例：
    python dev_commands.py records add --start "2026-06-01 23:30" --end "2026-06-02 07:30"
    python dev_commands.py records list
    python dev_commands.py goal set --hours 7.5 --start 23:45
    python dev_commands.py achievement unlock sleep_8h
    python dev_commands.py map set --unlocked-count 3 --recommended-node 图书馆
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from models import SleepEnvironment, SleepGoal, SleepRecord, SleepType
from storage import SleepRecordRepository
from utils.data_processing import SleepReportBuilder


KNOWN_ACHIEVEMENTS = {
    "first_sleep": "初入梦乡",
    "sleep_8h": "睡眠达人",
    "early_sleep": "早睡早起",
    "nap_master": "午休大师",
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = SleepRecordRepository(args.user_id, args.data_dir)
    args.func(repo, args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PKUSleeper 开发者调试命令",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--user-id", default="default_user", help="目标用户 ID，默认 default_user")
    parser.add_argument("--data-dir", default=Path(__file__).parent / "data", type=Path, help="数据目录")

    subparsers = parser.add_subparsers(dest="domain", required=True)
    add_record_commands(subparsers)
    add_goal_commands(subparsers)
    add_achievement_commands(subparsers)
    add_map_commands(subparsers)
    add_state_commands(subparsers)
    return parser


def add_record_commands(subparsers) -> None:
    records = subparsers.add_parser("records", help="手动设置、编辑、清除睡眠记录")
    record_sub = records.add_subparsers(dest="action", required=True)

    list_parser = record_sub.add_parser("list", help="列出睡眠记录")
    list_parser.add_argument("--limit", type=int, default=None)
    list_parser.set_defaults(func=cmd_records_list)

    add_parser = record_sub.add_parser("add", help="添加一条睡眠记录")
    add_record_fields(add_parser, require_times=True)
    add_parser.add_argument("--id", dest="record_id", default=None, help="指定 record_id")
    add_parser.set_defaults(func=cmd_records_add)

    edit_parser = record_sub.add_parser("edit", help="编辑一条睡眠记录")
    edit_parser.add_argument("record_id")
    add_record_fields(edit_parser, require_times=False)
    edit_parser.set_defaults(func=cmd_records_edit)

    delete_parser = record_sub.add_parser("delete", help="删除一条睡眠记录")
    delete_parser.add_argument("record_id")
    delete_parser.set_defaults(func=cmd_records_delete)

    clear_parser = record_sub.add_parser("clear", help="清空当前用户全部睡眠记录")
    clear_parser.add_argument("--yes", action="store_true", help="确认执行清空")
    clear_parser.set_defaults(func=cmd_records_clear)


def add_goal_commands(subparsers) -> None:
    goal = subparsers.add_parser("goal", help="查看或修改睡眠目标")
    goal_sub = goal.add_subparsers(dest="action", required=True)

    show_parser = goal_sub.add_parser("show", help="显示当前目标")
    show_parser.set_defaults(func=cmd_goal_show)

    set_parser = goal_sub.add_parser("set", help="设置当前目标")
    set_parser.add_argument("--hours", type=float, required=True, help="目标睡眠时长，单位小时")
    set_parser.add_argument("--start", required=True, help="目标入睡时间，格式 HH:MM")
    set_parser.add_argument("--difficulty", type=int, default=1)
    set_parser.set_defaults(func=cmd_goal_set)

    reset_parser = goal_sub.add_parser("reset", help="重置为默认目标")
    reset_parser.set_defaults(func=cmd_goal_reset)


def add_achievement_commands(subparsers) -> None:
    achievement = subparsers.add_parser("achievement", help="修改成就调试状态")
    achievement_sub = achievement.add_subparsers(dest="action", required=True)

    list_parser = achievement_sub.add_parser("list", help="列出成就调试状态")
    list_parser.set_defaults(func=cmd_achievement_list)

    unlock_parser = achievement_sub.add_parser("unlock", help="手动点亮成就")
    unlock_parser.add_argument("achievement_id")
    unlock_parser.set_defaults(func=cmd_achievement_unlock)

    lock_parser = achievement_sub.add_parser("lock", help="手动锁定成就")
    lock_parser.add_argument("achievement_id")
    lock_parser.set_defaults(func=cmd_achievement_lock)

    clear_parser = achievement_sub.add_parser("clear", help="清除成就手动覆盖")
    clear_parser.set_defaults(func=cmd_achievement_clear)


def add_map_commands(subparsers) -> None:
    map_parser = subparsers.add_parser("map", help="修改地图调试状态")
    map_sub = map_parser.add_subparsers(dest="action", required=True)

    show_parser = map_sub.add_parser("show", help="显示地图调试状态")
    show_parser.set_defaults(func=cmd_map_show)

    set_parser = map_sub.add_parser("set", help="设置地图状态")
    set_parser.add_argument("--unlocked-count", type=int, default=None)
    set_parser.add_argument("--total-count", type=int, default=None)
    set_parser.add_argument("--recommended-node", default=None)
    set_parser.set_defaults(func=cmd_map_set)

    unlock_parser = map_sub.add_parser("unlock-node", help="手动解锁地图节点")
    unlock_parser.add_argument("node_id")
    unlock_parser.set_defaults(func=cmd_map_unlock_node)

    lock_parser = map_sub.add_parser("lock-node", help="手动锁定地图节点")
    lock_parser.add_argument("node_id")
    lock_parser.set_defaults(func=cmd_map_lock_node)

    clear_parser = map_sub.add_parser("clear", help="清除地图手动状态")
    clear_parser.set_defaults(func=cmd_map_clear)


def add_state_commands(subparsers) -> None:
    state = subparsers.add_parser("state", help="查看或清除所有开发者状态")
    state_sub = state.add_subparsers(dest="action", required=True)

    show_parser = state_sub.add_parser("show", help="显示 dev_state.json")
    show_parser.set_defaults(func=cmd_state_show)

    reset_parser = state_sub.add_parser("reset", help="删除 dev_state.json")
    reset_parser.set_defaults(func=cmd_state_reset)


def add_record_fields(parser: argparse.ArgumentParser, require_times: bool) -> None:
    parser.add_argument("--start", required=require_times, help="开始时间，如 2026-06-01 23:30")
    parser.add_argument("--end", required=require_times, help="结束时间，如 2026-06-02 07:30")
    parser.add_argument("--type", choices=[item.value for item in SleepType], default=None)
    parser.add_argument("--env", choices=[item.value for item in SleepEnvironment], default=None)
    parser.add_argument("--expected-minutes", type=int, default=None)
    parser.add_argument("--expected-start", default=None, help="目标入睡时间，HH:MM 或完整日期时间")


def cmd_records_list(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    records = list(reversed(repo.user_list(args.user_id)))
    if args.limit is not None:
        records = records[: args.limit]

    if not records:
        print("暂无睡眠记录。")
        return

    grader = SleepReportBuilder()
    for record in records:
        duration = (record.ended_at - record.started_at).total_seconds() / 3600
        score = round(grader.calculate_sleep_quality(record))
        print(
            f"{record.record_id} | {record.sleep_type.value} | "
            f"{record.started_at:%Y-%m-%d %H:%M} -> {record.ended_at:%Y-%m-%d %H:%M} | "
            f"{duration:.1f}h | {score}分 | {record.environment.value}"
        )


def cmd_records_add(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    record = build_record_from_args(repo, args)
    repo.save(record)
    print(f"已添加睡眠记录：{record.record_id}")


def cmd_records_edit(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    old_record = repo.get_by_id(args.record_id)
    if old_record is None:
        raise SystemExit(f"找不到记录：{args.record_id}")

    updates: dict[str, Any] = {}
    if args.start:
        updates["started_at"] = parse_datetime(args.start)
    if args.end:
        updates["ended_at"] = parse_datetime(args.end)
    if args.type:
        updates["sleep_type"] = SleepType(args.type)
    if args.env:
        updates["environment"] = SleepEnvironment(args.env)
    if args.expected_minutes is not None:
        updates["expected_duration_minutes"] = args.expected_minutes
    if args.expected_start:
        updates["expected_start_time"] = parse_expected_start(args.expected_start)

    new_record = replace(old_record, **updates)
    validate_record_time(new_record.started_at, new_record.ended_at)
    repo.save(new_record)
    print(f"已更新睡眠记录：{new_record.record_id}")


def cmd_records_delete(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    if repo.get_by_id(args.record_id) is None:
        raise SystemExit(f"找不到记录：{args.record_id}")
    repo.delete(args.record_id)
    print(f"已删除睡眠记录：{args.record_id}")


def cmd_records_clear(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    if not args.yes:
        raise SystemExit("清空记录需要显式添加 --yes")
    count = repo.clear_records()
    print(f"已清空 {count} 条睡眠记录。")


def cmd_goal_show(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    goal = repo.load_current_goal()
    print(
        f"目标时长：{goal.target_duration_minutes / 60:.1f} 小时 | "
        f"目标入睡：{goal.expected_sleep_start_time:%H:%M} | "
        f"难度：{goal.difficulty_level}"
    )


def cmd_goal_set(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    goal = SleepGoal(
        target_value=args.hours,
        target_duration_minutes=int(args.hours * 60),
        expected_sleep_start_time=parse_time(args.start),
        difficulty_level=args.difficulty,
    )
    repo.save_current_goal(goal)
    print("睡眠目标已更新。")


def cmd_goal_reset(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    repo.save_current_goal(
        SleepGoal(
            target_value=8.0,
            target_duration_minutes=480,
            expected_sleep_start_time=parse_time("23:30"),
            difficulty_level=1,
        )
    )
    print("睡眠目标已重置为 8.0 小时 / 23:30。")


def cmd_achievement_list(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()["achievement"]
    unlocked = set(state["unlocked_ids"])
    locked = set(state["locked_ids"])
    for achievement_id, name in KNOWN_ACHIEVEMENTS.items():
        if achievement_id in locked:
            status = "手动锁定"
        elif achievement_id in unlocked:
            status = "手动解锁"
        else:
            status = "自动判定"
        print(f"{achievement_id:16} {status:8} {name}")


def cmd_achievement_unlock(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    achievement = state["achievement"]
    add_unique(achievement["unlocked_ids"], args.achievement_id)
    remove_value(achievement["locked_ids"], args.achievement_id)
    repo.save_developer_state(state)
    print(f"已手动解锁成就：{args.achievement_id}")


def cmd_achievement_lock(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    achievement = state["achievement"]
    add_unique(achievement["locked_ids"], args.achievement_id)
    remove_value(achievement["unlocked_ids"], args.achievement_id)
    repo.save_developer_state(state)
    print(f"已手动锁定成就：{args.achievement_id}")


def cmd_achievement_clear(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    state["achievement"] = {"unlocked_ids": [], "locked_ids": []}
    repo.save_developer_state(state)
    print("已清除成就手动覆盖。")


def cmd_map_show(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    map_state = repo.load_developer_state()["map"]
    print(f"已解锁节点：{map_state['unlocked_node_ids']}")
    print(f"解锁数量覆盖：{map_state['unlocked_count']}")
    print(f"总节点数：{map_state['total_count']}")
    print(f"推荐节点：{map_state['recommended_node']}")


def cmd_map_set(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    map_state = state["map"]
    if args.unlocked_count is not None:
        map_state["unlocked_count"] = args.unlocked_count
    if args.total_count is not None:
        map_state["total_count"] = args.total_count
    if args.recommended_node is not None:
        map_state["recommended_node"] = args.recommended_node
    repo.save_developer_state(state)
    print("地图状态已更新。")


def cmd_map_unlock_node(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    add_unique(state["map"]["unlocked_node_ids"], args.node_id)
    repo.save_developer_state(state)
    print(f"已手动解锁地图节点：{args.node_id}")


def cmd_map_lock_node(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    remove_value(state["map"]["unlocked_node_ids"], args.node_id)
    repo.save_developer_state(state)
    print(f"已手动锁定地图节点：{args.node_id}")


def cmd_map_clear(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    state = repo.load_developer_state()
    state["map"] = {
        "unlocked_node_ids": [],
        "unlocked_count": None,
        "total_count": 4,
        "recommended_node": None,
    }
    repo.save_developer_state(state)
    print("已清除地图手动状态。")


def cmd_state_show(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    print_json(repo.load_developer_state())


def cmd_state_reset(repo: SleepRecordRepository, args: argparse.Namespace) -> None:
    repo.reset_developer_state()
    print("已删除开发者状态文件。")


def build_record_from_args(repo: SleepRecordRepository, args: argparse.Namespace) -> SleepRecord:
    started_at = parse_datetime(args.start)
    ended_at = parse_datetime(args.end)
    validate_record_time(started_at, ended_at)

    sleep_type = SleepType(args.type) if args.type else SleepType.NIGHT
    environment = SleepEnvironment(args.env) if args.env else SleepEnvironment.DORMITORY
    goal = repo.load_current_goal()
    expected_minutes = args.expected_minutes
    if expected_minutes is None:
        expected_minutes = 30 if sleep_type == SleepType.NAP else goal.target_duration_minutes

    expected_start = (
        parse_expected_start(args.expected_start)
        if args.expected_start
        else goal.expected_sleep_start_time
    )

    return SleepRecord(
        record_id=args.record_id or uuid4().hex,
        user_id=repo.user_id,
        started_at=started_at,
        ended_at=ended_at,
        expected_duration_minutes=expected_minutes,
        expected_start_time=expected_start,
        sleep_type=sleep_type,
        environment=environment,
        interruptions=(),
    )


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError as exc:
        raise SystemExit(f"无法解析时间：{value}") from exc


def parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise SystemExit(f"无法解析时间：{value}，请使用 HH:MM") from exc


def parse_expected_start(value: str) -> datetime:
    if len(value) <= 5 and ":" in value:
        return parse_time(value)
    return parse_datetime(value)


def validate_record_time(started_at: datetime, ended_at: datetime) -> None:
    if ended_at <= started_at:
        raise SystemExit("结束时间必须晚于开始时间。")


def add_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def remove_value(values: list[str], value: str) -> None:
    while value in values:
        values.remove(value)


def print_json(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    raise SystemExit(main())
