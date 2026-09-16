"""
Coleta em massa de metadados de repositorios Spring Boot no GitHub.

A Search REST devolve no maximo 1.000 resultados por consulta. Para chegar
a dezenas de milhares, as janelas de created: (e, se preciso, de stars:)
sao partidas automaticamente. A descoberta usa so a Search; contribuidores
e issues totais entram numa segunda passada, com checkpoint no CSV.

Uso:
    python collect_spring_boot_50k.py --limit 50000
    python collect_spring_boot_50k.py --phase enrich
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

import requests

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"
SEARCH_PER_PAGE = 100
SEARCH_HARD_CAP = 1000
SEARCH_SLEEP_S = 2.1
CORE_SLEEP_S = 0.75
GRAPHQL_BATCH = 20
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

CSV_FIELDS = [
    "full_name",
    "url",
    "created_at",
    "pushed_at",
    "updated_at",
    "stars",
    "forks",
    "open_issues",
    "total_issues",
    "contributors",
    "topics",
    "language",
    "size_kb",
    "archived",
    "disabled",
    "default_branch",
    "license",
    "framework_primary",
    "detection_source",
    "collected_at",
    "enriched_at",
]


def load_env() -> None:
    for env_path in (Path(".env"), Path(__file__).resolve().parent / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        break


def default_output_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "Artefatos"
        / "metadados_spring_boot_50k.csv"
    )


def log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


class GitHubClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise SystemExit(
                "GITHUB_TOKEN nao encontrado. Copie .env.example para .env e informe o token."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "SpringTCC-spring-boot-50k",
            }
        )

    def _backoff(self, response: requests.Response, search: bool) -> None:
        retry_after = response.headers.get("Retry-After")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        resource = (response.headers.get("X-RateLimit-Resource") or "").lower()
        is_search = search or resource == "search"
        if retry_after:
            wait = max(5, int(retry_after) + 1)
            log(f"rate-limit Retry-After={wait}s")
            time.sleep(wait)
            return
        if remaining is not None and int(remaining) <= (2 if is_search else 80):
            wait = 5
            if reset:
                wait = max(5, int(reset) - int(time.time()) + 2)
            log(f"rate-limit {resource or 'core'} restam {remaining}; pausa {wait}s")
            time.sleep(wait)
            return
        time.sleep(SEARCH_SLEEP_S if is_search else CORE_SLEEP_S)

    def rest_get(
        self, path: str, params: Optional[Dict[str, Any]] = None, search: bool = False
    ) -> requests.Response:
        url = path if path.startswith("http") else f"{REST_URL}{path}"
        last = None
        for attempt in range(8):
            response = self.session.get(url, params=params, timeout=90)
            last = response
            if response.status_code in (403, 429):
                text = response.text.lower()
                if "secondary rate limit" in text or "abuse" in text or response.status_code == 429:
                    time.sleep(30 * (attempt + 1))
                    continue
                self._backoff(response, search)
                if response.status_code in (403, 429):
                    continue
            self._backoff(response, search)
            return response
        return last if last is not None else response

    def graphql(self, query: str) -> Dict[str, Any]:
        for attempt in range(8):
            response = self.session.post(GRAPHQL_URL, json={"query": query}, timeout=90)
            self._backoff(response, search=False)
            if response.status_code in (403, 429):
                time.sleep(20 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"GraphQL HTTP {response.status_code}: {response.text[:240]}")
            payload = response.json()
            if payload.get("errors"):
                messages = "; ".join(e.get("message", str(e)) for e in payload["errors"])
                if "rate limit" in messages.lower():
                    time.sleep(20 * (attempt + 1))
                    continue
                # Aliases individuais podem falhar (repo sumiu); devolve o que veio.
                data = payload.get("data") or {}
                if data:
                    return data
                raise RuntimeError(messages)
            return payload.get("data") or {}
        raise RuntimeError("GraphQL: excesso de tentativas apos rate limit")


def build_query(created: str, stars: Optional[str] = None) -> str:
    # Sem OR/parenteses: a Search de repositorios devolve total_count=0.
    # Sem fork:false: a Search so aceita fork:true / fork:only.
    parts = ["language:Java", "topic:spring-boot", f"created:{created}"]
    if stars:
        parts.append(f"stars:{stars}")
    return " ".join(parts)


def yearly_windows(start_year: int, end_year: int) -> List[Tuple[date, date]]:
    windows = []
    for year in range(start_year, end_year + 1):
        windows.append((date(year, 1, 1), date(year, 12, 31)))
    return windows


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


def normalize_repo(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if item.get("fork"):
        return None
    language = item.get("language") or ""
    if language and language.lower() not in {"java", "kotlin"}:
        return None
    license_info = item.get("license") or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "full_name": item.get("full_name") or "",
        "url": item.get("html_url") or "",
        "created_at": item.get("created_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "updated_at": item.get("updated_at") or "",
        "stars": item.get("stargazers_count") or 0,
        "forks": item.get("forks_count") or 0,
        "open_issues": item.get("open_issues_count") or 0,
        "total_issues": "",
        "contributors": "",
        "topics": "; ".join(item.get("topics") or []),
        "language": language,
        "size_kb": item.get("size") or 0,
        "archived": bool(item.get("archived")),
        "disabled": bool(item.get("disabled")),
        "default_branch": item.get("default_branch") or "",
        "license": license_info.get("spdx_id") or "",
        "framework_primary": "Spring Boot",
        "detection_source": "topics",
        "collected_at": now,
        "enriched_at": "",
    }


class CsvStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seen: Set[str] = set()
        if self.path.exists():
            with self.path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    name = row.get("full_name") or ""
                    if name:
                        self.seen.add(name)
        else:
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=CSV_FIELDS).writeheader()

    def append(self, rows: Iterable[Dict[str, Any]]) -> int:
        added = 0
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            for row in rows:
                name = row.get("full_name") or ""
                if not name or name in self.seen:
                    continue
                writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
                self.seen.add(name)
                added += 1
        return added

    def rewrite(self, rows: List[Dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp.csv")
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
        tmp.replace(self.path)
        self.seen = {row["full_name"] for row in rows if row.get("full_name")}

    def load_rows(self) -> List[Dict[str, Any]]:
        with self.path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


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
) -> Tuple[int, List[Dict[str, Any]]]:
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
        return 0, []
    payload = response.json()
    return int(payload.get("total_count") or 0), payload.get("items") or []


def collect_range(
    client: GitHubClient,
    store: CsvStore,
    checkpoint: WindowCheckpoint,
    start: date,
    end: date,
    limit: int,
    stars: Optional[str] = None,
) -> None:
    if len(store.seen) >= limit:
        return
    created = fmt_range(start, end)
    key = f"{created}|stars:{stars or '*'}"
    if key in checkpoint.done:
        return
    query = build_query(created, stars)
    total, items = search_page(client, query, 1)
    log(f"{query}  total_count={total}  amostra={len(store.seen)}/{limit}")
    if total == 0:
        checkpoint.mark(key)
        return
    if total <= SEARCH_HARD_CAP:
        added = store.append(repo for item in items if (repo := normalize_repo(item)))
        fetched = len(items)
        page = 2
        while fetched < total and len(store.seen) < limit:
            _, batch = search_page(client, query, page)
            if not batch:
                break
            added += store.append(repo for item in batch if (repo := normalize_repo(item)))
            fetched += len(batch)
            page += 1
            if len(batch) < SEARCH_PER_PAGE:
                break
        log(f"    +{added} novos nesta janela")
        checkpoint.mark(key)
        return

    parts = split_dates(start, end)
    if parts:
        log(f"    {total} > 1000; partindo {created}")
        for left, right in parts:
            collect_range(client, store, checkpoint, left, right, limit, stars)
        return

    if stars is None:
        log(f"    {total} > 1000 no mesmo dia {created}; partindo por estrelas")
        for slice_stars in STAR_SLICES:
            if len(store.seen) >= limit:
                return
            collect_range(client, store, checkpoint, start, end, limit, slice_stars)
        checkpoint.mark(key)
        return

    log(f"    [!] {query} ainda > 1000; pegando os 1000 mais estrelados")
    added = store.append(repo for item in items if (repo := normalize_repo(item)))
    fetched = len(items)
    page = 2
    while fetched < SEARCH_HARD_CAP and len(store.seen) < limit:
        _, batch = search_page(client, query, page)
        if not batch:
            break
        added += store.append(repo for item in batch if (repo := normalize_repo(item)))
        fetched += len(batch)
        page += 1
        if len(batch) < SEARCH_PER_PAGE:
            break
    log(f"    +{added} (cap 1000)")
    checkpoint.mark(key)


def phase_search(client: GitHubClient, store: CsvStore, args: argparse.Namespace) -> None:
    checkpoint = WindowCheckpoint(store.path.with_suffix(".windows.json"))
    log(
        f"fase search: alvo {args.limit}  ja no CSV={len(store.seen)}  "
        f"janelas feitas={len(checkpoint.done)}"
    )
    for start, end in yearly_windows(args.start_year, args.end_year):
        if len(store.seen) >= args.limit:
            break
        collect_range(client, store, checkpoint, start, end, args.limit)
    log(f"fase search concluida: {len(store.seen)} repositorios unicos")


def contributor_count(client: GitHubClient, full_name: str) -> Optional[int]:
    owner, repo = full_name.split("/", 1)
    response = client.rest_get(
        f"/repos/{owner}/{repo}/contributors",
        params={"per_page": 1, "anon": "true"},
    )
    if response.status_code in (204, 404):
        return 0
    if response.status_code != 200:
        return None
    link = response.headers.get("Link") or response.headers.get("link") or ""
    if 'rel="last"' in link:
        for part in link.split(","):
            if 'rel="last"' in part:
                url = part[part.find("<") + 1 : part.find(">")]
                page = parse_qs(urlparse(url).query).get("page", [None])[0]
                return int(page) if page else 1
    body = response.json()
    return len(body) if isinstance(body, list) else 0


def build_issues_query(batch: List[Dict[str, Any]]) -> str:
    parts = ["query {"]
    for index, row in enumerate(batch):
        owner, name = row["full_name"].split("/", 1)
        alias = f"r{index}"
        parts.append(
            f'  {alias}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) '
            "{ issues { totalCount } issuesOpen: issues(states: [OPEN]) { totalCount } }"
        )
    parts.append("}")
    return "\n".join(parts)


def phase_enrich(client: GitHubClient, store: CsvStore, args: argparse.Namespace) -> None:
    rows = store.load_rows()
    pending = [
        row
        for row in rows
        if row.get("full_name")
        and (row.get("contributors") in ("", None) or row.get("total_issues") in ("", None))
    ]
    log(f"fase enrich: {len(pending)} pendentes de {len(rows)}")
    if not pending:
        return

    dirty = False
    by_name = {row["full_name"]: row for row in rows}

    for offset in range(0, len(pending), GRAPHQL_BATCH):
        batch = pending[offset : offset + GRAPHQL_BATCH]
        try:
            data = client.graphql(build_issues_query(batch))
        except (RuntimeError, requests.RequestException) as exc:
            log(f"    [!] graphql lote {offset}: {exc}")
            data = {}
        for index, row in enumerate(batch):
            node = data.get(f"r{index}") or {}
            issues = node.get("issues") or {}
            issues_open = node.get("issuesOpen") or {}
            target = by_name[row["full_name"]]
            if issues.get("totalCount") is not None:
                target["total_issues"] = issues["totalCount"]
            if issues_open.get("totalCount") is not None:
                target["open_issues"] = issues_open["totalCount"]
        dirty = True
        if offset % 200 == 0 and offset:
            store.rewrite(rows)
            log(f"    issues {min(offset + GRAPHQL_BATCH, len(pending))}/{len(pending)}")

    if dirty:
        store.rewrite(rows)
        log("    issues gravadas; iniciando contribuidores")

    for index, row in enumerate(pending, 1):
        target = by_name[row["full_name"]]
        if target.get("contributors") not in ("", None):
            continue
        try:
            count = contributor_count(client, row["full_name"])
        except requests.RequestException as exc:
            log(f"    [!] contributors {row['full_name']}: {exc}")
            count = None
        if count is not None:
            target["contributors"] = count
            target["enriched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if index % 50 == 0:
            store.rewrite(rows)
            log(f"    contributors {index}/{len(pending)}  amostra={len(rows)}")
    store.rewrite(rows)
    filled = sum(1 for row in rows if row.get("contributors") not in ("", None))
    log(f"fase enrich concluida: {filled}/{len(rows)} com contribuidores")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coleta em massa de metadados Spring Boot (Search fatiada + enrich)."
    )
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument(
        "--phase",
        choices=("search", "enrich", "all"),
        default="all",
        help="search = so descoberta; enrich = preenche CSV existente; all = as duas",
    )
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=default_output_path())
    return parser.parse_args()


def main() -> int:
    load_env()
    args = parse_args()
    client = GitHubClient(os.getenv("GITHUB_TOKEN", ""))
    store = CsvStore(args.output)
    log(f"saida: {args.output}")
    if args.phase in ("search", "all"):
        phase_search(client, store, args)
    if args.phase in ("enrich", "all"):
        phase_enrich(client, store, args)
    log(f"fim: {len(store.seen)} linhas em {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
