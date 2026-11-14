#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 4b: Filtro de completude longitudinal (painel balanceado).

Le as medicoes por snapshot produzidas por `extrair_snapshots_ck_ia.py` e a curadoria
de `reporeaper_curation.py`. Um repositorio aprovado na curadoria so integra a amostra
final se tiver extracao CK valida (status == 'ok') em TODAS as eras previstas para o
seu grupo temporal, sem substituicao:
  * Grupo Pioneiro (criados ate 2013): E1, E2, E3 e E4;
  * Grupo Principal (criados entre 2014 e 2017): E2, E3 e E4.

Nenhum valor e imputado: snapshot ausente, falha de recuperacao, ausencia de classes
Java ou extracao parcial excluem o repositorio, e o motivo fica registrado no manifesto.
Saidas: `repositorios_validos.csv`, `measurements_validos.csv` e `ck_manifest.json`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

MOTIVOS = {
    "missing_snapshot": "sem_commit_na_linha_principal_em_alguma_era",
    "temporal_anomaly": "anomalia_temporal_no_historico",
    "retrieval_error": "falha_de_clonagem_ou_historico",
    "no_java": "sem_classes_java_mensuraveis",
    "partial_ck": "extracao_ck_parcial",
    "error": "erro_de_extracao_ck",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_completude(
    sample_785_csv: Path,
    reporeaper_csv: Path,
    measurements_csv: Path,
    output_valid_repos_csv: Path,
    output_valid_measurements_csv: Path,
    manifest_path: Path,
) -> Dict[str, Any]:
    print("[*] Etapa 4b: Completude Longitudinal (painel balanceado)")

    with open(sample_785_csv, "r", encoding="utf-8") as f:
        sample_by_id = {str(r["repository_id"]): r for r in csv.DictReader(f)}
    with open(reporeaper_csv, "r", encoding="utf-8") as f:
        approved_ids = sorted(
            (str(r["repository_id"]) for r in csv.DictReader(f) if str(r.get("approved", "")).lower() == "true"),
            key=int,
        )
    with open(measurements_csv, "r", encoding="utf-8") as f:
        meas_rows = list(csv.DictReader(f))
    meas_fields = list(meas_rows[0].keys())
    meas = {(str(m["repository_id"]), str(m["era"])): m for m in meas_rows}

    valid_repos: List[Dict[str, Any]] = []
    valid_measurements: List[Dict[str, Any]] = []
    exclusoes: Counter = Counter()

    for rid in approved_ids:
        srow = sample_by_id[rid]
        pioneiro = srow["created_at"] < "2014-01-01T00:00:00Z"
        req = ["E1", "E2", "E3", "E4"] if pioneiro else ["E2", "E3", "E4"]
        status = [meas.get((rid, e), {}).get("status", "retrieval_error") for e in req]
        falha = next((s for s in status if s != "ok"), None)
        if falha:
            exclusoes[MOTIVOS.get(falha, falha)] += 1
            continue
        e3, e4 = meas[(rid, "E3")], meas[(rid, "E4")]
        valid_repos.append({
            "repository_id": rid,
            "full_name": srow.get("full_name", ""),
            "stargazers_count": srow.get("stargazers_count", "0"),
            "created_at": srow.get("created_at", ""),
            "pushed_at": srow.get("pushed_at", ""),
            "grupo_temporal": "pioneiro_2009_2013" if pioneiro else "principal_2014_2017",
            "eras_validas": ";".join(req),
            "sha_e4": e4["sha"],
            "e4_mesmo_sha_de_e3": e4["sha"] == e3["sha"],
            "ia_status_e4": e4["ia_status"],
        })
        valid_measurements.extend(meas[(rid, e)] for e in req)

    output_valid_repos_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_valid_repos_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(valid_repos[0].keys()))
        writer.writeheader()
        writer.writerows(valid_repos)
    with open(output_valid_measurements_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=meas_fields)
        writer.writeheader()
        writer.writerows(valid_measurements)

    pion = sum(1 for r in valid_repos if r["grupo_temporal"].startswith("pioneiro"))
    ia = Counter(r["ia_status_e4"] for r in valid_repos)
    manifest = {
        "step": "04b_completude_longitudinal",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "measurements_source": str(measurements_csv),
        "measurements_source_sha256": _sha256_file(measurements_csv),
        "reporeaper_approved_evaluated": len(approved_ids),
        "excluded_incomplete_longitudinal": {"total": len(approved_ids) - len(valid_repos),
                                             **dict(sorted(exclusoes.items()))},
        "valid_repositories_total": len(valid_repos),
        "pioneer_group_valid_e1_to_e4": pion,
        "main_group_valid_e2_to_e4": len(valid_repos) - pion,
        "valid_ck_snapshots_total": len(valid_measurements),
        "valid_with_e4_sha_equal_e3": sum(1 for r in valid_repos if r["e4_mesmo_sha_de_e3"]),
        "e4_ai_classification_on_valid": dict(sorted(ia.items())),
        "valid_repos_csv": str(output_valid_repos_csv),
        "valid_repos_sha256": _sha256_file(output_valid_repos_csv),
        "valid_measurements_csv": str(output_valid_measurements_csv),
        "valid_measurements_sha256": _sha256_file(output_valid_measurements_csv),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Amostra final valida: {len(valid_repos)} repositorios (Pioneiro E1-E4: {pion}, "
          f"Principal E2-E4: {len(valid_repos) - pion}, Snapshots CK: {len(valid_measurements)}, "
          f"IA E4: {dict(ia)})")
    return manifest


def main() -> None:
    base = Path("pipeline_oficial_tcc")
    parser = argparse.ArgumentParser(description="Etapa 4b: filtro de completude longitudinal.")
    parser.add_argument("--sample", type=Path, default=base / "02_coortes_e_shas/sample_785.csv")
    parser.add_argument("--reporeaper", type=Path, default=base / "03_higienizacao_reporeaper/reporeaper_results.csv")
    parser.add_argument("--measurements-src", type=Path, default=base / "04_extracao_ck/measurements_785_candidatos.csv")
    parser.add_argument("--output-repos", type=Path, default=base / "04_extracao_ck/repositorios_validos.csv")
    parser.add_argument("--output-measurements", type=Path, default=base / "04_extracao_ck/measurements_validos.csv")
    parser.add_argument("--manifest", type=Path, default=base / "04_extracao_ck/ck_manifest.json")
    args = parser.parse_args()
    run_completude(args.sample, args.reporeaper, args.measurements_src,
                   args.output_repos, args.output_measurements, args.manifest)


if __name__ == "__main__":
    main()
