#!/usr/bin/env python3
"""Run from any directory; all paths and data fingerprints are pinned in the run."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import zipfile
from collections import Counter

from ck_pipeline.extraction import PROTOCOL, atomic_json, digest, now, process_repository, run, write_csv

BASE = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE.parent / 'Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv'
DEFAULT_OUTPUT = BASE.parent / 'Artefatos/metricas_ck/runs/20261005_java'


def load_population(path):
    with path.open(newline='', encoding='utf-8-sig') as f: rows = list(csv.DictReader(f))
    required = {'repository_id', 'full_name', 'created_at', 'default_branch'}
    if not rows or not required <= set(rows[0]): raise ValueError('CSV de seleção vazio ou sem colunas obrigatórias')
    ids = [r['repository_id'] for r in rows]
    if len(ids) != len(set(ids)): raise ValueError('IDs duplicados no CSV de seleção')
    for r in rows:
        if not r['repository_id'].isdigit() or not re.fullmatch(r'[\w.-]+/[\w.-]+', r['full_name']):
            raise ValueError('Identidade inválida: ' + r['full_name'])
    return rows


def load_classification(path, selected_ids):
    if not path: return {}
    with path.open(newline='', encoding='utf-8-sig') as f: rows = list(csv.DictReader(f))
    answer = {}
    for r in rows:
        rid = r.get('repository_id', '')
        if rid not in selected_ids: raise ValueError('Classificação fora da seleção final: ' + rid)
        if rid in answer: raise ValueError('Classificação duplicada: ' + rid)
        value = r.get('ia_detectada', '').strip().lower()
        state = 'indeterminada' if r.get('erro') or value not in {'true', 'false', '1', '0'} else ('com_evidencia' if value in {'true', '1'} else 'sem_evidencia_detectada')
        answer[rid] = {'ia_status': state, 'ia_level': r.get('nivel_deteccao', ''), 'ia_agents': r.get('agentes', ''),
                       'ia_method': 'external_csv_unaligned_snapshot', 'evidence': [r], 'commits': []}
    return answer


def consolidate(out, population):
    selected_ids = {r['repository_id'] for r in population}
    saved = {p.parent.name: json.loads(p.read_text()) for p in (out / 'repositories').glob('*/result.json')}
    if set(saved) - selected_ids: raise ValueError('Resultados fora da população fixada')
    all_rows = [saved[r['repository_id']] for r in population if r['repository_id'] in saved]
    done = [r for r in all_rows if r['status'] != 'running']
    eligible = [r for r in done if r.get('eligible')]
    planned_path = out / 'planned_repositories.csv'
    if planned_path.exists():
        with planned_path.open() as f: planned_ids = {r['repository_id'] for r in csv.DictReader(f)}
    else: planned_ids = selected_ids
    planned_done = sum(r['repository_id'] in planned_ids for r in done)
    status = {'requested_scope': len(planned_ids), 'requested_scope_finished': planned_done,
              'requested_scope_complete': planned_done == len(planned_ids), 'updated_at': now(), 'population': len(population), 'finished': len(done),
              'pending': len(population) - len(done), 'complete': len(done) == len(population),
              'eligible': len(eligible), 'statuses': dict(Counter(r['status'] for r in all_rows)),
              'ia_all_finished': dict(Counter(r['ia_status'] for r in done)),
              'ia_eligible': dict(Counter(r['ia_status'] for r in eligible)),
              'comparison_eligible': sum(r.get('comparison_eligible', False) for r in eligible),
              'epoch_eligible': dict(Counter(r['epoch'] for r in eligible))}
    write_csv(out / 'repository_metrics.csv', done, fields=None if done else ['repository_id', 'status'])
    write_csv(out / 'eligible_metrics.csv', eligible, fields=None if eligible else ['repository_id', 'status'])
    write_csv(out / 'classification.csv', [{k: r.get(k) for k in ('repository_id', 'full_name', 'commit_sha', 'extracted_at', 'ia_status', 'ia_level', 'ia_agents', 'ia_method', 'status')} for r in done])
    write_csv(out / 'exclusions.csv', [{k: r.get(k) for k in ('repository_id', 'full_name', 'status', 'exclusion_reasons', 'error')} for r in done if not r.get('eligible')])
    atomic_json(out / 'status.json', status)
    return status


def collect(args):
    population = load_population(args.input)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'work').mkdir(exist_ok=True)
    # Prevent two writers, including concurrent resume attempts.
    with (out / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        java = str(Path(args.java).resolve()) if Path(args.java).is_file() else shutil.which(args.java)
        if not java: raise ValueError('Java não encontrado')
        import subprocess
        java_check = subprocess.run([java, '-version'], capture_output=True, text=True, check=True)
        java_version = java_check.stderr.strip()
        jar = args.jar.resolve()
        with zipfile.ZipFile(jar) as z:
            props = z.read('META-INF/maven/com.github.mauricioaniche/ck/pom.properties').decode()
        ck_version = re.search(r'^version=(.+)$', props, re.M).group(1)
        config = {'protocol': PROTOCOL, 'input_sha256': digest(args.input), 'population': len(population),
                  'jar': str(jar), 'ck_sha256': digest(jar), 'ck_version': ck_version, 'java': java,
                  'java_version': java_version, 'commits': args.commits, 'min_loc': args.min_loc,
                  'min_java_files': args.min_java_files,
                  'heap': args.heap, 'partition': args.partition, 'clone_timeout': args.clone_timeout,
                  'ck_timeout': args.ck_timeout, 'runner_classes': str(args.runner_classes.resolve()) if args.runner_classes else None,
                  'runner_sha256': {p.name:digest(p) for p in sorted(args.runner_classes.glob('*.class'))} if args.runner_classes else None, 'classification_sha256': digest(args.classification) if args.classification else None,
                  'detect_ai': args.detect_ai,
                  'source_scope': 'tracked_java_including_tests_without_hidden_build_generated_vendor',
                  'lcom_column': 'lcom*', 'use_jars': False,
                  'pipeline_sha256': {str(p.relative_to(BASE)): digest(p) for p in [Path(__file__), BASE / 'ck_pipeline/extraction.py', BASE / 'ck_pipeline/__init__.py', BASE / 'detectar_agentes_ia.py']},
                  'packages': {n: importlib.metadata.version(n) for n in ('numpy', 'scipy', 'pandas', 'matplotlib', 'requests', 'python-dotenv')}}
        external = load_classification(args.classification, {r['repository_id'] for r in population})
        if args.classification and not external: raise ValueError('CSV de classificação vazio')
        for row in population:
            if row['repository_id'] in external:
                given_name = external[row['repository_id']]['evidence'][0].get('full_name')
                if given_name and given_name != row['full_name']: raise ValueError('ID/nome divergente no CSV: ' + row['full_name'])
        planned = [r for r in population if not args.classification or r['repository_id'] in external]
        config['classification_scope_size'] = len(planned)
        config_path = out / 'config.json'
        if config_path.exists():
            old = json.loads(config_path.read_text())
            if old['config'] != config: raise ValueError('Protocolo/ambiente/código mudou; use outro diretório para evitar mistura de execuções')
        else:
            atomic_json(config_path, {'created_at': now(), 'config': config})
            shutil.copyfile(args.input, out / 'selected_repositories.csv')
            for relative in config['pipeline_sha256']:
                target = out / 'instruments' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(BASE / relative, target)
        write_csv(out / 'planned_repositories.csv', planned)
        if args.classification: shutil.copyfile(args.classification, out / 'classification.input.csv')
        candidates = []
        for row in planned[:args.limit or None]:
            p = out / 'repositories' / row['repository_id'] / 'result.json'
            previous = json.loads(p.read_text()) if p.exists() else {}
            if previous.get('status') not in (None, 'running') and not (args.retry_errors and previous.get('status') == 'error'): continue
            candidates.append(row)
        atomic_json(out / 'active_process.json', {'pid': os.getpid(), 'started_at': now(), 'requested_repositories': len(candidates), 'workers': args.workers})
        consolidate(out, population)
        print(f'População={len(population)}; pendentes nesta execução={len(candidates)}; CK={ck_version}; JVM={java_version.splitlines()[0]}', flush=True)
        t = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(process_repository, r, config, out, external.get(r['repository_id'])): r for r in candidates}
                for index, future in enumerate(as_completed(futures), 1):
                    r = future.result()
                    print(f'[{index}/{len(candidates)}] {r["full_name"]}: {r["status"]}, IA={r["ia_status"]}, LOC={r.get("total_loc", "-")}, elegível={r["eligible"]}, {r["duration_seconds"]}s', flush=True)
                    if index % 25 == 0 or time.monotonic() - t >= 60:
                        consolidate(out, population); t = time.monotonic()
        finally:
            print(json.dumps(consolidate(out, population), ensure_ascii=False), flush=True)
            atomic_json(out / 'active_process.json', {'pid': os.getpid(), 'ended_at': now(), 'running': False})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    c.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    c.add_argument('--jar', type=Path, default=BASE / 'ck.jar')
    c.add_argument('--runner-classes', type=Path, help='Adapter compiled against the fixed CK jar; preserves (file,class) identity.')
    c.add_argument('--java', default='/opt/homebrew/opt/openjdk@17/bin/java' if Path('/opt/homebrew/opt/openjdk@17/bin/java').exists() else 'java')
    c.add_argument('--classification', type=Path)
    c.add_argument('--detect-ai', action='store_true', help='Refaz a classificação. Sem esta opção e sem CSV externo, rótulos ficam indeterminados.')
    c.add_argument('--limit', type=int, default=0, help='Primeiros N da seleção; 0 processa todos. Subconjunto é sempre declarado parcial.')
    c.add_argument('--workers', type=int, default=2)
    c.add_argument('--commits', type=int, default=30)
    c.add_argument('--min-loc', type=int, default=2000)
    c.add_argument('--min-java-files', type=int, default=10)
    c.add_argument('--heap', default='2g')
    c.add_argument('--partition', type=int, default=100)
    c.add_argument('--clone-timeout', type=int, default=900)
    c.add_argument('--ck-timeout', type=int, default=1800)
    c.add_argument('--retry-errors', action='store_true')
    for name in ('consolidate', 'report'):
        s = sub.add_parser(name)
        s.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    if args.command == 'collect':
        if args.detect_ai and args.classification: p.error('Escolha --classification OU --detect-ai')
        if args.workers < 1 or args.commits < 1 or args.limit < 0: p.error('workers/commits devem ser positivos; limit >= 0')
        collect(args)
    else:
        population = load_population(args.output / 'selected_repositories.csv')
        status = consolidate(args.output, population)
        if args.command == 'report':
            from ck_pipeline.statistics import generate_report
            generate_report(args.output, status)
        else: print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
