from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .discovery import count_population, discover_population
from .filters import run_filters, select_top_n
from .github_client import GitHubClient
from .reporting import build_run_metadata, write_report, write_run_metadata
from .technical import validate_selected
from .util import DEFAULT_CONFIG, RUNS_ROOT, load_config, load_env, log, utc_now, utc_now_iso


def new_run_dir() -> Path:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    path = RUNS_ROOT / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_run_dir(explicit: Optional[Path], create: bool) -> Path:
    if explicit:
        explicit.mkdir(parents=True, exist_ok=True)
        return explicit
    if create:
        return new_run_dir()
    if RUNS_ROOT.exists():
        runs = sorted(
            path
            for path in RUNS_ROOT.iterdir()
            if path.is_dir() and path.name[0].isdigit()
        )
        if runs:
            return runs[-1]
    return new_run_dir()


def copy_config(config_path: Path, run_dir: Path) -> None:
    shutil.copy(config_path, run_dir / "config.used.yaml")


def load_population(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "population.csv"
    if not path.exists():
        raise SystemExit(f"population.csv nao encontrado em {run_dir}. Rode discover antes.")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save_count(run_dir: Path, info: Dict[str, Any]) -> None:
    (run_dir / "count.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    snapshots = run_dir.parent / "count_snapshots.jsonl"
    snapshots.parent.mkdir(parents=True, exist_ok=True)
    with snapshots.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(info, ensure_ascii=False) + "\n")


def print_count(info: Dict[str, Any]) -> None:
    print(f"Query: {info['query']}")
    print(f"Collected at: {info['collected_at']}")
    print(f"Total repositories: {info['total_count']}")


def make_client(config: Dict[str, Any]) -> GitHubClient:
    load_env()
    import os

    version = (config.get("discovery") or {}).get("api_version", "2022-11-28")
    return GitHubClient(os.getenv("GITHUB_TOKEN", ""), api_version=version)


def cmd_count(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_dir = resolve_run_dir(args.run_dir, create=True)
    copy_config(args.config, run_dir)
    info = count_population(make_client(config), config)
    save_count(run_dir, info)
    print_count(info)
    log(f"artefato: {run_dir / 'count.json'}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.start_year:
        config["discovery"]["start_year"] = args.start_year
    if args.end_year:
        config["discovery"]["end_year"] = args.end_year
    run_dir = resolve_run_dir(args.run_dir, create=True)
    copy_config(args.config, run_dir)
    started = utc_now_iso()
    client = make_client(config)
    info = count_population(client, config)
    save_count(run_dir, info)
    print_count(info)
    store = discover_population(client, config, run_dir)
    write_run_metadata(
        run_dir / "run_metadata.json",
        build_run_metadata(
            config,
            started_at=started,
            finished_at=utc_now_iso(),
            target_n=args.limit or config.get("target_count") or 0,
            count_info=info,
            collected_unique=len(store.seen),
            eligible_count=0,
            selected_count=0,
            cutoff_date="",
            ordering=config.get("ordering") or [],
            command="discover",
        ),
    )
    log(f"populacao: {run_dir / 'population.csv'} ({len(store.seen)} linhas)")
    return 0


def cmd_filter(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_dir = resolve_run_dir(args.run_dir, create=False)
    copy_config(args.config, run_dir)
    rows = load_population(run_dir)
    result = run_filters(rows, config, run_dir)
    target = args.limit if args.limit is not None else int(config.get("target_count") or 50000)
    selected = select_top_n(result["eligible"], target, run_dir)
    write_report(
        run_dir / "report.txt",
        collection_date=utc_now_iso()[:10],
        attrition=result["attrition"],
        ordering=result["ordering"],
        target_n=target,
        selected_count=len(selected),
        eligible_count=len(result["eligible"]),
    )
    write_run_metadata(
        run_dir / "run_metadata.json",
        build_run_metadata(
            config,
            started_at=utc_now_iso(),
            finished_at=utc_now_iso(),
            target_n=target,
            count_info=json.loads((run_dir / "count.json").read_text(encoding="utf-8"))
            if (run_dir / "count.json").exists()
            else None,
            collected_unique=len(rows),
            eligible_count=len(result["eligible"]),
            selected_count=len(selected),
            cutoff_date=result["cutoff_date"],
            ordering=result["ordering"],
            command="filter",
        ),
    )
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_dir = resolve_run_dir(args.run_dir, create=False)
    eligible_path = run_dir / "eligible_repositories.csv"
    if not eligible_path.exists():
        return cmd_filter(args)
    eligible = load_rows(eligible_path)
    target = args.limit if args.limit is not None else int(config.get("target_count") or 50000)
    selected = select_top_n(eligible, target, run_dir)
    log(f"selected {len(selected)} of {len(eligible)} eligible (requested {target})")
    if len(eligible) < target:
        print(f"Requested: {target}")
        print(f"Eligible: {len(eligible)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.start_year:
        config["discovery"]["start_year"] = args.start_year
    if args.end_year:
        config["discovery"]["end_year"] = args.end_year
    run_dir = resolve_run_dir(args.run_dir, create=True)
    copy_config(args.config, run_dir)
    started = utc_now_iso()
    client = make_client(config)
    info = count_population(client, config)
    save_count(run_dir, info)
    print_count(info)
    store = discover_population(client, config, run_dir)
    rows = load_population(run_dir)
    result = run_filters(rows, config, run_dir)
    target = args.limit if args.limit is not None else int(config.get("target_count") or 50000)
    selected = select_top_n(result["eligible"], target, run_dir)
    write_report(
        run_dir / "report.txt",
        collection_date=started[:10],
        attrition=result["attrition"],
        ordering=result["ordering"],
        target_n=target,
        selected_count=len(selected),
        eligible_count=len(result["eligible"]),
    )
    write_run_metadata(
        run_dir / "run_metadata.json",
        build_run_metadata(
            config,
            started_at=started,
            finished_at=utc_now_iso(),
            target_n=target,
            count_info=info,
            collected_unique=len(store.seen),
            eligible_count=len(result["eligible"]),
            selected_count=len(selected),
            cutoff_date=result["cutoff_date"],
            ordering=result["ordering"],
            command="run",
        ),
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_dir = resolve_run_dir(args.run_dir, create=False)
    selected_path = run_dir / "selected_repositories.csv"
    if not selected_path.exists():
        raise SystemExit("selected_repositories.csv ausente. Rode sample ou filter antes.")
    rows = load_rows(selected_path)
    validate_selected(make_client(config), rows, config, run_dir, args.sample_size)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline auditavel de descoberta, filtragem e amostragem Spring Boot."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("count", help="Consulta total_count da populacao operacional")
    sub.add_parser("discover", help="Coleta o universo particionando created:")
    sub.add_parser("filter", help="Aplica filtros auditaveis sobre population.csv")
    sub.add_parser("sample", help="Seleciona TOP N dos elegiveis")
    sub.add_parser("run", help="count + discover + filter + sample")
    validate = sub.add_parser("validate", help="Valida evidencia Spring Boot no build (amostra)")
    validate.add_argument("--sample-size", type=int, default=30)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "count": cmd_count,
        "discover": cmd_discover,
        "filter": cmd_filter,
        "sample": cmd_sample,
        "run": cmd_run,
        "validate": cmd_validate,
    }
    return commands[args.command](args)
