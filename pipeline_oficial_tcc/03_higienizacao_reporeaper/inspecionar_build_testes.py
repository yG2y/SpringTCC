#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 3a: Inspecao real dos criterios C3 (build) e C4 (testes) nos 785 candidatos.

Os criterios sao apurados sobre a arvore de arquivos do ESTADO ATUAL do repositorio
(o mesmo snapshot usado em E4), listada com `git ls-tree -r --name-only`:
- C3 (automacao de build): existe arquivo chamado pom.xml, build.gradle ou
  build.gradle.kts em qualquer diretorio;
- C4 (testes automatizados): existe caminho contendo `src/test` ou arquivo terminado
  em `Test.java` / `Tests.java` (comparacao sem diferenciar maiusculas).

Fonte da arvore: o clone fixado da execucao oficial de extracao
(`extrair_snapshots_ck_ia.py`), no commit de referencia (tip) registrado em
`repositories/<id>/reference.json`, que e o snapshot de E4. Repositorio sem clone
(falha de recuperacao) fica como `indisponivel` e nao comprova C3/C4.

Nenhum resultado de CK ou de IA e consultado. A saida `evidencias_build_testes.csv`
registra, por repositorio, a fonte, o SHA inspecionado e um caminho de exemplo que
comprova cada criterio; `reporeaper_curation.py` le esse arquivo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")
FIELDS = [
    "repository_id", "full_name", "fonte", "sha_inspecionado", "status",
    "c3_ok", "c3_evidencia", "c4_ok", "c4_evidencia",
]


def _git(repo: Path, *args: str, timeout: int = 600) -> Tuple[int, str]:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, errors="replace", timeout=timeout, env=env,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        return 124, ""


def avaliar_arvore(paths: List[str]) -> Dict[str, Any]:
    """Aplica C3 e C4 a uma lista de caminhos do repositorio."""
    build = sorted(p for p in paths if p.rsplit("/", 1)[-1].lower() in BUILD_FILES)
    tests = sorted(
        p for p in paths
        if "src/test" in p.lower() or p.lower().endswith(("test.java", "tests.java"))
    )
    return {
        "c3_ok": bool(build), "c3_evidencia": build[0] if build else "",
        "c4_ok": bool(tests), "c4_evidencia": tests[0] if tests else "",
    }


def _listar(repo: Path, ref: str) -> Optional[List[str]]:
    code, out = _git(repo, "ls-tree", "-r", "--name-only", ref)
    return out.splitlines() if code == 0 else None


def inspecionar(row: Dict[str, str], run_dir: Path) -> Dict[str, Any]:
    rid, full_name = str(row["repository_id"]), row["full_name"]
    base = {"repository_id": rid, "full_name": full_name}
    referencia = run_dir / "repositories" / rid / "reference.json"
    clone = run_dir / "clones" / rid
    if referencia.is_file() and clone.exists():
        tip = json.loads(referencia.read_text())["tip"]
        paths = _listar(clone, tip)
        if paths is not None:
            return {**base, "fonte": "clone_fixado", "sha_inspecionado": tip,
                    "status": "ok", **avaliar_arvore(paths)}
    return {**base, "fonte": "indisponivel", "sha_inspecionado": "", "status": "indisponivel",
            "c3_ok": "", "c3_evidencia": "", "c4_ok": "", "c4_evidencia": ""}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 3a: inspecao real de build (C3) e testes (C4).")
    parser.add_argument("--sample", type=Path, default=Path("pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv"))
    parser.add_argument("--run-dir", type=Path, default=Path(
        "Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261113_pipeline_oficial_785"))
    parser.add_argument("--output", type=Path, default=Path(
        "pipeline_oficial_tcc/03_higienizacao_reporeaper/evidencias_build_testes.csv"))
    parser.add_argument("--manifest", type=Path, default=Path(
        "pipeline_oficial_tcc/03_higienizacao_reporeaper/evidencias_build_testes_manifest.json"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    with open(args.sample, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[*] Etapa 3a: inspecionando build e testes em {len(rows)} candidatos")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda r: inspecionar(r, args.run_dir), rows))
    results.sort(key=lambda r: int(r["repository_id"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    def conta(chave: str, valor: Any) -> int:
        return sum(1 for r in results if r[chave] == valor)

    manifest = {
        "step": "03a_inspecao_build_testes",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "rule": "C3 e C4 apurados na arvore do estado atual do repositorio (snapshot de E4)",
        "c3_build_files": list(BUILD_FILES),
        "c4_test_markers": ["src/test", "*Test.java", "*Tests.java"],
        "total_candidates": len(results),
        "by_source": {k: conta("fonte", k) for k in ("clone_fixado", "indisponivel")},
        "c3_ok": conta("c3_ok", True),
        "c4_ok": conta("c4_ok", True),
        "output_csv": str(args.output),
        "output_sha256": _sha256_file(args.output),
    }
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"[+] Fontes: {manifest['by_source']} | C3 ok: {manifest['c3_ok']} | C4 ok: {manifest['c4_ok']}")


if __name__ == "__main__":
    main()
