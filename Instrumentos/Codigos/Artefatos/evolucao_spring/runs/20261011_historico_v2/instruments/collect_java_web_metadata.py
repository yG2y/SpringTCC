"""
Coleta metadados de repositorios Java web no GitHub.

Recupera estrelas, issues, contribuidores, datas e topics (GraphQL + REST)
e classifica o framework web a partir de topics e arquivos de build
(pom.xml / build.gradle), sem clonar o repositorio nem executar a CK.

Uso:
    python collect_java_web_metadata.py --limit 200
"""

from __future__ import annotations

import argparse
import base64
import csv
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

import requests

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

# Topics conferidos um a um contra /search/repositories: os que retornavam
# zero resultado (vert.x, spark-java, eclipse-vertx, grails) foram removidos.
WEB_TOPICS = [
    "spring-boot",
    "spring-mvc",
    "quarkus",
    "micronaut",
    "helidon",
    "dropwizard",
    "vertx",
    "play-framework",
    "playframework",
    "vaadin",
    "jsf",
    "primefaces",
    "struts",
    "struts2",
    "wicket",
    "javalin",
    "sparkjava",
    "jakarta-ee",
    "java-ee",
    "javaee",
    "servlet",
    "jhipster",
    "gwt",
    "java-web",
]

CREATED_WINDOWS = [
    "2009-01-01..2013-12-31",
    "2014-01-01..2017-12-31",
    "2018-01-01..2021-12-31",
    "2022-01-01..2026-12-31",
]

# Minimo de repositorios retirados de cada par (topic, janela) antes de
# repassar o excedente para completar a amostra.
MIN_PER_CELL = 4

SEARCH_PER_PAGE = 100

FRAMEWORK_PRIORITY = [
    "Spring Boot",
    "Quarkus",
    "Micronaut",
    "Helidon",
    "Dropwizard",
    "Vert.x",
    "Play Framework",
    "Vaadin",
    "JSF / PrimeFaces",
    "Struts",
    "Wicket",
    "Javalin",
    "Spark Java",
    "Spring MVC",
    "Jakarta EE / Java EE",
    "GWT",
    "Nao web / indefinido",
]

TOPIC_TO_FRAMEWORK = {
    "spring-boot": "Spring Boot",
    "spring-mvc": "Spring MVC",
    "quarkus": "Quarkus",
    "micronaut": "Micronaut",
    "helidon": "Helidon",
    "dropwizard": "Dropwizard",
    "vertx": "Vert.x",
    "vert.x": "Vert.x",
    "eclipse-vertx": "Vert.x",
    "play-framework": "Play Framework",
    "playframework": "Play Framework",
    "vaadin": "Vaadin",
    "jsf": "JSF / PrimeFaces",
    "java-server-faces": "JSF / PrimeFaces",
    "primefaces": "JSF / PrimeFaces",
    "struts": "Struts",
    "struts2": "Struts",
    "wicket": "Wicket",
    "javalin": "Javalin",
    "sparkjava": "Spark Java",
    "spark-java": "Spark Java",
    "jakarta-ee": "Jakarta EE / Java EE",
    "java-ee": "Jakarta EE / Java EE",
    "javaee": "Jakarta EE / Java EE",
    "servlet": "Jakarta EE / Java EE",
    "jhipster": "Spring Boot",
    "gwt": "GWT",
}

BUILD_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("Spring Boot", re.compile(r"spring-boot-starter(?:-web(?:flux)?)?", re.I)),
    ("Quarkus", re.compile(r"io\.quarkus", re.I)),
    ("Micronaut", re.compile(r"io\.micronaut", re.I)),
    ("Helidon", re.compile(r"io\.helidon", re.I)),
    ("Dropwizard", re.compile(r"io\.dropwizard", re.I)),
    ("Vert.x", re.compile(r"io\.vertx", re.I)),
    ("Play Framework", re.compile(r"com\.typesafe\.play|org\.playframework", re.I)),
    ("Vaadin", re.compile(r"com\.vaadin", re.I)),
    ("JSF / PrimeFaces", re.compile(r"jakarta\.faces|javax\.faces|org\.primefaces", re.I)),
    ("Struts", re.compile(r"org\.apache\.struts", re.I)),
    ("Wicket", re.compile(r"org\.apache\.wicket", re.I)),
    ("Javalin", re.compile(r"io\.javalin", re.I)),
    ("Spark Java", re.compile(r"com\.sparkjava", re.I)),
    ("Spring MVC", re.compile(r"spring-webmvc", re.I)),
    ("Jakarta EE / Java EE", re.compile(r"jakarta\.servlet|javax\.servlet|jakarta\.ws\.rs|javax\.ws\.rs", re.I)),
    ("GWT", re.compile(r"com\.google\.gwt", re.I)),
]

SPRING_BOOT_VERSION_PATTERNS = [
    re.compile(
        r"<parent>[\s\S]*?spring-boot-starter-parent[\s\S]*?<version>\s*([^<]+)\s*</version>",
        re.I,
    ),
    re.compile(r"<spring-boot\.version>\s*([^<]+)\s*</spring-boot\.version>", re.I),
    re.compile(
        r"""id\s*\(?\s*['\"]org\.springframework\.boot['\"]\s*\)?\s+version\s+['\"]([^'\"]+)['\"]""",
        re.I,
    ),
]

CSV_FIELDS = [
    "full_name",
    "url",
    "created_at",
    "pushed_at",
    "stars",
    "forks",
    "open_issues",
    "total_issues",
    "contributors",
    "topics",
    "frameworks",
    "framework_primary",
    "detection_source",
    "spring_boot_version",
    "collected_at",
]


def load_env() -> None:
    env_paths = [Path(".env"), Path(__file__).resolve().parent / ".env"]
    for env_path in env_paths:
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
        / "metadados_java_web.csv"
    )


class RateLimitError(RuntimeError):
    pass


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
                "User-Agent": "SpringTCC-java-web-metadata",
            }
        )

    def _respect_rate_limit(self, response: requests.Response, search: bool = False) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is None:
            return
        # A Search tem cota propria de 30 req/min: um piso fixo de 50 dispararia
        # pausa em toda chamada. O recurso vem no header X-RateLimit-Resource.
        resource = (response.headers.get("X-RateLimit-Resource") or "").lower()
        quota = int(response.headers.get("X-RateLimit-Limit") or 0)
        threshold = 2 if (search or resource == "search" or 0 < quota <= 30) else 50
        if int(remaining) > threshold:
            return
        wait = 5
        if reset:
            wait = max(5, int(reset) - int(time.time()) + 2)
        print(f"    [rate-limit] restam {remaining} requisicoes; pausa de {wait}s")
        time.sleep(wait)

    def graphql(self, query: str, variables: Dict[str, Any], search: bool = False) -> Dict[str, Any]:
        for attempt in range(5):
            response = self.session.post(
                GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=60
            )
            self._respect_rate_limit(response, search=search)
            if response.status_code == 403 and "secondary rate limit" in response.text.lower():
                time.sleep(20 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                messages = "; ".join(e.get("message", str(e)) for e in payload["errors"])
                if "rate limit" in messages.lower():
                    time.sleep(20 * (attempt + 1))
                    continue
                raise RuntimeError(messages)
            return payload["data"]
        raise RateLimitError("GraphQL: excesso de tentativas apos rate limit")

    def rest_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = path if path.startswith("http") else f"{REST_URL}{path}"
        for attempt in range(5):
            response = self.session.get(url, params=params, timeout=60)
            self._respect_rate_limit(response)
            if response.status_code in (403, 429) and attempt < 4:
                time.sleep(15 * (attempt + 1))
                continue
            return response
        return response


def build_search_query(topic: str, created: str, min_stars: int) -> str:
    # /search/repositories nao aceita OR nem parenteses (so code search e issues
    # suportam booleanos): "(topic:a OR topic:b)" devolve total_count=0. Por isso
    # cada topic vira uma consulta separada.
    # Tambem nao usar fork:false: a Search so aceita fork:true / fork:only, e sem
    # o qualificativo os forks ja ficam de fora.
    return f"language:Java stars:>={min_stars} topic:{topic} created:{created}"


REPO_ISSUES_QUERY = """
query RepoIssues($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    issues { totalCount }
    issuesOpen: issues(states: [OPEN]) { totalCount }
  }
}
"""


def search_repos(
    client: GitHubClient, query: str, max_pages: int = 1
) -> Tuple[int, List[Dict[str, Any]]]:
    """Descoberta via REST Search. Devolve (total_count, itens da consulta)."""
    total = 0
    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        response = client.rest_get(
            "/search/repositories",
            params={
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": SEARCH_PER_PAGE,
                "page": page,
            },
        )
        if response.status_code != 200:
            print(f"        [!] search HTTP {response.status_code}: {response.text[:200]}")
            break
        payload = response.json()
        if page == 1:
            total = payload.get("total_count", 0)
        batch = payload.get("items") or []
        items.extend(batch)
        if len(batch) < SEARCH_PER_PAGE:
            break
        time.sleep(2.0)
    return total, items


def normalize_repo(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    language = item.get("language") or ""
    if language and language.lower() != "java":
        return None
    if item.get("fork"):
        return None
    topics = item.get("topics") or []
    return {
        "full_name": item["full_name"],
        "url": item.get("html_url") or "",
        "created_at": item.get("created_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "stars": item.get("stargazers_count") or 0,
        "forks": item.get("forks_count") or 0,
        "open_issues": item.get("open_issues_count") or 0,
        "total_issues": item.get("open_issues_count") or 0,
        "topics": topics,
    }


def fill_issue_counts(client: GitHubClient, repo: Dict[str, Any]) -> None:
    owner, name = repo["full_name"].split("/", 1)
    try:
        data = client.graphql(
            REPO_ISSUES_QUERY, {"owner": owner, "name": name}
        ).get("repository") or {}
    except (RuntimeError, requests.RequestException):
        return
    issues = data.get("issues") or {}
    issues_open = data.get("issuesOpen") or {}
    if issues.get("totalCount") is not None:
        repo["total_issues"] = issues["totalCount"]
    if issues_open.get("totalCount") is not None:
        repo["open_issues"] = issues_open["totalCount"]


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


def decode_github_file(payload: Dict[str, Any]) -> str:
    encoding = payload.get("encoding")
    content = payload.get("content") or ""
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def fetch_build_text(client: GitHubClient, full_name: str) -> str:
    owner, repo = full_name.split("/", 1)
    chunks: List[str] = []
    for filename in ("pom.xml", "build.gradle", "build.gradle.kts"):
        response = client.rest_get(f"/repos/{owner}/{repo}/contents/{filename}")
        if response.status_code != 200:
            continue
        payload = response.json()
        if isinstance(payload, dict) and payload.get("type") == "file":
            chunks.append(decode_github_file(payload))
    return "\n".join(chunks)


def extract_spring_boot_version(build_text: str) -> str:
    if not build_text:
        return ""
    for pattern in SPRING_BOOT_VERSION_PATTERNS:
        match = pattern.search(build_text)
        if match:
            return match.group(1).strip()
    return ""


def classify_frameworks(
    topics: Sequence[str], build_text: str
) -> Tuple[List[str], str, str]:
    from_topics: List[str] = []
    for topic in topics:
        mapped = TOPIC_TO_FRAMEWORK.get(topic.lower())
        if mapped and mapped not in from_topics:
            from_topics.append(mapped)

    from_build: List[str] = []
    if build_text:
        android = bool(re.search(r"com\.android|com\.google\.android", build_text, re.I))
        for name, pattern in BUILD_PATTERNS:
            if pattern.search(build_text) and name not in from_build:
                from_build.append(name)
        if android and not from_build:
            from_build.append("Nao web / indefinido")

    # Spring MVC so conta como primario se nao houver Boot.
    if "Spring Boot" in from_build and "Spring MVC" in from_build:
        from_build = [f for f in from_build if f != "Spring MVC"]
    if "Spring Boot" in from_topics and "Spring MVC" in from_topics:
        from_topics = [f for f in from_topics if f != "Spring MVC"]

    combined: List[str] = []
    for name in from_topics + from_build:
        if name not in combined:
            combined.append(name)

    if not combined:
        combined = ["Nao web / indefinido"]

    primary = next(
        (name for name in FRAMEWORK_PRIORITY if name in combined),
        combined[0],
    )

    has_topic = any(name != "Nao web / indefinido" for name in from_topics)
    has_build = any(name != "Nao web / indefinido" for name in from_build)
    if has_topic and has_build:
        source = "both"
    elif has_build:
        source = "build"
    elif has_topic:
        source = "topics"
    else:
        source = "none"
    return combined, primary, source


def collect_candidates(
    client: GitHubClient, limit: int, min_stars: int
) -> List[Dict[str, Any]]:
    cells = [(topic, window) for topic in WEB_TOPICS for window in CREATED_WINDOWS]
    per_cell = max(MIN_PER_CELL, math.ceil(limit / len(cells)))
    seen: Dict[str, Dict[str, Any]] = {}
    # Excedente de cada consulta: evita gastar novas chamadas de Search quando a
    # cota por celula nao for suficiente para fechar a amostra.
    reserve: List[Dict[str, Any]] = []
    nonempty = 0

    print(
        f"[*] Buscando ate {limit} repositorios Java web em {len(cells)} consultas "
        f"({len(WEB_TOPICS)} topics x {len(CREATED_WINDOWS)} janelas), "
        f"cota de {per_cell} por consulta..."
    )
    for topic, window in cells:
        if len(seen) >= limit and len(reserve) + len(seen) >= limit:
            break
        query = build_search_query(topic, window, min_stars)
        total, items = search_repos(client, query)
        if total:
            nonempty += 1
        print(f"    topic={topic} created={window} total_count={total}")
        taken = 0
        for item in items:
            repo = normalize_repo(item)
            if not repo or repo["full_name"] in seen:
                continue
            if taken < per_cell and len(seen) < limit:
                seen[repo["full_name"]] = repo
                taken += 1
            else:
                reserve.append(repo)
        time.sleep(1.0)

    for repo in reserve:
        if len(seen) >= limit:
            break
        seen.setdefault(repo["full_name"], repo)

    if not seen:
        raise SystemExit(
            "Nenhum repositorio encontrado. Verifique o GITHUB_TOKEN e a conectividade: "
            f"{nonempty} de {len(cells)} consultas retornaram total_count > 0."
        )
    print(
        f"[+] {len(seen)} repositorios unicos "
        f"({nonempty}/{len(cells)} consultas com resultado)"
    )
    return list(seen.values())


def enrich_repo(client: GitHubClient, repo: Dict[str, Any]) -> Dict[str, Any]:
    full_name = repo["full_name"]
    print(f"    metadados extra: {full_name}")
    fill_issue_counts(client, repo)
    contributors = contributor_count(client, full_name)
    build_text = fetch_build_text(client, full_name)
    frameworks, primary, source = classify_frameworks(repo["topics"], build_text)
    version = extract_spring_boot_version(build_text) if "Spring Boot" in frameworks else ""
    repo["contributors"] = contributors if contributors is not None else ""
    repo["frameworks"] = "; ".join(frameworks)
    repo["framework_primary"] = primary
    repo["detection_source"] = source
    repo["spring_boot_version"] = version
    repo["topics"] = "; ".join(repo["topics"])
    repo["collected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return repo


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coleta metadados e classifica frameworks de repositorios Java web no GitHub."
    )
    parser.add_argument("--limit", type=int, default=200, help="Maximo de repositorios (padrao: 200)")
    parser.add_argument(
        "--min-stars",
        type=int,
        default=10,
        help="Minimo de estrelas por repositorio (padrao: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_path(),
        help="Caminho do CSV de saida",
    )
    return parser.parse_args()


def main() -> int:
    load_env()
    args = parse_args()
    client = GitHubClient(os.getenv("GITHUB_TOKEN", ""))
    candidates = collect_candidates(client, args.limit, args.min_stars)
    rows: List[Dict[str, Any]] = []
    for index, repo in enumerate(candidates, 1):
        print(f"[{index}/{len(candidates)}] {repo['full_name']}")
        try:
            rows.append(enrich_repo(client, repo))
        except requests.RequestException as exc:
            print(f"    [!] falha em {repo['full_name']}: {exc}")
    write_csv(args.output, rows)
    print(f"[+] CSV salvo em: {args.output} ({len(rows)} linhas)")
    counts: Dict[str, int] = {}
    for row in rows:
        key = row.get("framework_primary") or "Nao web / indefinido"
        counts[key] = counts.get(key, 0) + 1
    print("[*] Distribuicao framework_primary:")
    for name, total in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"    {name}: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
