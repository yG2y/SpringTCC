from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .util import git_commit, utc_now_iso


def attrition_value(attrition: Sequence[Dict[str, Any]], stage: str, field: str) -> str:
    for row in attrition:
        if row["stage"] == stage:
            return str(row[field])
    return "n/a"


def write_run_metadata(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_run_metadata(
    config: Dict[str, Any],
    *,
    started_at: str,
    finished_at: str,
    target_n: int,
    count_info: Optional[Dict[str, Any]],
    collected_unique: int,
    eligible_count: int,
    selected_count: int,
    cutoff_date: str,
    ordering: Sequence[Dict[str, str]],
    command: str,
) -> Dict[str, Any]:
    discovery = config.get("discovery") or {}
    return {
        "collection_started_at": started_at,
        "collection_finished_at": finished_at,
        "collection_date": started_at[:10],
        "query": discovery.get("query"),
        "include_forks_in_search": discovery.get("include_forks_in_search"),
        "filters": config.get("exclude"),
        "activity": config.get("activity"),
        "cutoff_date": cutoff_date,
        "sorting": [f"{rule['field']} {rule['direction']}" for rule in ordering],
        "target_n": target_n,
        "github_api_version": discovery.get("api_version"),
        "git_commit": git_commit(),
        "command": command,
        "api_total_count": None if not count_info else count_info.get("total_count"),
        "collected_unique_count": collected_unique,
        "eligible_count": eligible_count,
        "selected_count": selected_count,
        "count_snapshot": count_info,
    }


def write_report(
    path: Path,
    *,
    collection_date: str,
    attrition: List[Dict[str, Any]],
    ordering: Sequence[Dict[str, str]],
    target_n: int,
    selected_count: int,
    eligible_count: int,
) -> None:
    lines = [
        "SPRING BOOT REPOSITORY SELECTION",
        "================================",
        "",
        f"Collection date: {collection_date}",
        "",
        f"Initial population:       {attrition_value(attrition, 'universe', 'input_count')}",
        f"After fork removal:       {attrition_value(attrition, 'remove_forks', 'output_count')}",
        f"After mirror removal:     {attrition_value(attrition, 'remove_mirrors', 'output_count')}",
        f"After archived removal:   {attrition_value(attrition, 'remove_archived', 'output_count')}",
        f"After disabled removal:   {attrition_value(attrition, 'remove_disabled', 'output_count')}",
        f"After activity filter:    {attrition_value(attrition, 'remove_inactive', 'output_count')}",
        f"After template removal:   {attrition_value(attrition, 'remove_templates', 'output_count')}",
        f"After empty removal:      {attrition_value(attrition, 'remove_empty', 'output_count')}",
        f"After non-software:       {attrition_value(attrition, 'remove_non_software', 'output_count')}",
        "",
        f"Eligible repositories:    {eligible_count}",
        "",
        "Ordering:",
    ]
    for index, rule in enumerate(ordering, 1):
        lines.append(f"{index}. {rule['field']} {rule['direction'].upper()}")
    lines.extend(
        [
            "",
            f"Requested sample:          {target_n}",
            f"Final selected:            {selected_count}",
        ]
    )
    if eligible_count < target_n:
        lines.extend(
            [
                "",
                "NOTE: eligible_count < target_n. Filters were NOT relaxed.",
                f"Requested: {target_n}",
                f"Eligible: {eligible_count}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path.read_text(encoding="utf-8"), flush=True)
