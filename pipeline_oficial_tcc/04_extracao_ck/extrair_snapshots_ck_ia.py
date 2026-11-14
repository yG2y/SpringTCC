#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 4a: Extracao real por snapshot (clone fixado, commit de cada era, CK e IA).

Para cada um dos 785 candidatos de `02_coortes_e_shas/sample_785.csv`:
1. CLONE FIXADO: clone bare completo da branch principal, com o commit de referencia
   (tip) registrado. Clones da execucao historica de 15/10/2026 sao reutilizados com o
   mesmo tip; os demais sao clonados do GitHub e fixados no SHA de E4 registrado na
   coleta de outubro quando ele esta na linha principal (senao, no HEAD atual).
2. COMMIT POR ERA: em E1 (2009-2013), E2 (2014-2017) e E3 (2018-2021), o ultimo commit
   da linha do primeiro pai com data dentro da era; ausencia de commit e dado ausente.
   Em E4 (era corrente), o snapshot e o tip fixado da branch principal, sem exigir
   commit datado a partir de 2022 (pode coincidir com o de E3).
3. CK: sete medidas com o CK 0.7.1-SNAPSHOT auditado (8a1ef916), sem compilar nem
   executar os projetos; falhas nunca viram zero; producao e testes ficam separados
   nas extracoes brutas.
4. IA: vestigios em arquivos do snapshot e em identidades/trailers de commits
   alcancaveis no historico ate o snapshot, para todas as eras.

Reutiliza os modulos auditados da suite `Instrumentos/Codigos/codigoCKSpring`
(evolution.history, evolution.measurement, ck_tools). E retomavel: resultados ja
gravados nao sao refeitos. Saidas consolidadas:
`04_extracao_ck/measurements_785_candidatos.csv` e
`02_coortes_e_shas/shas_mapeados_por_era.csv`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "Instrumentos/Codigos/codigoCKSpring"
sys.path.insert(0, str(CODE))

from ck_pipeline.extraction import METRICS, atomic_json, digest, is_source, now, write_csv  # noqa: E402
from evolution import history  # noqa: E402
from evolution.history import ai_at_snapshot, ai_history, git, materialize, pin_clone, read_history, redact  # noqa: E402
from evolution.measurement import instrument, measure  # noqa: E402
from spring_boot_selection.util import parse_iso  # noqa: E402

ERA_BOUNDS = {"E1": (2009, 2013), "E2": (2014, 2017), "E3": (2018, 2021)}
ERAS = ["E1", "E2", "E3", "E4"]
RUN_DEFAULT = ROOT / "Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261113_pipeline_oficial_785"
FROZEN_DEFAULT = ROOT / "Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017"

# Emenda de 13/11/2026 aos padroes de vestigios de IA (lacunas confirmadas em auditoria):
# coautoria do Copilot no formato atual do GitHub e entradas de .gitignore sem barra
# final. Aplicada em memoria para nao alterar a suite historica congelada.
AI_PATTERN_AMENDMENT = {
    "coauthor": {"GitHub Copilot": ["copilot@users.noreply.github.com"]},
    "gitignore": {"Claude Code": [".claude"], "Cursor": [".cursor"]},
}
for _agent, _extra in AI_PATTERN_AMENDMENT["coauthor"].items():
    history.COAUTHORED_AGENTES[_agent] = list(history.COAUTHORED_AGENTES[_agent]) + [
        p for p in _extra if p not in history.COAUTHORED_AGENTES[_agent]]
for _agent, _extra in AI_PATTERN_AMENDMENT["gitignore"].items():
    history.GITIGNORE_AGENTES[_agent] = list(history.GITIGNORE_AGENTES[_agent]) + [
        p for p in _extra if p not in history.GITIGNORE_AGENTES[_agent]]


def grupo(row) -> str:
    return "pioneiro_2009_2013" if row["created_at"] < "2014-01-01T00:00:00Z" else "principal_2014_2017"


def preparar_clone(row, out: Path, frozen: Path, sha_e4_registrado: str, timeout: int):
    """Devolve (repo, referencia) com o tip fixado conforme a metodologia."""
    rid = str(row["repository_id"])
    record = out / "repositories" / rid / "reference.json"
    clone = out / "clones" / rid
    if record.exists():
        return pin_clone(row, out, timeout)

    antigo_ref = frozen / "repositories" / rid / "reference.json"
    antigo_clone = frozen / "clones" / rid
    if antigo_ref.is_file() and antigo_clone.is_dir():
        ref = json.loads(antigo_ref.read_text())
        if str(ref["repository_id"]) == rid and ref["full_name"] == row["full_name"]:
            clone.parent.mkdir(parents=True, exist_ok=True)
            if not clone.exists():
                os.symlink(antigo_clone.resolve(), clone)
            ref = dict(ref, tip_source="clone_fixado_20261015", object_cache=str(antigo_clone))
            atomic_json(record, ref)
            return pin_clone(row, out, timeout)

    repo, ref = pin_clone(row, out, timeout)
    fonte = "head_no_clone_de_20261113"
    if sha_e4_registrado and sha_e4_registrado != ref["tip"]:
        linha = set(git(repo, "rev-list", "--first-parent", ref["tip"]).splitlines())
        if sha_e4_registrado in linha:
            ref = dict(ref, head_no_clone=ref["tip"], tip=sha_e4_registrado)
            fonte = "sha_e4_registrado_na_coleta_de_outubro"
        else:
            fonte = "head_no_clone_de_20261113_sha_registrado_fora_da_linha_principal"
    elif sha_e4_registrado:
        fonte = "sha_e4_registrado_na_coleta_de_outubro"
    ref = dict(ref, tip_source=fonte)
    atomic_json(record, ref)
    return repo, ref


def snapshots_por_era(commits, line, tip: str, cutoff: datetime, pioneiro: bool):
    """E1-E3: ultimo commit da linha principal na era. E4: o tip fixado."""
    resultados = []
    for era, (first, last) in ERA_BOUNDS.items():
        if era == "E1" and not pioneiro:
            continue
        start = datetime(first, 1, 1, tzinfo=timezone.utc)
        end = datetime(last, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        res = dict(era=era, period_start=start.isoformat(), cutoff=end.isoformat(), status="missing_snapshot",
                   exclusion_reasons="no_mainline_commit_within_era")
        cand = [(i, commits[s]) for i, s in enumerate(line) if start <= commits[s]["committed"] <= end]
        if cand:
            index, c = cand[-1]
            res.update(sha=c["sha"], mainline_index=index, committed_at=c["committed"].isoformat(),
                       authored_at=c["authored"].isoformat(),
                       ancestry_max_date=c["ancestry_max_date"].isoformat())
            if c["ancestry_max_date"] > end:
                res.update(status="temporal_anomaly", exclusion_reasons="ancestor_or_author_date_after_cutoff")
            else:
                res.update(status="planned", exclusion_reasons="")
        resultados.append(res)
    c = commits[tip]
    resultados.append(dict(
        era="E4", period_start=datetime(2022, 1, 1, tzinfo=timezone.utc).isoformat(), cutoff=cutoff.isoformat(),
        status="planned", exclusion_reasons="", sha=tip, mainline_index=len(line) - 1,
        committed_at=c["committed"].isoformat(), authored_at=c["authored"].isoformat(),
        ancestry_max_date=c["ancestry_max_date"].isoformat(),
        e4_commit_datado_em_e4=c["committed"].year >= 2022))
    return resultados


def processar(row, out: Path, frozen: Path, config, cutoff: datetime, sha_e4_registrado: str):
    rid = str(row["repository_id"])
    dest = out / "repositories" / rid
    dest.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    pioneiro = grupo(row).startswith("pioneiro")
    base = dict(repository_id=rid, full_name=row["full_name"], created_at=row["created_at"],
                grupo_temporal=grupo(row), stargazers_count=row.get("stargazers_count", ""))
    try:
        repo, ref = preparar_clone(row, out, frozen, sha_e4_registrado, config["clone_timeout"])
        commits, line, anomalias = read_history(repo, ref["tip"])
        snaps = snapshots_por_era(commits, line, ref["tip"], cutoff, pioneiro)
        atomic_json(dest / "history_diagnostics.json",
                    dict(commits=len(commits), mainline_commits=len(line), anomalies=anomalias))
        eventos = None
        for snap in snaps:
            arquivo = dest / "snapshots" / snap["era"] / "result.json"
            if arquivo.exists():
                continue
            res = dict(snap, **base, pinned_tip=ref["tip"], tip_source=ref.get("tip_source", ""),
                       instrument_hash=config["instrument_hash"], ia_status="indeterminada", measured_at=now())
            if snap["status"] == "planned":
                try:
                    with tempfile.TemporaryDirectory(dir=out / "work", prefix=rid + "-") as tmp:
                        fonte = Path(tmp)
                        entradas = materialize(repo, snap["sha"], fonte, is_source)
                        caminhos = [e["path"] for e in entradas
                                    if e["kind"] == "blob" and e["mode"] in {"100644", "100755"}]
                        res.update(measure(fonte, caminhos, config, out))
                        res["submodules"] = sum(e["kind"] == "commit" for e in entradas)
                    if eventos is None:
                        arq_eventos = dest / "ai_history.json"
                        if arq_eventos.exists():
                            eventos = json.loads(arq_eventos.read_text())["events"]
                        else:
                            eventos = ai_history(repo, ref["tip"], commits, line)
                            atomic_json(arq_eventos, dict(tip=ref["tip"], scanned_commits=len(commits),
                                                          events=eventos))
                    ia = ai_at_snapshot(repo, snap, eventos)
                    res.update({k: v for k, v in ia.items()
                                if k not in {"present_evidence", "historical_evidence", "first_observed"}})
                    agentes = sorted({e["agent"] for e in ia["present_evidence"] + ia["historical_evidence"]})
                    tipos = sorted({e["type"] for e in ia["present_evidence"] + ia["historical_evidence"]})
                    res.update(ia_agentes="; ".join(agentes), ia_tipos_de_sinal="; ".join(tipos))
                    atomic_json(arquivo.parent / "ai_evidence.json", ia)
                except Exception as exc:  # falha do snapshot fica registrada, nunca vira zero
                    res.update(status="error", exclusion_reasons="snapshot_error", error=redact(str(exc))[:1500])
            atomic_json(arquivo, res)
        status = "complete"
    except Exception as exc:
        status = "error"
        for era in ERAS:
            if era == "E1" and not pioneiro:
                continue
            arquivo = dest / "snapshots" / era / "result.json"
            if arquivo.exists():
                continue
            atomic_json(arquivo, dict(base, era=era, status="retrieval_error", ia_status="indeterminada",
                                      exclusion_reasons="history_retrieval_error",
                                      instrument_hash=config["instrument_hash"], error=redact(str(exc))[:1500]))
    return dict(repository_id=rid, full_name=row["full_name"], status=status,
                seconds=round(time.monotonic() - inicio, 2))


CAMPOS = (["repository_id", "full_name", "stargazers_count", "created_at", "grupo_temporal", "era", "sha",
           "committed_at", "status", "exclusion_reasons", "pinned_tip", "tip_source", "e4_commit_datado_em_e4",
           "classes", "methods", "java_files", "total_loc", "production_loc", "test_loc",
           "production_java_files", "test_java_files"]
          + list(METRICS) + ["n_lcom_star"]
          + ["production_" + m for m in METRICS] + ["test_" + m for m in METRICS]
          + ["source_coverage", "files_without_class_output", "ck_error_signals",
             "ia_status", "ia_present", "ia_history", "ia_agentes", "ia_tipos_de_sinal", "cache_key", "error"])


def consolidar(out: Path, ids, measurements_csv: Path, shas_csv: Path):
    registros = []
    for path in sorted((out / "repositories").glob("*/snapshots/*/result.json")):
        r = json.loads(path.read_text())
        if str(r["repository_id"]) in ids:
            registros.append(r)
    ordem = {e: i for i, e in enumerate(ERAS)}
    registros.sort(key=lambda r: (int(r["repository_id"]), ordem[r["era"]]))
    write_csv(measurements_csv, [{k: r.get(k, "") for k in CAMPOS} for r in registros], CAMPOS)
    campos_sha = ["repository_id", "full_name", "grupo_temporal", "era", "sha", "committed_at", "status"]
    write_csv(shas_csv, [{k: r.get(k, "") for k in campos_sha} for r in registros], campos_sha)
    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 4a: extracao real por snapshot (clone, eras, CK e IA).")
    parser.add_argument("--sample", type=Path, default=ROOT / "pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv")
    parser.add_argument("--run-dir", type=Path, default=RUN_DEFAULT)
    parser.add_argument("--frozen-run", type=Path, default=FROZEN_DEFAULT)
    parser.add_argument("--shas-registrados", type=Path, default=None,
                        help="CSV (repository_id, era, sha) com os SHAs de E4 registrados na coleta de outubro.")
    parser.add_argument("--measurements", type=Path,
                        default=ROOT / "pipeline_oficial_tcc/04_extracao_ck/measurements_785_candidatos.csv")
    parser.add_argument("--shas", type=Path,
                        default=ROOT / "pipeline_oficial_tcc/02_coortes_e_shas/shas_mapeados_por_era.csv")
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "pipeline_oficial_tcc/04_extracao_ck/extracao_manifest.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Processa apenas os N primeiros (teste).")
    parser.add_argument("--only-report", action="store_true", help="Apenas reconsolida os resultados existentes.")
    args = parser.parse_args()

    out = args.run_dir.resolve()
    (out / "work").mkdir(parents=True, exist_ok=True)
    with open(args.sample, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    registrados = {}
    if args.shas_registrados and args.shas_registrados.exists():
        with open(args.shas_registrados, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("era") == "E4" and (r.get("sha") or "").strip():
                    registrados[str(r["repository_id"])] = r["sha"].strip()

    config = instrument(out)
    run_manifest = out / "run_manifest.json"
    if run_manifest.exists():
        info = json.loads(run_manifest.read_text())
    else:
        info = dict(protocol="pipeline_oficial_tcc/extracao-por-snapshot-v1", started_at=now(),
                    collection_cutoff=now(), extractor_sha256=digest(Path(__file__)),
                    ai_pattern_amendment=AI_PATTERN_AMENDMENT,
                    e4_rule="tip fixado da branch principal; sem exigir commit datado em E4")
        atomic_json(run_manifest, info)
    cutoff = parse_iso(info["collection_cutoff"])

    if not args.only_report:
        print(f"[*] Etapa 4a: extraindo {len(rows)} candidatos em {out}", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = [pool.submit(processar, r, out, args.frozen_run.resolve(), config, cutoff,
                                registrados.get(str(r["repository_id"]), "")) for r in rows]
            for n, fut in enumerate(as_completed(jobs), 1):
                s = fut.result()
                print(json.dumps(dict(s, completed=n, total=len(rows)), ensure_ascii=False), flush=True)

    ids = {str(r["repository_id"]) for r in rows}
    registros = consolidar(out, ids, args.measurements, args.shas)
    fontes = Counter()
    for rid in ids:
        ref = out / "repositories" / rid / "reference.json"
        fontes[json.loads(ref.read_text()).get("tip_source", "?") if ref.exists() else "sem_clone"] += 1
    manifest = dict(
        step="04a_extracao_por_snapshot", timestamp_utc=now(), run_dir=os.path.relpath(out, ROOT),
        ck_version="0.7.1-SNAPSHOT (commit 8a1ef916d597d33ad619d748b616bb7dbc3f0c36)",
        java_version=config["java_version"].splitlines()[0], instrument_hash=config["instrument_hash"],
        extractor_sha256=digest(Path(__file__)), collection_cutoff=info["collection_cutoff"],
        e4_rule=info["e4_rule"], ai_pattern_amendment=AI_PATTERN_AMENDMENT,
        candidates=len(rows), tip_sources=dict(sorted(fontes.items())),
        snapshot_rows=len(registros),
        status_by_era={e: dict(sorted(Counter(r["status"] for r in registros if r["era"] == e).items()))
                       for e in ERAS},
        ia_by_era={e: dict(sorted(Counter(r.get("ia_status", "") for r in registros
                                          if r["era"] == e and r["status"] == "ok").items())) for e in ERAS},
        measurements_csv=os.path.relpath(args.measurements.resolve(), ROOT), measurements_sha256=digest(args.measurements),
        shas_csv=os.path.relpath(args.shas.resolve(), ROOT), shas_sha256=digest(args.shas))
    atomic_json(args.manifest, manifest)
    print(json.dumps({k: manifest[k] for k in ("tip_sources", "status_by_era", "ia_by_era")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
