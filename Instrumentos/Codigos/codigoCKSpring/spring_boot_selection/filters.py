from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .util import as_bool, as_int, minus_years, parse_iso, utc_now

ELIGIBLE_FIELDS = [
    "repository_id",
    "full_name",
    "html_url",
    "description",
    "language",
    "stargazers_count",
    "forks_count",
    "created_at",
    "pushed_at",
    "updated_at",
    "topics",
    "size_kb",
    "default_branch",
    "license",
    "is_fork",
    "is_template",
    "archived",
    "disabled",
]


def topic_list(row: Dict[str, Any]) -> List[str]:
    raw = row.get("topics") or ""
    return [part.strip().lower() for part in str(raw).split(";") if part.strip()]


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def exclusion_record(
    row: Dict[str, Any],
    stage: str,
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record = {
        "repository_id": row.get("repository_id"),
        "full_name": row.get("full_name"),
        "html_url": row.get("html_url"),
        "filter_stage": stage,
        "exclusion_reason": reason,
        "relevant_metadata": {
            "stargazers_count": row.get("stargazers_count"),
            "pushed_at": row.get("pushed_at"),
            "created_at": row.get("created_at"),
            "language": row.get("language"),
            "topics": row.get("topics"),
            "is_fork": row.get("is_fork"),
            "archived": row.get("archived"),
            "disabled": row.get("disabled"),
            "is_template": row.get("is_template"),
            "size_kb": row.get("size_kb"),
            "default_branch": row.get("default_branch"),
            "mirror_url": row.get("mirror_url"),
        },
    }
    if extra:
        record["relevant_metadata"].update(extra)
        record.update({key: value for key, value in extra.items() if key in {"primary_reason", "all_reasons"}})
    return record


def apply_predicate(
    rows: List[Dict[str, Any]],
    stage: str,
    reason: str,
    drop: Callable[[Dict[str, Any]], bool],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for row in rows:
        if drop(row):
            excluded.append(exclusion_record(row, stage, reason))
        else:
            kept.append(row)
    return kept, excluded


def classify_non_software(
    row: Dict[str, Any], spec: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """Devolve (razoes de exclusao automatica, razoes apenas sinalizadas)."""
    auto: List[str] = []
    flagged: List[str] = []
    topics = set(topic_list(row))
    name = (row.get("full_name") or "").split("/")[-1].lower()
    description = (row.get("description") or "").lower()

    for topic in spec.get("auto_exclude_topics") or []:
        if topic.lower() in topics:
            auto.append(f"non_software:topic:{topic.lower()}")

    for pattern in spec.get("auto_exclude_name_regex") or []:
        if re.search(pattern, name, flags=re.I):
            auto.append(f"non_software:name:{pattern}")

    for pattern in spec.get("flag_name_regex") or []:
        if re.search(pattern, name, flags=re.I):
            flagged.append(f"flag:name:{pattern}")

    for term in spec.get("flag_description_terms") or []:
        if term.lower() in description:
            flagged.append(f"flag:description:{term.lower()}")

    # Dedup preservando ordem.
    def unique(items: List[str]) -> List[str]:
        seen = set()
        ordered = []
        for item in items:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    return unique(auto), unique(flagged)


def primary_non_software_category(reason: str) -> str:
    if ":topic:" in reason:
        return reason.split(":topic:", 1)[1]
    if reason.startswith("non_software:name:"):
        return "name_pattern"
    return reason


def sort_eligible(rows: List[Dict[str, Any]], ordering: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    def key(row: Dict[str, Any]) -> Tuple:
        parts = []
        for rule in ordering:
            field = rule["field"]
            direction = (rule.get("direction") or "asc").lower()
            value: Any = row.get(field)
            if field in {"stargazers_count", "forks_count", "repository_id", "size_kb"}:
                number = as_int(value, 0)
                parts.append(-number if direction == "desc" else number)
            elif field in {"pushed_at", "created_at", "updated_at"}:
                parsed = parse_iso(str(value or ""))
                stamp = parsed.timestamp() if parsed else 0.0
                parts.append(-stamp if direction == "desc" else stamp)
            else:
                text = str(value or "")
                parts.append(text if direction == "asc" else text)
        return tuple(parts)

    return sorted(rows, key=key)


def run_filters(
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
    run_dir: Path,
    collection_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    exclude_cfg = config.get("exclude") or {}
    activity_cfg = config.get("activity") or {}
    non_software_cfg = config.get("non_software") or {}
    now = collection_time or utc_now()
    years = int(activity_cfg.get("max_inactive_years") or 3)
    cutoff = minus_years(now, years)
    activity_field = activity_cfg.get("field") or "pushed_at"

    attrition: List[Dict[str, Any]] = []
    excluded_dir = run_dir / "excluded"
    excluded_dir.mkdir(parents=True, exist_ok=True)
    flagged_rows: List[Dict[str, Any]] = []
    current = list(rows)

    def record_stage(stage: str, before: int, excluded_n: int) -> None:
        after = before - excluded_n
        pct = (100.0 * excluded_n / before) if before else 0.0
        attrition.append(
            {
                "stage": stage,
                "input_count": before,
                "excluded_count": excluded_n,
                "output_count": after,
                "excluded_percentage": round(pct, 4),
            }
        )

    record_stage("universe", len(current), 0)

    stages: List[Tuple[str, str, Callable[[Dict[str, Any]], bool], str]] = []
    if exclude_cfg.get("forks", True):
        stages.append(("remove_forks", "is_fork", lambda r: as_bool(r.get("is_fork")), "forks.jsonl"))
    if exclude_cfg.get("mirrors", True):
        stages.append(
            (
                "remove_mirrors",
                "is_mirror",
                lambda r: as_bool(r.get("is_mirror")) or bool(r.get("mirror_url")),
                "mirrors.jsonl",
            )
        )
    if exclude_cfg.get("archived", True):
        stages.append(("remove_archived", "archived", lambda r: as_bool(r.get("archived")), "archived.jsonl"))
    if exclude_cfg.get("disabled", True):
        stages.append(("remove_disabled", "disabled", lambda r: as_bool(r.get("disabled")), "disabled.jsonl"))
    if exclude_cfg.get("inactive", True):
        def is_inactive(row: Dict[str, Any]) -> bool:
            parsed = parse_iso(str(row.get(activity_field) or ""))
            if parsed is None:
                return True
            return parsed < cutoff

        stages.append(("remove_inactive", "inactive_3_years", is_inactive, "inactive.jsonl"))
    if exclude_cfg.get("templates", True):
        stages.append(
            ("remove_templates", "is_template", lambda r: as_bool(r.get("is_template")), "templates.jsonl")
        )
    if exclude_cfg.get("empty", True):
        def is_empty(row: Dict[str, Any]) -> bool:
            return as_int(row.get("size_kb"), 0) <= 0 or not str(row.get("default_branch") or "").strip()

        stages.append(("remove_empty", "empty_or_no_default_branch", is_empty, "empty.jsonl"))

    for stage, reason, predicate, filename in stages:
        before = len(current)
        current, dropped = apply_predicate(current, stage, reason, predicate)
        write_jsonl(excluded_dir / filename, dropped)
        record_stage(stage, before, len(dropped))

    non_software_dropped: List[Dict[str, Any]] = []
    if exclude_cfg.get("non_software", True):
        before = len(current)
        kept: List[Dict[str, Any]] = []
        for row in current:
            auto_reasons, flag_reasons = classify_non_software(row, non_software_cfg)
            if auto_reasons:
                non_software_dropped.append(
                    exclusion_record(
                        row,
                        "remove_non_software",
                        auto_reasons[0],
                        extra={
                            "primary_reason": auto_reasons[0],
                            "all_reasons": auto_reasons,
                            "flagged_reasons": flag_reasons,
                        },
                    )
                )
            else:
                if flag_reasons:
                    flagged_rows.append(
                        {
                            "repository_id": row.get("repository_id"),
                            "full_name": row.get("full_name"),
                            "html_url": row.get("html_url"),
                            "flag_reasons": "; ".join(flag_reasons),
                            "topics": row.get("topics"),
                            "description": row.get("description"),
                        }
                    )
                kept.append(row)
        current = kept
        write_jsonl(excluded_dir / "non_software.jsonl", non_software_dropped)
        record_stage("remove_non_software", before, len(non_software_dropped))

    reason_counts: Dict[str, int] = {}
    for item in non_software_dropped:
        category = primary_non_software_category(str(item.get("primary_reason") or item["exclusion_reason"]))
        reason_counts[category] = reason_counts.get(category, 0) + 1

    write_csv(
        run_dir / "non_software_reasons.csv",
        ["motivo", "quantidade"],
        [{"motivo": key, "quantidade": value} for key, value in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))],
    )
    write_csv(
        run_dir / "flagged_non_software.csv",
        ["repository_id", "full_name", "html_url", "flag_reasons", "topics", "description"],
        flagged_rows,
    )
    write_csv(
        run_dir / "filter_attrition.csv",
        ["stage", "input_count", "excluded_count", "output_count", "excluded_percentage"],
        attrition,
    )

    ordering = config.get("ordering") or [
        {"field": "stargazers_count", "direction": "desc"},
        {"field": "pushed_at", "direction": "desc"},
        {"field": "repository_id", "direction": "asc"},
    ]
    eligible = sort_eligible(current, ordering)
    write_csv(run_dir / "eligible_repositories.csv", ELIGIBLE_FIELDS, eligible)

    return {
        "eligible": eligible,
        "attrition": attrition,
        "cutoff_date": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "activity_field": activity_field,
        "flagged_non_software": len(flagged_rows),
        "non_software_reason_counts": reason_counts,
        "ordering": ordering,
    }


def select_top_n(eligible: List[Dict[str, Any]], limit: int, run_dir: Path) -> List[Dict[str, Any]]:
    selected = eligible[: max(0, limit)]
    write_csv(run_dir / "selected_repositories.csv", ELIGIBLE_FIELDS, selected)
    return selected
