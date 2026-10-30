#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instrumento Local de Higienizacao de Repositorios baseado no RepoReaper (4 Cenarios)
Referencia conceitual: Munaiah et al. (2017) - "Curating GitHub for engineered software projects"
                       Empirical Software Engineering, 22(6), 3219-3253.
                       DOI: 10.1007/s10664-017-9512-6
                       Projeto Oficial: https://github.com/reporeapers/reaper

Este script operacionaliza integralmente em ambiente local a curadoria de relevancia
dos repositorios candidatos do TCC (substituindo cortes arbitrarios por numero de
estrelas), exigindo aprovacao simultanea nos quatro cenarios complementares:
1. Cenario C1 (Curadoria de Finalidade Didatica Estrita):
   Exclusao de repositorios voltados a ensino, tarefas academicas ou tutoriais
   (course, homework, assignment, learning, tutorial, exercicio, exercicios, aula,
   curso, treinamento, udemy, mooc, exercism, lecture). Termos tecnicos de dominio
   como 'machine-learning' e 'deep-learning' sao preservados.
2. Cenario C2 Ajustado (Curadoria de Projetos Brinquedo e Efemeros, flexibilizada
   para especificidades do ecossistema Spring Boot):
   Exclusao de sandboxes, rascunhos de pratica e esqueletos descartaveis
   (playground, sandbox, toy, practice, boilerplate, cheatsheet, cheat-sheet, slides).
   Os termos 'demo', 'sample' e 'example' (e plurais) sao deliberadamente excluidos da
   penalizacao porque o Spring Initializr adota 'demo' como identificador padrao e a
   comunidade corporativa Java/Spring nomeia arquiteturas reais de referencia com
   'sample' e 'example'.
3. Cenario C3 (Arquitetura de Build Padronizada):
   Presenca comprovada de descritores formais de automacao de compilacao do ecossistema
   Java/Spring (pom.xml, build.gradle ou build.gradle.kts).
4. Cenario C4 (Engenharia de Testes Automatizados):
   Presenca comprovada de estrutura ou classes de testes automatizados (src/test ou
   arquivos *Test.java / *Tests.java).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DIDACTIC_KEYWORDS = [
    "course",
    "homework",
    "assignment",
    "learning",
    "tutorial",
    "exercicio",
    "exercicios",
    "aula",
    "curso",
    "treinamento",
    "udemy",
    "mooc",
    "exercism",
    "lecture",
]

TOY_KEYWORDS_ADJUSTED = [
    "playground",
    "sandbox",
    "toy",
    "practice",
    "boilerplate",
    "cheatsheet",
    "cheat-sheet",
    "slides",
]

BUILD_FILES = [
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
]


def _parse_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "sim"):
        return True
    if text in ("false", "0", "no", "nao", ""):
        return False
    return None


def evaluate_c1_didactic(name: str, description: str, topics: str) -> Tuple[bool, List[str]]:
    full_text = f"{name} {description} {topics}".lower()
    cleaned_text = re.sub(r"\b(machine|deep)[\s_-]learning\b", "", full_text, flags=re.I)
    flags = [kw for kw in DIDACTIC_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", cleaned_text)]
    return len(flags) == 0, flags


def evaluate_c2_toy_adjusted(name: str, description: str, topics: str) -> Tuple[bool, List[str]]:
    full_text = f"{name} {description} {topics}".lower()
    flags = [kw for kw in TOY_KEYWORDS_ADJUSTED if re.search(rf"\b{re.escape(kw)}\b", full_text)]
    return len(flags) == 0, flags


def evaluate_repository_reaper(
    repo_data: Dict[str, Any],
    repo_path: Optional[Path] = None,
    build_test_hint: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    repo_id = str(repo_data.get("repository_id", ""))
    full_name = str(repo_data.get("full_name", ""))
    description = str(repo_data.get("description", ""))
    topics = str(repo_data.get("topics", ""))

    c1_ok, c1_flags = evaluate_c1_didactic(full_name, description, topics)
    c2_ok, c2_flags = evaluate_c2_toy_adjusted(full_name, description, topics)

    has_build = False
    has_tests = False

    if repo_path and repo_path.exists():
        for root, _, files in os.walk(repo_path):
            norm_root = root.replace("\\", "/").lower()
            if "/.git" in norm_root or norm_root.endswith("/.git"):
                continue
            if "src/test" in norm_root:
                has_tests = True
            for fname in files:
                f_lower = fname.lower()
                if f_lower in BUILD_FILES:
                    has_build = True
                if f_lower.endswith("test.java") or f_lower.endswith("tests.java"):
                    has_tests = True
            if has_build and has_tests:
                break
    else:
        if build_test_hint:
            has_build = bool(build_test_hint.get("has_build", False))
            has_tests = bool(build_test_hint.get("has_tests", False))

        for b_key in ("c3_ok", "has_build_tool", "has_build", "framework_confirmed"):
            if _parse_bool(repo_data.get(b_key)) is True:
                has_build = True

        for t_key in ("c4_ok", "has_automated_tests", "has_tests"):
            if _parse_bool(repo_data.get(t_key)) is True:
                has_tests = True

        if not has_tests:
            for num_key in ("test_n_cbo", "test_classes", "test_loc", "test_java_files"):
                raw_val = repo_data.get(num_key)
                if raw_val not in (None, ""):
                    try:
                        if float(raw_val) > 0:
                            has_tests = True
                            break
                    except ValueError:
                        pass

    c3_ok = has_build
    c4_ok = has_tests
    is_approved = c1_ok and c2_ok and c3_ok and c4_ok

    reasons: List[str] = []
    if not c1_ok:
        reasons.extend(f"c1_didactic:{kw}" for kw in c1_flags)
    if not c2_ok:
        reasons.extend(f"c2_toy_adjusted:{kw}" for kw in c2_flags)
    if not c3_ok:
        reasons.append("c3_missing_maven_or_gradle_build")
    if not c4_ok:
        reasons.append("c4_missing_automated_tests")
    if is_approved:
        reasons.append("approved_all_4_scenarios")

    return {
        "repository_id": repo_id,
        "full_name": full_name,
        "c1_ok": c1_ok,
        "c1_flags": ";".join(c1_flags),
        "c2_ok": c2_ok,
        "c2_flags": ";".join(c2_flags),
        "c3_ok": c3_ok,
        "c4_ok": c4_ok,
        "is_didactic": not c1_ok,
        "is_toy_adjusted": not c2_ok,
        "has_build_tool": c3_ok,
        "has_automated_tests": c4_ok,
        "approved": is_approved,
        "reasons": ";".join(reasons),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_reporeaper_curation(
    input_csv: Path,
    output_dir: Path,
    repos_dir: Optional[Path] = None,
    required_eras: Optional[List[str]] = None,
    measurements_csv: Optional[Path] = None,
    audit_hint_csv: Optional[Path] = Path("pipeline_oficial_tcc/03_higienizacao_reporeaper/auditoria_completa_785_4cenarios.csv"),
    population_csv: Optional[Path] = Path(
        "Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/population.csv"
    ),
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []

    print(f"[*] Lendo candidatos de: {input_csv}")
    with open(input_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[*] Total de candidatos lidos: {len(rows)}")

    if rows and ("description" not in rows[0] or "topics" not in rows[0]):
        if population_csv and population_csv.exists():
            pop_meta: Dict[str, Tuple[str, str]] = {}
            with open(population_csv, "r", encoding="utf-8") as pf:
                for prow in csv.DictReader(pf):
                    pid = str(prow.get("repository_id", ""))
                    if pid:
                        pop_meta[pid] = (
                            str(prow.get("description") or ""),
                            str(prow.get("topics") or ""),
                        )
            for r in rows:
                rid = str(r.get("repository_id", ""))
                if rid in pop_meta:
                    desc, top = pop_meta[rid]
                    if not r.get("description"):
                        r["description"] = desc
                    if not r.get("topics"):
                        r["topics"] = top

    repo_shas: Dict[str, Set[str]] = {}
    bt_hints: Dict[str, Dict[str, bool]] = {}

    if audit_hint_csv and audit_hint_csv.exists():
        with open(audit_hint_csv, "r", encoding="utf-8") as af:
            for arow in csv.DictReader(af):
                rid = str(arow.get("repository_id", ""))
                hint = bt_hints.setdefault(rid, {"has_build": False, "has_tests": False})
                if _parse_bool(arow.get("c3_ok")) is True:
                    hint["has_build"] = True
                if _parse_bool(arow.get("c4_ok")) is True:
                    hint["has_tests"] = True

    if measurements_csv and measurements_csv.exists():
        with open(measurements_csv, "r", encoding="utf-8") as f:
            for mrow in csv.DictReader(f):
                rid = str(mrow.get("repository_id", ""))
                era = str(mrow.get("era", ""))
                sha = (mrow.get("sha") or "").strip()
                if sha:
                    repo_shas.setdefault(rid, set()).add(era)
                hint = bt_hints.setdefault(rid, {"has_build": False, "has_tests": False})
                if _parse_bool(mrow.get("framework_confirmed")) is True or _parse_bool(mrow.get("has_build")) is True:
                    hint["has_build"] = True
                for num_key in ("test_loc", "test_java_files", "test_n_cbo", "test_classes"):
                    val = mrow.get(num_key)
                    if val not in (None, ""):
                        try:
                            if float(val) > 0:
                                hint["has_tests"] = True
                        except ValueError:
                            pass

    if required_eras and repo_shas:
        req_set = set(required_eras)
        rows = [r for r in rows if req_set.issubset(repo_shas.get(str(r.get("repository_id", "")), set()))]

    c1_count = c2_count = c3_count = c4_count = approved_count = 0

    for row in rows:
        repo_id = str(row.get("repository_id", ""))
        full_name = str(row.get("full_name", ""))
        repo_path = (repos_dir / full_name.replace("/", "__")) if repos_dir else None

        evaluation = evaluate_repository_reaper(row, repo_path=repo_path, build_test_hint=bt_hints.get(repo_id))
        results.append(evaluation)

        c1_count += int(evaluation["c1_ok"])
        c2_count += int(evaluation["c2_ok"])
        c3_count += int(evaluation["c3_ok"])
        c4_count += int(evaluation["c4_ok"])
        approved_count += int(evaluation["approved"])

    total_candidates = len(results)
    rejected_count = total_candidates - approved_count

    output_csv = output_dir / "reporeaper_results.csv"
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "repository_id",
            "full_name",
            "c1_ok",
            "c1_flags",
            "c2_ok",
            "c2_flags",
            "c3_ok",
            "c4_ok",
            "is_didactic",
            "is_toy_adjusted",
            "has_build_tool",
            "has_automated_tests",
            "approved",
            "reasons",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    script_path = Path(__file__).resolve()
    manifest = {
        "tool": "RepoReaper Local Curation Instrument (4 Scenarios: C1 + C2 Adjusted + C3 + C4)",
        "reference": "Munaiah et al. (2017) DOI: 10.1007/s10664-017-9512-6",
        "script_sha256": _sha256_file(script_path),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_dataset": str(input_csv),
        "input_sha256": _sha256_file(input_csv),
        "parameters": {
            "c1_didactic_keywords": DIDACTIC_KEYWORDS,
            "c2_toy_keywords_adjusted": TOY_KEYWORDS_ADJUSTED,
            "c2_spring_boot_exempted_terms": ["demo", "demos", "sample", "samples", "example", "examples"],
            "c3_build_descriptors": BUILD_FILES,
            "c4_automated_test_markers": ["src/test", "*Test.java", "*Tests.java"],
        },
        "required_eras_filter": required_eras,
        "total_candidates_evaluated": total_candidates,
        "scenario_approvals": {
            "c1_non_didactic": c1_count,
            "c2_non_toy_spring_adjusted": c2_count,
            "c3_standard_build": c3_count,
            "c4_automated_tests": c4_count,
            "all_4_jointly": approved_count,
        },
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "approval_rate_percent": round(100.0 * approved_count / total_candidates, 2) if total_candidates else 0.0,
        "output_results_csv": str(output_csv),
        "output_results_sha256": _sha256_file(output_csv),
    }

    manifest_path = output_dir / "reporeaper_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Aprovados nos 4 cenarios juntos: {approved_count} de {total_candidates} ({manifest['approval_rate_percent']}%)")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Higienizacao local em 4 cenarios baseada no RepoReaper (Munaiah et al., 2017)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pipeline_oficial_tcc/03_higienizacao_reporeaper"),
    )
    parser.add_argument(
        "--repos-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--eras",
        nargs="*",
        default=None,
    )
    parser.add_argument(
        "--measurements",
        type=Path,
        default=Path("pipeline_oficial_tcc/04_extracao_ck/measurements_785_candidatos.csv"),
    )

    args = parser.parse_args()
    if not args.input.exists():
        print(f"[!] Erro: arquivo de entrada nao encontrado: {args.input}", file=sys.stderr)
        sys.exit(1)

    run_reporeaper_curation(
        input_csv=args.input,
        output_dir=args.output_dir,
        repos_dir=args.repos_dir,
        required_eras=args.eras,
        measurements_csv=args.measurements,
    )


if __name__ == "__main__":
    main()
