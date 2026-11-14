from __future__ import annotations

import base64
import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .github_client import GitHubClient
from .util import log, utc_now_iso

BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")


def compile_patterns(raw_patterns: Sequence[str]) -> List[re.Pattern[str]]:
    return [re.compile(pattern, re.I | re.S) for pattern in raw_patterns]


def decode_github_file(payload: Dict[str, Any]) -> str:
    encoding = payload.get("encoding")
    content = payload.get("content") or ""
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def fetch_build_text(client: GitHubClient, full_name: str, files: Sequence[str]) -> str:
    owner, repo = full_name.split("/", 1)
    chunks: List[str] = []
    for filename in files:
        response = client.rest_get(f"/repos/{owner}/{repo}/contents/{filename}")
        if response.status_code != 200:
            continue
        payload = response.json()
        if isinstance(payload, dict) and payload.get("type") == "file":
            chunks.append(decode_github_file(payload))
    return "\n".join(chunks)


def has_spring_boot(build_text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    if not build_text:
        return False
    return any(pattern.search(build_text) for pattern in patterns)


def validate_selected(
    client: GitHubClient,
    rows: List[Dict[str, Any]],
    config: Dict[str, Any],
    run_dir: Path,
    sample_size: int,
) -> Path:
    spec = config.get("technical_validation") or {}
    files = spec.get("files") or list(BUILD_FILES)
    patterns = compile_patterns(spec.get("patterns") or ["org\\.springframework\\.boot"])
    sample = rows[:sample_size]
    out_path = run_dir / "technical_validation_sample.csv"
    fields = [
        "repository_id",
        "full_name",
        "html_url",
        "spring_boot_evidence",
        "build_files_found",
        "validated_at",
    ]
    results: List[Dict[str, Any]] = []
    for index, row in enumerate(sample, 1):
        log(f"validate {index}/{len(sample)} {row['full_name']}")
        text = fetch_build_text(client, row["full_name"], files)
        results.append(
            {
                "repository_id": row.get("repository_id"),
                "full_name": row.get("full_name"),
                "html_url": row.get("html_url"),
                "spring_boot_evidence": has_spring_boot(text, patterns),
                "build_files_found": bool(text),
                "validated_at": utc_now_iso(),
            }
        )
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    positives = sum(1 for row in results if row["spring_boot_evidence"] is True)
    log(f"validacao tecnica: {positives}/{len(results)} com evidencia no build da raiz")
    return out_path
