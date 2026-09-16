from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .github_client import GitHubClient
from .util import as_bool, log, utc_now_iso

SEARCH_PER_PAGE = 100
SEARCH_HARD_CAP = 1000
STAR_SLICES = [
    "0..0",
    "1..2",
    "3..5",
    "6..10",
    "11..20",
    "21..50",
    "51..100",
    "101..500",
    "501..2000",
    ">2000",
]

POPULATION_FIELDS = [
    "repository_id",
    "node_id",
    "full_name",
    "html_url",
    "description",
    "is_fork",
    "is_mirror",
    "mirror_url",
    "is_template",
    "archived",
    "disabled",
    "default_branch",
    "size_kb",
    "language",
    "stargazers_count",
    "forks_count",
    "open_issues_count",
    "topics",
    "created_at",
    "updated_at",
    "pushed_at",
    "license",
    "query_partition",
    "collected_at",
]


def build_discovery_query(
    base: str,
    include_forks: bool,
    created: Optional[str] = None,
    stars: Optional[str] = None,
) -> str:
    parts = [base.strip()]
    if include_forks:
        parts.append("fork:true")
    if created:
        parts.append(f"created:{created}")
    if stars:
        parts.append(f"stars:{stars}")
    return " ".join(parts)


def yearly_windows(start_year: int, end_year: int) -> List[Tuple[date, date]]:
    return [(date(year, 1, 1), date(year, 12, 31)) for year in range(start_year, end_year + 1)]


def split_dates(start: date, end: date) -> Optional[List[Tuple[date, date]]]:
    if start >= end:
        return None
    mid = start + timedelta(days=(end - start).days // 2)
    if mid >= end:
        mid = end - timedelta(days=1)
    if mid < start:
        return None
    return [(start, mid), (mid + timedelta(days=1), end)]


def fmt_range(start: date, end: date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def normalize_repo(item: Dict[str, Any], partition: str) -> Optional[Dict[str, Any]]:
    repo_id = item.get("id")
    full_name = item.get("full_name") or ""
    if repo_id is None or not full_name:
        return None
    license_info = item.get("license") or {}
    return {
        "repository_id": repo_id,
        "node_id": item.get("node_id") or "",
        "full_name": full_name,
        "html_url": item.get("html_url") or "",
        "description": (item.get("description") or "").replace("\r", " ").replace("\n", " "),
        "is_fork": bool(item.get("fork")),
        "is_mirror": bool(item.get("mirror_url")),
        "mirror_url": item.get("mirror_url") or "",
        "is_template": bool(item.get("is_template")),
        "archived": bool(item.get("archived")),
        "disabled": bool(item.get("disabled")),
        "default_branch": item.get("default_branch") or "",
        "size_kb": item.get("size") or 0,
        "language": item.get("language") or "",
        "stargazers_count": item.get("stargazers_count") or 0,
        "forks_count": item.get("forks_count") or 0,
        "open_issues_count": item.get("open_issues_count") or 0,
        "topics": "; ".join(item.get("topics") or []),
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "license": license_info.get("spdx_id") or "",
        "query_partition": partition,
        "collected_at": utc_now_iso(),
    }


class PopulationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seen: Set[str] = set()
        if self.path.exists():
            with self.path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    key = row.get("repository_id") or row.get("full_name")
                    if key:
                        self.seen.add(str(key))
        else:
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=POPULATION_FIELDS).writeheader()

    def append(self, rows: Iterable[Dict[str, Any]]) -> int:
        added = 0
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=POPULATION_FIELDS, extrasaction="ignore")
            for row in rows:
                key = str(row.get("repository_id") or "")
                if not key or key in self.seen:
                    continue
                writer.writerow({field: row.get(field, "") for field in POPULATION_FIELDS})
                self.seen.add(key)
                added += 1
        return added


class WindowCheckpoint:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.done: Set[str] = set()
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.done = set(payload.get("completed") or [])

    def mark(self, key: str) -> None:
        self.done.add(key)
        self.path.write_text(
            json.dumps({"completed": sorted(self.done)}, indent=2),
            encoding="utf-8",
        )


def search_page(
    client: GitHubClient, query: str, page: int
) -> Tuple[int, List[Dict[str, Any]], bool]:
    response = client.rest_get(
        "/search/repositories",
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": SEARCH_PER_PAGE,
            "page": page,
        },
        search=True,
    )
    if response.status_code != 200:
        log(f"search HTTP {response.status_code}: {response.text[:200]}")
        return 0, [], False
    payload = response.json()
    return (
        int(payload.get("total_count") or 0),
        payload.get("items") or [],
        bool(payload.get("incomplete_results")),
    )


def append_query_log(path: Path, row: Dict[str, Any]) -> None:
    exists = path.exists()
    fields = [
        "collected_at",
        "query",
        "total_count",
        "retrieved",
        "incomplete_results",
        "partition_key",
    ]
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def count_population(client: GitHubClient, config: Dict[str, Any]) -> Dict[str, Any]:
    discovery = config["discovery"]
    query = build_discovery_query(
        discovery["query"],
        as_bool(discovery.get("include_forks_in_search", True)),
    )
    total, _, incomplete = search_page(client, query, 1)
    result = {
        "query": query,
        "collected_at": utc_now_iso(),
        "total_count": total,
        "incomplete_results": incomplete,
        "api_version": discovery.get("api_version", "2022-11-28"),
        "note": (
            "total_count e a estimativa da Search API para a query inteira, "
            "antes de qualquer filtro local. Pode divergir da soma das particoes."
        ),
    }
    return result


def collect_range(
    client: GitHubClient,
    store: PopulationStore,
    checkpoint: WindowCheckpoint,
    query_log: Path,
    config: Dict[str, Any],
    start: date,
    end: date,
    stars: Optional[str] = None,
) -> None:
    discovery = config["discovery"]
    created = fmt_range(start, end)
    key = f"{created}|stars:{stars or '*'}"
    if key in checkpoint.done:
        return
    query = build_discovery_query(
        discovery["query"],
        as_bool(discovery.get("include_forks_in_search", True)),
        created=created,
        stars=stars,
    )
    total, items, incomplete = search_page(client, query, 1)
    log(f"{query}  total_count={total}  coletados={len(store.seen)}")
    if total == 0:
        append_query_log(
            query_log,
            {
                "collected_at": utc_now_iso(),
                "query": query,
                "total_count": 0,
                "retrieved": 0,
                "incomplete_results": incomplete,
                "partition_key": key,
            },
        )
        checkpoint.mark(key)
        return

    def drain(first_items: List[Dict[str, Any]], cap: int) -> int:
        added = store.append(
            repo
            for item in first_items
            if (repo := normalize_repo(item, key))
        )
        fetched = len(first_items)
        page = 2
        while fetched < cap:
            _, batch, _ = search_page(client, query, page)
            if not batch:
                break
            added += store.append(
                repo for item in batch if (repo := normalize_repo(item, key))
            )
            fetched += len(batch)
            page += 1
            if len(batch) < SEARCH_PER_PAGE:
                break
        append_query_log(
            query_log,
            {
                "collected_at": utc_now_iso(),
                "query": query,
                "total_count": total,
                "retrieved": fetched,
                "incomplete_results": incomplete,
                "partition_key": key,
            },
        )
        return added

    if total <= SEARCH_HARD_CAP:
        added = drain(items, total)
        log(f"    +{added} novos nesta janela")
        checkpoint.mark(key)
        return

    parts = split_dates(start, end)
    if parts:
        log(f"    {total} > 1000; partindo {created}")
        for left, right in parts:
            collect_range(client, store, checkpoint, query_log, config, left, right, stars)
        return

    if stars is None:
        log(f"    {total} > 1000 no mesmo dia {created}; partindo por estrelas")
        for slice_stars in STAR_SLICES:
            collect_range(
                client, store, checkpoint, query_log, config, start, end, slice_stars
            )
        checkpoint.mark(key)
        return

    log(f"    [!] {query} ainda > 1000; recuperando o teto de 1000")
    drain(items, SEARCH_HARD_CAP)
    checkpoint.mark(key)


def discover_population(
    client: GitHubClient, config: Dict[str, Any], run_dir: Path
) -> PopulationStore:
    store = PopulationStore(run_dir / "population.csv")
    checkpoint = WindowCheckpoint(run_dir / "windows.json")
    query_log = run_dir / "queries.csv"
    discovery = config["discovery"]
    start_year = int(discovery["start_year"])
    end_year = int(discovery["end_year"])
    log(
        f"discover: query={discovery['query']} fork:true="
        f"{discovery.get('include_forks_in_search')} "
        f"{start_year}-{end_year} ja={len(store.seen)}"
    )
    for start, end in yearly_windows(start_year, end_year):
        collect_range(client, store, checkpoint, query_log, config, start, end)
    log(f"discover concluido: {len(store.seen)} repositorios unicos")
    return store
