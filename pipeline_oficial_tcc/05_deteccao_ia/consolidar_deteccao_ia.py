#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 5: Consolidacao da deteccao de vestigios de IA nos repositorios validos.

A deteccao em si e feita por snapshot em `04_extracao_ck/extrair_snapshots_ck_ia.py`,
que inspeciona (a) arquivos e diretorios de configuracao de agentes e entradas
correlatas em `.gitignore` presentes na arvore do snapshot e (b) identidades de bots e
trailers `Co-authored-by` de commits alcancaveis no historico Git ate o snapshot.
Este script apenas reune, para cada repositorio valido, o status em cada era e os
agentes e tipos de sinal observados em E4.

Ausencia de vestigio nao comprova ausencia de uso de IA, e o primeiro registro
versionado nao data o inicio do uso.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ERAS = ["E1", "E2", "E3", "E4"]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    base = Path("pipeline_oficial_tcc")
    parser = argparse.ArgumentParser(description="Etapa 5: consolidacao da deteccao de IA nos validos.")
    parser.add_argument("--valid-repos", type=Path, default=base / "04_extracao_ck/repositorios_validos.csv")
    parser.add_argument("--valid-measurements", type=Path, default=base / "04_extracao_ck/measurements_validos.csv")
    parser.add_argument("--output", type=Path, default=base / "05_deteccao_ia/resultado_deteccao_ia_validos.csv")
    parser.add_argument("--manifest", type=Path, default=base / "05_deteccao_ia/deteccao_ia_manifest.json")
    args = parser.parse_args()

    with open(args.valid_repos, "r", encoding="utf-8") as f:
        repos = list(csv.DictReader(f))
    with open(args.valid_measurements, "r", encoding="utf-8") as f:
        meas = {(r["repository_id"], r["era"]): r for r in csv.DictReader(f)}

    linhas = []
    for r in repos:
        rid = r["repository_id"]
        e4 = meas[(rid, "E4")]
        linha = {"repository_id": rid, "full_name": r["full_name"], "grupo_temporal": r["grupo_temporal"],
                 "sha_e4": e4["sha"]}
        for era in ERAS:
            linha[f"ia_status_{era.lower()}"] = meas[(rid, era)]["ia_status"] if (rid, era) in meas else ""
        linha.update(ia_arquivo_ou_gitignore_no_snapshot_e4=e4["ia_present"],
                     ia_commits_ate_o_snapshot_e4=e4["ia_history"],
                     ia_agentes_e4=e4["ia_agentes"], ia_tipos_de_sinal_e4=e4["ia_tipos_de_sinal"])
        linhas.append(linha)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    manifest = {
        "step": "05_deteccao_ia",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "method": "arquivos e .gitignore no snapshot; bots e trailers Co-authored-by no historico ate o snapshot",
        "valid_repositories": len(linhas),
        "status_by_era": {era: dict(sorted(Counter(l[f"ia_status_{era.lower()}"] for l in linhas
                                                   if l[f"ia_status_{era.lower()}"]).items())) for era in ERAS},
        "e4_signal_types": dict(sorted(Counter(
            t for l in linhas for t in l["ia_tipos_de_sinal_e4"].split("; ") if t).items())),
        "e4_agents": dict(sorted(Counter(
            a for l in linhas for a in l["ia_agentes_e4"].split("; ") if a).items())),
        "output_csv": str(args.output),
        "output_sha256": _sha256_file(args.output),
    }
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"[+] IA por era nos {len(linhas)} validos: {manifest['status_by_era']}")


if __name__ == "__main__":
    main()
