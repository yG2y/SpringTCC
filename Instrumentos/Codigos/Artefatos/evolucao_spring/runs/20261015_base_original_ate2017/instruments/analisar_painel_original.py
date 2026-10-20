#!/usr/bin/env python3
"""Painel por eras restrito à seleção original. Filtrar antes de IA/CK."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import html
import json
import statistics
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from ck_pipeline.extraction import METRICS, atomic_json, digest, is_source, now, write_csv
from evolution.framework import detect, needed
from evolution.history import ai_at_snapshot, ai_history, git, materialize, pin_clone, read_history, redact
from evolution.measurement import eligibility, instrument, measure
from evolution.selection import read_csv
from spring_boot_selection.util import parse_iso

CODE = Path(__file__).resolve().parent
BASE = CODE.parent / 'Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv'
BASE_HASH = 'a69e784858cef9ba93d0c017020b5d4733e7ec0390f077904501c673aa88d67f'
CREATED_BEFORE = '2018-01-01T00:00:00Z'
ERA_BOUNDS = {'E1': (2009, 2013), 'E2': (2014, 2017), 'E3': (2018, 2021), 'E4': (2022, 2026)}
PROTOCOL = 'original-selection-era-endpoints-v1'


def cached_clone(row):
    """Reuse objects only; the source population and GitHub ref remain authoritative."""
    old = CODE.parent/'Artefatos/evolucao_spring/runs/20261011_historico'
    reference = old/'repositories'/row['repository_id']/'reference.json'
    clone = old/'clones'/row['repository_id']
    if reference.is_file() and clone.is_dir():
        saved = json.loads(reference.read_text())
        if str(saved['repository_id']) == row['repository_id'] and saved['full_name'] == row['full_name']:
            return clone
    return None


def filter_rows(rows):
    """Pure date filter; never discover, restore exclusions or silently drop errors."""
    cutoff = parse_iso(CREATED_BEFORE)
    ids = [r['repository_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate repository IDs in source')
    included, excluded = [], []
    for row in rows:
        created = parse_iso(row.get('created_at', ''))
        if created is None or created >= cutoff:
            excluded.append(dict(row, exclusion_reason='invalid_creation_date' if created is None else 'created_after_2017'))
        else:
            included.append(dict(row))
    return included, excluded


def prepare(out):
    if digest(BASE) != BASE_HASH:
        raise ValueError('Original selection changed: do not substitute another population')
    source = read_csv(BASE)
    included, excluded = filter_rows(source)
    manifest = out / 'filter_manifest.json'
    if manifest.exists():
        validate_filter(out)
        activity_sensitivity(out, included)
        return json.loads(manifest.read_text())
    if len(source) != 38456:
        raise ValueError('Unexpected original selection size')
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'eligible_repositories.csv', included)
    write_csv(out / 'excluded_creation.csv', excluded)
    e1 = [r for r in included if parse_iso(r['created_at']).year <= 2013]
    e2 = [r for r in included if 2014 <= parse_iso(r['created_at']).year <= 2017]
    write_csv(out / 'e1_20.csv', e1)
    write_csv(out / 'e2_520.csv', e2)
    activity_sensitivity(out, included)
    write_csv(out / 'filter_attrition.csv', [
        dict(stage='original_selected', input_count=len(source), excluded_count=0, output_count=len(source)),
        dict(stage='created_through_2017_utc', input_count=len(source), excluded_count=len(excluded), output_count=len(included))])
    result = dict(protocol=PROTOCOL, created_at=now(), source=str(BASE), source_sha256=BASE_HASH,
                  original_selected=len(source), filtered=len(included), excluded=len(excluded),
                  creation_before=CREATED_BEFORE, e1=len(e1), e2=len(e2),
                  filtered_sha256=digest(out/'eligible_repositories.csv'),
                  activity_policy='Inherited original 3-year pushed_at filter; no refreshed membership',
                  activity_reference='2026-09-17T16:36:06Z', activity_cutoff='2023-09-17T16:36:06Z',
                  sample_status='awaiting_explicit_composition', discovery=False)
    atomic_json(manifest, result)
    return result


def activity_sensitivity(out, rows):
    write_csv(out/'activity_sensitivity.csv', [dict(
        window=label, reference='2026-09-17T16:36:06Z', cutoff=date,
        retained=sum(bool(parse_iso(r.get('pushed_at',''))) and parse_iso(r['pushed_at']) >= parse_iso(date) for r in rows),
        input_count=len(rows), applied_to_membership=False)
        for label,date in [('3_years','2023-09-17T16:36:06Z'),('3_months','2026-06-17T16:36:06Z')]])


def validate_filter(out):
    manifest = json.loads((out/'filter_manifest.json').read_text())
    if digest(BASE) != BASE_HASH or manifest['source_sha256'] != BASE_HASH:
        raise ValueError('Original source provenance mismatch')
    if digest(out/'eligible_repositories.csv') != manifest['filtered_sha256']:
        raise ValueError('Filtered data changed after freezing')
    expected, _ = filter_rows(read_csv(BASE))
    actual = read_csv(out/'eligible_repositories.csv')
    if actual != expected:
        raise ValueError('Filtered population must be exactly the original selection through 2017')
    return actual


def choose(rows, mode, seed=20261011):
    early = [dict(r) for r in rows if parse_iso(r['created_at']).year <= 2013]
    later = [dict(r) for r in rows if parse_iso(r['created_at']).year >= 2014]
    if mode == 'all540':
        selected = early + later
    elif mode == 'e2_520':
        selected = later
    elif mode == 'combined520':
        ordered = sorted(later, key=lambda r: (hashlib.sha256(f'{seed}:{r["repository_id"]}'.encode()).hexdigest(), r['repository_id']))
        selected = early + ordered[:max(0, 520-len(early))]
    else:
        raise ValueError('Explicit sample mode required')
    return sorted(selected, key=lambda r: (r['created_at'], r['repository_id']))


def plan(out, mode):
    rows = validate_filter(out)
    chosen = choose(rows, mode)
    path = out/'sample_manifest.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if previous['mode'] != mode or digest(out/'sample.csv') != previous['sample_sha256']:
            raise ValueError('Frozen sample cannot be replaced; use a new run')
        return previous
    write_csv(out/'sample.csv', chosen)
    manifest = dict(protocol=PROTOCOL, mode=mode, n=len(chosen), seed=20261011,
                    source_sha256=BASE_HASH, filtered_sha256=digest(out/'eligible_repositories.csv'),
                    sample_sha256=digest(out/'sample.csv'), frozen_at=now(), partial_cutoff=now(),
                    min_loc=2000, min_java_files=10, replacement=False,
                    snapshots='last first-parent commit within each era; E1 only original 20')
    atomic_json(path, manifest)
    return manifest


def period_snapshots(commits, line, cutoff, include_e1):
    """No fallback to a more convenient SHA; a missing era remains missing."""
    results = []
    for era, (first, last) in ERA_BOUNDS.items():
        if era == 'E1' and not include_e1:
            continue
        start = datetime(first, 1, 1, tzinfo=timezone.utc)
        end = cutoff if era == 'E4' else datetime(last, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        result = dict(era=era, year=last, period_start=start.isoformat(), cutoff=end.isoformat(),
                      partial=era == 'E4', status='missing_snapshot', eligible=False,
                      exclusion_reasons='no_mainline_commit_within_era')
        candidates = [(i, commits[s]) for i, s in enumerate(line) if start <= commits[s]['committed'] <= end]
        if candidates:
            index, c = candidates[-1]
            result.update(sha=c['sha'], mainline_index=index, committed_at=c['committed'].isoformat(),
                          authored_at=c['authored'].isoformat(), ancestry_max_date=c['ancestry_max_date'].isoformat())
            if c['ancestry_max_date'] > end:
                result.update(status='temporal_anomaly', exclusion_reasons='ancestor_or_author_date_after_cutoff')
            else:
                result.update(status='planned', exclusion_reasons='')
        results.append(result)
    return results


def frozen_instrument(out):
    config = instrument(out)
    # Freeze the endpoint selector and population guard as well as the CK producer.
    selector = digest(Path(__file__))
    manifest = out/'panel_instrument.json'
    info = dict(protocol=PROTOCOL, selector_sha256=selector, ck_instrument_hash=config['instrument_hash'])
    if manifest.exists() and json.loads(manifest.read_text()) != info:
        raise ValueError('Panel instrument changed; use a new run')
    atomic_json(manifest, info)
    return config


def process_repo(row, out, config, cutoff, eras, retry=False):
    rid = row['repository_id']
    dest = out/'repositories'/rid
    dest.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        repo, reference = pin_clone(row, out, config['clone_timeout'], reference_repo=cached_clone(row))
        commits, line, anomalies = read_history(repo, reference['tip'])
        snapshots = period_snapshots(commits, line, cutoff, parse_iso(row['created_at']).year <= 2013)
        snapshots = [s for s in snapshots if s['era'] in eras]
        atomic_json(dest/'history_diagnostics.json', dict(commits=len(commits), mainline_commits=len(line), anomalies=anomalies))
        events_file = dest/'ai_history.json'
        events = None
        for snapshot in snapshots:
            result_file = dest/'snapshots'/snapshot['era']/'result.json'
            if result_file.exists():
                existing = json.loads(result_file.read_text())
                if existing['instrument_hash'] != config['instrument_hash'] or existing['cutoff'] != snapshot['cutoff']:
                    raise ValueError('Frozen snapshot mismatch')
                if not retry or existing['status'] not in {'error', 'partial_ck', 'retrieval_error'}:
                    continue
            result = dict(snapshot, repository_id=rid, full_name=row['full_name'], created_at=row['created_at'],
                          pinned_tip=reference['tip'], instrument_hash=config['instrument_hash'],
                          ia_status='indeterminada', measured_at=now())
            if snapshot['status'] == 'planned':
                try:
                    with tempfile.TemporaryDirectory(dir=out/'work', prefix=rid+'-') as tmp:
                        source = Path(tmp)
                        entries = materialize(repo, snapshot['sha'], source, lambda p: is_source(p) or needed(p))
                        paths = [e['path'] for e in entries if e['kind']=='blob' and e['mode'] in {'100644','100755'}]
                        framework = detect(source, paths, row['full_name'])
                        measured = measure(source, paths, config, out, retry_errors=retry)
                        result.update(measured)
                        submodules = sum(e['kind']=='commit' for e in entries)
                        reasons = eligibility(measured, framework, submodules, config['min_loc'], config['min_java_files'])
                        result.update({k:v for k,v in framework.items() if k not in {'evidence', 'diagnostics'}})
                        result.update(eligible=not reasons, exclusion_reasons=';'.join(reasons), submodules=submodules)
                        atomic_json(result_file.parent/'framework_evidence.json', framework)
                    if events is None:
                        if events_file.exists():
                            saved = json.loads(events_file.read_text())
                            if saved['tip'] != reference['tip'] or saved['instrument_hash'] != config['instrument_hash']:
                                raise ValueError('AI evidence provenance mismatch')
                            events = saved['events']
                        else:
                            events = ai_history(repo, reference['tip'], commits, line)
                            atomic_json(events_file, dict(tip=reference['tip'], instrument_hash=config['instrument_hash'],
                                                        scanned_commits=len(commits), events=events))
                    ai = ai_at_snapshot(repo, snapshot, events)
                    result.update({k:v for k,v in ai.items() if k not in {'present_evidence', 'historical_evidence', 'first_observed'}})
                    atomic_json(result_file.parent/'ai_evidence.json', ai)
                except Exception as exc:
                    result.update(status='error', eligible=False, exclusion_reasons='snapshot_error',
                                  error=redact(str(exc))[:1500])
            atomic_json(result_file, result)
        status = 'complete'
    except Exception as exc:
        status = 'error'
        for snapshot in period_snapshots({}, [], cutoff, parse_iso(row['created_at']).year <= 2013):
            if snapshot['era'] not in eras:
                continue
            path = dest/'snapshots'/snapshot['era']/'result.json'
            if path.exists() and not retry:
                continue
            atomic_json(path, dict(snapshot, repository_id=rid, full_name=row['full_name'],
                created_at=row['created_at'], instrument_hash=config['instrument_hash'],
                status='retrieval_error', ia_status='indeterminada', exclusion_reasons='history_retrieval_error',
                error=redact(str(exc))[:1500]))
    return dict(repository_id=rid, full_name=row['full_name'], status=status, seconds=round(time.monotonic()-start, 2))


def collection_rows(out, scope):
    filtered = validate_filter(out)
    if scope == 'e1':
        return [r for r in filtered if parse_iso(r['created_at']).year <= 2013], ['E1'], None
    manifest = json.loads((out/'sample_manifest.json').read_text())
    if manifest['filtered_sha256'] != digest(out/'eligible_repositories.csv') or digest(out/'sample.csv') != manifest['sample_sha256']:
        raise ValueError('Sample provenance mismatch')
    sample = read_csv(out/'sample.csv')
    expected = choose(filtered, manifest['mode'], manifest['seed'])
    if sample != expected:
        raise ValueError('Sample does not match the authorized population and mode')
    # In e2_520 mode the 20 old projects are an explicitly separate E1 audit.
    return sample, list(ERA_BOUNDS), manifest


def collect(out, scope, workers, retry=False):
    if not 1 <= workers <= 4:
        raise ValueError('Use 1–4 workers')
    rows, eras, manifest = collection_rows(out, scope)
    config = frozen_instrument(out)
    cutoff = parse_iso(manifest['partial_cutoff']) if manifest else parse_iso(json.loads((out/'filter_manifest.json').read_text())['created_at'])
    (out/'work').mkdir(exist_ok=True)
    with (out/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atomic_json(out/'collection_status.json', dict(status='running', scope=scope, selected=len(rows), completed=0, started_at=now()))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [pool.submit(process_repo, row, out, config, cutoff, eras, retry) for row in rows]
            for count, future in enumerate(as_completed(jobs), 1):
                status = future.result()
                print(json.dumps(dict(status, completed=count, total=len(rows)), ensure_ascii=False), flush=True)
                atomic_json(out/'collection_status.json', dict(status='running', scope=scope, selected=len(rows), completed=count, updated_at=now()))
        atomic_json(out/'collection_status.json', dict(status='finished_attempts', scope=scope, selected=len(rows), completed=len(rows), finished_at=now()))
    return report(out)


def report(out):
    filtered = validate_filter(out)
    ids = {r['repository_id'] for r in filtered}
    records = []
    for path in sorted((out/'repositories').glob('*/snapshots/*/result.json')):
        result = json.loads(path.read_text())
        if result['repository_id'] not in ids:
            raise ValueError('Foreign repository in results')
        records.append(result)
    write_csv(out/'measurements.csv', records, list(dict.fromkeys(k for r in records for k in r)) or ['repository_id','era','status','eligible'])
    e1 = [r for r in records if r['era']=='E1']
    fields = ['repository_id','full_name','created_at','era','cutoff','sha','committed_at','status','eligible','exclusion_reasons','java_files','total_loc','framework']
    write_csv(out/'e1_snapshot_audit.csv', [{k:r.get(k) for k in fields} for r in e1], fields)
    summary = []
    for era in ERA_BOUNDS:
        current = [r for r in records if r['era']==era]
        eligible = [r for r in current if r['eligible']]
        summary.append(dict(era=era, attempted_projects=len(current), snapshots=sum(bool(r.get('sha')) for r in current),
            eligible_projects=len(eligible), with_ai=sum(r['ia_status']=='com_evidencia' for r in eligible),
            without_detected_ai=sum(r['ia_status']=='sem_evidencia_detectada' for r in eligible),
            **{m:statistics.mean(r[m] for r in eligible) if eligible else None for m in METRICS}))
    write_csv(out/'era_summary.csv', summary)
    pairs = []
    by_key = {(r['repository_id'],r['era']):r for r in records if r['eligible']}
    for a,b in zip(list(ERA_BOUNDS), list(ERA_BOUNDS)[1:]):
        for rid in ids:
            before, after = by_key.get((rid,a)), by_key.get((rid,b))
            if before and after:
                for metric in METRICS:
                    pairs.append(dict(repository_id=rid,full_name=before['full_name'],before_era=a,after_era=b,
                        before_sha=before['sha'],after_sha=after['sha'],metric=metric,
                        before=before[metric],after=after[metric],difference=after[metric]-before[metric]))
    write_csv(out/'paired_changes.csv', pairs, ['repository_id','full_name','before_era','after_era','before_sha','after_sha','metric','before','after','difference'])
    def table(rows, columns):
        head = ''.join('<th>'+html.escape(c)+'</th>' for c in columns)
        body = ''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(c) if r.get(c) is not None else '—'))+'</td>' for c in columns)+'</tr>' for r in rows)
        return '<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>'
    summary_html = table(summary, ['era','attempted_projects','snapshots','eligible_projects','with_ai','without_detected_ai',*METRICS])
    (out/'report.html').write_text('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Painel da base original</title>'
        '<style>body{font:16px system-ui;margin:32px;line-height:1.5}table{border-collapse:collapse;font-size:13px}th,td{border:1px solid #ddd;padding:8px}th{background:#e8eef5}a{color:#1450a0}</style>'
        '<h1>Projetos da seleção original — snapshots por era</h1>'
        '<p>Base original: 38.456. Criados até 31/12/2017 UTC: '+str(len(filtered))+'. E1 restrita aos 20 originais. '
        'A era indica a data do código. E4 é parcial até o corte fixado. Cada projeto contribui com no máximo uma versão por era.</p>'
        '<p>Os números abaixo descrevem resultados disponíveis; não equivalem à conclusão da coleta. '
        'Elegibilidade: Spring confirmado, pelo menos 2.000 LOC e 10 arquivos Java, cobertura completa e sete métricas disponíveis. '
        'Ausência de evidência não comprova ausência de uso de IA. Valores são médias aritméticas; dados ausentes aparecem como travessão.</p>'
        +summary_html+'<p><a href="measurements.csv">Medições completas</a> · <a href="e1_snapshot_audit.csv">Auditoria dos 20 antigos</a> · '
        '<a href="paired_changes.csv">Diferenças dos mesmos projetos</a> · <a href="eligible_repositories.csv">Base filtrada</a></p></html>',encoding='utf-8')
    result = dict(generated_at=now(), filtered=len(filtered), measured_projects=len({r['repository_id'] for r in records}),
                  era_summary=summary, statuses=dict(Counter(r['status'] for r in records)),
                  measurement_rows=len(records), eligible_snapshots=sum(r['eligible'] for r in records))
    atomic_json(out/'report_manifest.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['filter','plan','collect','report'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['all540','e2_520','combined520'])
    parser.add_argument('--scope', choices=['e1','all'], default='all')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    if args.stage == 'filter':
        result = prepare(out)
    elif args.stage == 'plan':
        if not args.mode:
            parser.error('--mode is required: confirm sample composition before collection')
        result = plan(out, args.mode)
    elif args.stage == 'collect':
        result = collect(out, args.scope, args.workers, args.retry_errors)
    else:
        result = report(out)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
