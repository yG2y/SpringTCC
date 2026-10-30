#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 1: Coleta, Descoberta e Filtragem de Metadados (Sem Filtro de Estrelas)
Responsabilidade:
- Partir dos 95.894 registros únicos de population.csv (execução 20260920_java).
- Aplicar filtros sequenciais e determinísticos de metadados:
  1. Linguagem principal Java
  2. Exclusão de forks, espelhos, arquivados e desabilitados
  3. Janela de atividade na Era E4: pushed_at >= 2022-01-01T00:00:00Z
  4. Exclusão de templates e repositórios vazios/sem branch padrão
  5. Exclusão pelas heurísticas automáticas iniciais de tópicos/prefixos escolares
- Nenhum filtro por número de estrelas é aplicado (a relevância é aferida pelo RepoReaper).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

AUTO_TOPICS = {
    "tutorial", "tutorials", "course", "courses", "workshop", "workshops",
    "bootcamp", "bootcamps", "cheatsheet", "cheat-sheet", "cheat-sheets",
    "awesome-list", "awesome", "slides", "slideshow", "lecture", "lectures",
    "mooc", "udemy", "exercism",
}

AUTO_NAME_PATTERNS = [
    re.compile(r"^awesome-.+", re.I),
    re.compile(r".+-(course|tutorial|workshops?|bootcamps?|cheatsheets?|slides)$", re.I),
    re.compile(r"^(course|tutorial|workshop|bootcamp)-.+", re.I),
]


def is_auto_non_software(name: str, topics: str) -> bool:
    t_set = {t.strip().lower() for t in topics.split(";") if t.strip()}
    if t_set.intersection(AUTO_TOPICS):
        return True
    repo_short = name.split("/")[-1] if "/" in name else name
    return any(pat.match(repo_short) for pat in AUTO_NAME_PATTERNS)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_repositories(
    input_csv: Path,
    output_csv: Path,
    manifest_path: Path,
    pushed_at_start: str = "2022-01-01T00:00:00Z",
) -> Dict[str, Any]:
    print("[*] Etapa 1: Filtragem de Metadados (Sem Filtro de Estrelas)")
    print(f"    - Entrada: {input_csv}")
    print(f"    - Janela E4: pushed_at >= {pushed_at_start}")

    with open(input_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    exclusions: Dict[str, int] = defaultdict(int)
    eligible: List[Dict[str, Any]] = []

    for r in rows:
        lang = r.get("primary_language") or r.get("language") or ""
        if lang != "Java":
            exclusions["1_not_java"] += 1
            continue
        if str(r.get("is_fork", "")).lower() in ("true", "1"):
            exclusions["2_fork"] += 1
            continue
        if str(r.get("is_mirror", "")).lower() in ("true", "1") or r.get("mirror_url"):
            exclusions["3_mirror"] += 1
            continue
        if str(r.get("archived", "")).lower() in ("true", "1"):
            exclusions["4_archived"] += 1
            continue
        if str(r.get("disabled", "")).lower() in ("true", "1"):
            exclusions["5_disabled"] += 1
            continue
        pushed = r.get("pushed_at", "")
        if not pushed or pushed < pushed_at_start:
            exclusions["6_inactive_before_2022"] += 1
            continue
        if str(r.get("is_template", "")).lower() in ("true", "1"):
            exclusions["7_template"] += 1
            continue
        try:
            size = int(r.get("size_kb", 0))
        except ValueError:
            size = 0
        if size <= 0 or not r.get("default_branch"):
            exclusions["8_empty_or_no_branch"] += 1
            continue
        if is_auto_non_software(r.get("full_name", ""), r.get("topics", "")):
            exclusions["9_auto_educational"] += 1
            continue
        eligible.append(r)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(eligible)

    manifest = {
        "step": "01_coleta_descoberta",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_dataset": str(input_csv),
        "input_sha256": _sha256_file(input_csv),
        "star_filter": "none",
        "pushed_at_cutoff": pushed_at_start,
        "total_repositories_evaluated": len(rows),
        "exclusions_by_reason": dict(sorted(exclusions.items())),
        "total_excluded": sum(exclusions.values()),
        "eligible_active_e4_count": len(eligible),
        "output_file": str(output_csv),
        "output_sha256": _sha256_file(output_csv),
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Concluido! Retidos ativos em E4: {len(eligible)} de {len(rows)}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 1: Filtragem de Metadados sem Filtro de Estrelas.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/population.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pipeline_oficial_tcc/01_coleta_descoberta/repositorios_coletados.csv"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("pipeline_oficial_tcc/01_coleta_descoberta/coleta_manifest.json"),
    )
    parser.add_argument(
        "--pushed-at-start",
        type=str,
        default="2022-01-01T00:00:00Z",
    )
    args = parser.parse_args()
    filter_repositories(args.input, args.output, args.manifest, args.pushed_at_start)


if __name__ == "__main__":
    main()
