#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 4: Consolidacao da Extracao CK e Filtro de Validade Longitudinal Completa
Responsabilidade:
- Consolidar as medicoes estaticas do CK 0.7.1-SNAPSHOT (commit 8a1ef916) sobre os
  607 repositorios aprovados nos 4 cenarios do RepoReaper.
- Aplicar o criterio de validade longitudinal do estudo: um repositorio so e valido
  para comparacao se possuir dados CK validos (status == 'ok') em TODAS as eras
  previstas para o seu grupo temporal:
  * Grupo Pioneiro (<= 2013): CK valido nas 4 eras (E1, E2, E3 e E4) -> 17 repositorios (68 snapshots)
  * Grupo Principal (2014-2017): CK valido nas 3 eras (E2, E3 e E4) -> 453 repositorios (1.359 snapshots)
- Materializar a amostra final de 470 repositorios validos (1.427 snapshots CK) e o
  resultado consolidado de deteccao de IA em E4 para esses 470 repositorios (75 com
  evidencia detectada e 395 sem evidencia detectada).
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


def run_ck_consolidation(
    sample_785_csv: Path,
    reporeaper_csv: Path,
    measurements_source_csv: Path,
    audit_785_csv: Path,
    output_valid_repos_csv: Path,
    output_valid_measurements_csv: Path,
    output_ia_valid_csv: Path,
    manifest_path: Path,
) -> Dict[str, Any]:
    print("[*] Etapa 4: Extracao CK e Filtro de Completude Longitudinal (470 Validos)")

    with open(sample_785_csv, "r", encoding="utf-8") as f:
        sample_by_id = {str(r["repository_id"]): r for r in csv.DictReader(f)}

    with open(reporeaper_csv, "r", encoding="utf-8") as f:
        reaper_by_id = {str(r["repository_id"]): r for r in csv.DictReader(f)}

    ia_by_id: Dict[str, str] = {}
    if audit_785_csv.exists():
        with open(audit_785_csv, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ia_by_id[str(r["repository_id"])] = str(r.get("ia_status_norm") or "sem_evidencia_detectada")

    meas_by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
    with open(measurements_source_csv, "r", encoding="utf-8") as f:
        meas_rows = list(csv.DictReader(f))
        meas_fields = list(meas_rows[0].keys()) if meas_rows else []
        for m in meas_rows:
            meas_by_key[(str(m["repository_id"]), str(m["era"]))] = m

    approved_ids = sorted(
        rid for rid, rr in reaper_by_id.items() if str(rr.get("approved", "")).lower() == "true"
    )

    valid_repos: List[Dict[str, Any]] = []
    valid_measurements: List[Dict[str, Any]] = []
    ia_rows: List[Dict[str, Any]] = []

    pioneer_valid = 0
    main_valid = 0
    missing_sha_excluded = 0
    clone_or_nojava_excluded = 0

    for rid in approved_ids:
        srow = sample_by_id[rid]
        is_pioneer = srow.get("created_at", "") < "2014-01-01T00:00:00Z"
        req_eras = ["E1", "E2", "E3", "E4"] if is_pioneer else ["E2", "E3", "E4"]

        all_ok = all(meas_by_key.get((rid, e), {}).get("status") == "ok" for e in req_eras)
        if not all_ok:
            has_all_shas = all(bool((meas_by_key.get((rid, e), {}).get("sha") or "").strip()) for e in req_eras)
            if not has_all_shas:
                missing_sha_excluded += 1
            else:
                clone_or_nojava_excluded += 1
            continue

        grupo = "pioneiro_2009_2013" if is_pioneer else "principal_2014_2017"
        if is_pioneer:
            pioneer_valid += 1
        else:
            main_valid += 1

        ia_status = ia_by_id.get(rid, "sem_evidencia_detectada")
        valid_repos.append({
            "repository_id": rid,
            "full_name": srow.get("full_name", ""),
            "stargazers_count": srow.get("stargazers_count", "0"),
            "created_at": srow.get("created_at", ""),
            "pushed_at": srow.get("pushed_at", ""),
            "grupo_temporal": grupo,
            "eras_validas": ";".join(req_eras),
            "ia_status_e4": ia_status,
        })

        ia_rows.append({
            "repository_id": rid,
            "full_name": srow.get("full_name", ""),
            "grupo_temporal": grupo,
            "sha_e4": meas_by_key[(rid, "E4")].get("sha", ""),
            "ia_status_e4": ia_status,
        })

        for e in req_eras:
            valid_measurements.append(meas_by_key[(rid, e)])

    output_valid_repos_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_valid_repos_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(valid_repos[0].keys()))
        writer.writeheader()
        writer.writerows(valid_repos)

    with open(output_valid_measurements_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=meas_fields)
        writer.writeheader()
        writer.writerows(valid_measurements)

    output_ia_valid_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_ia_valid_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ia_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ia_rows)

    ia_detected = sum(1 for r in ia_rows if r["ia_status_e4"] == "com_evidencia")
    ia_not_detected = sum(1 for r in ia_rows if r["ia_status_e4"] == "sem_evidencia_detectada")

    manifest = {
        "step": "04_extracao_ck_e_completude_longitudinal",
        "ck_version": "0.7.1-SNAPSHOT (commit 8a1ef916d597d33ad619d748b616bb7dbc3f0c36)",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "reporeaper_approved_evaluated": len(approved_ids),
        "excluded_incomplete_longitudinal": {
            "total": len(approved_ids) - len(valid_repos),
            "missing_commit_sha_in_intermediate_era": missing_sha_excluded,
            "clone_failure_or_no_measurable_java_classes": clone_or_nojava_excluded,
        },
        "valid_repositories_total": len(valid_repos),
        "pioneer_group_valid_e1_to_e4": pioneer_valid,
        "main_group_valid_e2_to_e4": main_valid,
        "valid_ck_snapshots_total": len(valid_measurements),
        "e4_ai_classification_on_470_valid": {
            "com_evidencia": ia_detected,
            "sem_evidencia_detectada": ia_not_detected,
        },
        "valid_repos_csv": str(output_valid_repos_csv),
        "valid_repos_sha256": _sha256_file(output_valid_repos_csv),
        "valid_measurements_csv": str(output_valid_measurements_csv),
        "valid_measurements_sha256": _sha256_file(output_valid_measurements_csv),
        "ia_valid_csv": str(output_ia_valid_csv),
        "ia_valid_sha256": _sha256_file(output_ia_valid_csv),
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(
        f"[+] Amostra final valida: {len(valid_repos)} repositorios "
        f"(Pioneiro E1-E4: {pioneer_valid}, Principal E2-E4: {main_valid}, "
        f"Snapshots CK: {len(valid_measurements)}, IA E4: {ia_detected} vs {ia_not_detected})"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 4: Consolidacao CK e Filtro Longitudinal (470 Validos).")
    parser.add_argument("--sample", type=Path, default=Path("pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv"))
    parser.add_argument("--reporeaper", type=Path, default=Path("pipeline_oficial_tcc/03_higienizacao_reporeaper/reporeaper_results.csv"))
    parser.add_argument("--measurements-src", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/measurements_785_candidatos.csv"))
    parser.add_argument("--audit-src", type=Path, default=Path("pipeline_oficial_tcc/03_higienizacao_reporeaper/auditoria_completa_785_4cenarios.csv"))
    parser.add_argument("--output-repos", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/repositorios_470_validos.csv"))
    parser.add_argument("--output-measurements", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/measurements_470_validos.csv"))
    parser.add_argument("--output-ia", type=Path, default=Path("pipeline_oficial_tcc/05_deteccao_ia/resultado_deteccao_ia_470_validos.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/ck_manifest.json"))
    args = parser.parse_args()

    run_ck_consolidation(
        sample_785_csv=args.sample,
        reporeaper_csv=args.reporeaper,
        measurements_source_csv=args.measurements_src,
        audit_785_csv=args.audit_src,
        output_valid_repos_csv=args.output_repos,
        output_valid_measurements_csv=args.output_measurements,
        output_ia_valid_csv=args.output_ia,
        manifest_path=args.manifest,
    )


if __name__ == "__main__":
    main()
