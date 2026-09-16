from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from .util import log

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"
SEARCH_SLEEP_S = 2.1
CORE_SLEEP_S = 0.75
API_VERSION = "2022-11-28"


class GitHubClient:
    """Cliente REST/GraphQL com backoff da Search (30/min) e da API core."""

    def __init__(self, token: str, api_version: str = API_VERSION) -> None:
        if not token:
            raise SystemExit(
                "GITHUB_TOKEN nao encontrado. Copie .env.example para .env e informe o token."
            )
        self.api_version = api_version
        self.last_rate: Dict[str, Any] = {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": api_version,
                "User-Agent": "SpringTCC-spring-boot-selection",
            }
        )

    def _record_rate(self, response: requests.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        resource = response.headers.get("X-RateLimit-Resource") or ""
        self.last_rate = {
            "resource": resource,
            "remaining": remaining,
            "reset_at": reset,
            "limit": response.headers.get("X-RateLimit-Limit"),
        }

    def _backoff(self, response: requests.Response, search: bool) -> None:
        self._record_rate(response)
        retry_after = response.headers.get("Retry-After")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        resource = (response.headers.get("X-RateLimit-Resource") or "").lower()
        is_search = search or resource == "search"
        if retry_after:
            wait = max(5, int(retry_after) + 1)
            log(f"rate-limit Retry-After={wait}s remaining={remaining} reset_at={reset}")
            time.sleep(wait)
            return
        if remaining is not None and int(remaining) <= (2 if is_search else 80):
            wait = 5
            if reset:
                wait = max(5, int(reset) - int(time.time()) + 2)
            log(
                f"rate-limit {resource or 'core'} remaining={remaining} "
                f"reset_at={reset}; pausa {wait}s"
            )
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
                    log(
                        f"rate-limit secundario HTTP {response.status_code} "
                        f"remaining={response.headers.get('X-RateLimit-Remaining')} "
                        f"reset_at={response.headers.get('X-RateLimit-Reset')}"
                    )
                    time.sleep(30 * (attempt + 1))
                    continue
                self._backoff(response, search)
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
                data = payload.get("data") or {}
                if data:
                    return data
                raise RuntimeError(messages)
            return payload.get("data") or {}
        raise RuntimeError("GraphQL: excesso de tentativas apos rate limit")
