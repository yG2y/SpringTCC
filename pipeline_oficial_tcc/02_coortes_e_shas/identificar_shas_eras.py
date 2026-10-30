#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 2: Corte Temporal de Criacao (<= 2017), Divisao em Grupos Temporais e Mapeamento de SHAs
Responsabilidade:
- Filtrar os repositorios criados ate 31/12/2017 UTC (created_at < 2018-01-01T00:00:00Z)
  sem filtro de estrelas -> 785 candidatos.
- Organizar nos dois grupos temporais:
  1. Grupo Pioneiro (22 candidatos criados ate 2013): eras previstas E1, E2, E3 e E4.
  2. Grupo Principal (763 candidatos criados entre 2014 e 2017): eras previstas E2, E3 e E4.
- Consolidar o mapeamento deterministico dos SHAs historicos por era.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_group_and_sha_mapping(
    input_repositories_csv: Path,
    measurements_reference_csv: Path,
    output_sample_csv: Path,
    output_shas_csv: Path,
    manifest_path: Path,
) -> Dict[str, Any]:
    print("[*] Etapa 2: Corte Temporal (<= 2017), Grupos Temporais e SHAs por Era")
    with open(input_repositories_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    candidates: List[Dict[str, Any]] = []
    pioneer_group: List[Dict[str, Any]] = []
    main_group: List[Dict[str, Any]] = []

    for row in rows:
        created = row.get("created_at", "")
        if created and created < "2018-01-01T00:00:00Z":
            is_pioneer = created < "2014-01-01T00:00:00Z"
            row_copy = dict(row)
            row_copy["grupo_temporal"] = "pioneiro_2009_2013" if is_pioneer else "principal_2014_2017"
            candidates.append(row_copy)
            if is_pioneer:
                pioneer_group.append(row_copy)
            else:
                main_group.append(row_copy)

    output_sample_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_sample_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = list(candidates[0].keys()) if candidates else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    candidate_ids = {str(r["repository_id"]): r for r in candidates}
    sha_records: List[Dict[str, Any]] = []

    if measurements_reference_csv.exists():
        with open(measurements_reference_csv, "r", encoding="utf-8") as f:
            for mrow in csv.DictReader(f):
                rid = str(mrow.get("repository_id", ""))
                if rid not in candidate_ids:
                    continue
                era = str(mrow.get("era", ""))
                is_pioneer = candidate_ids[rid]["grupo_temporal"] == "pioneiro_2009_2013"
                if era == "E1" and not is_pioneer:
                    continue
                if era not in ("E1", "E2", "E3", "E4"):
                    continue
                sha_records.append({
                    "repository_id": rid,
                    "full_name": candidate_ids[rid].get("full_name", ""),
                    "grupo_temporal": candidate_ids[rid]["grupo_temporal"],
                    "era": era,
                    "sha": mrow.get("sha", ""),
                    "status": mrow.get("status", ""),
                })

    with open(output_shas_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["repository_id", "full_name", "grupo_temporal", "era", "sha", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sha_records)

    manifest = {
        "step": "02_grupos_temporais_e_shas",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "creation_cutoff": "created_at < 2018-01-01T00:00:00Z",
        "total_candidates": len(candidates),
        "pioneer_group_count": len(pioneer_group),
        "main_group_count": len(main_group),
        "stars_lt_10": sum(1 for r in candidates if int(r.get("stargazers_count") or 0) < 10),
        "stars_ge_10": sum(1 for r in candidates if int(r.get("stargazers_count") or 0) >= 10),
        "total_sha_records_mapped": len(sha_records),
        "sample_csv": str(output_sample_csv),
        "sample_sha256": _sha256_file(output_sample_csv),
        "shas_csv": str(output_shas_csv),
        "shas_sha256": _sha256_file(output_shas_csv),
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Candidatos ate 2017: {len(candidates)} (Pioneiro: {len(pioneer_group)}, Principal: {len(main_group)})")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 2: Grupos Temporais e SHAs por Era.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("pipeline_oficial_tcc/01_coleta_descoberta/repositorios_coletados.csv"),
    )
    parser.add_argument(
        "--measurements-ref",
        type=Path,
        default=Path("pipeline_oficial_tcc/04_extracao_ck/measurements_785_candidatos.csv"),
    )
    parser.add_argument(
        "--output-sample",
        type=Path,
        default=Path("pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv"),
    )
    parser.add_argument(
        "--output-shas",
        type=Path,
        default=Path("pipeline_oficial_tcc/02_coortes_e_shas/shas_mapeados_por_era.csv"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("pipeline_oficial_tcc/02_coortes_e_shas/coortes_manifest.json"),
    )
    args = parser.parse_args()
    run_group_and_sha_mapping(
        args.input,
        args.measurements_ref,
        args.output_sample,
        args.output_shas,
        args.manifest,
    )


if __name__ == "__main__":
    main()
