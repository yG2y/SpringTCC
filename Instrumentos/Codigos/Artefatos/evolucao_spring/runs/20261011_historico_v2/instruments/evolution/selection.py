"""Metadata first. Sampling is independent of activity, stars and CK outcomes."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from ck_pipeline.extraction import atomic_json, cohort, digest, now, write_csv
from spring_boot_selection.discovery import discover_population
from spring_boot_selection.filters import classify_non_software, run_filters
from spring_boot_selection.github_client import GitHubClient
from spring_boot_selection.util import as_bool, load_config, load_env, minus_years, parse_iso

TOPICS = ('spring', 'spring-framework', 'spring-mvc', 'spring-boot')
COHORTS = ('E1', 'E2', 'E3', 'E4')


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def historical_config():
    config = copy.deepcopy(load_config())
    config['exclude'].update(archived=False, inactive=False)
    config['ordering'] = [{'field': 'repository_id', 'direction': 'asc'}]
    return config


def creation_cohort(row):
    date = parse_iso(row.get('created_at', ''))
    return cohort(date.isoformat()) if date else 'data_desconhecida'


def activity(row, cutoff):
    date = parse_iso(row.get('pushed_at', ''))
    if date is None or date > cutoff:
        return 'data_desconhecida'
    return 'recente' if date >= minus_years(cutoff, 3) else 'antiga'


def sample(rows, cutoff, seed=20261011, limit=500, pilot=10):
    """Choose first by hash, *then* assign processing order. Never replace failures."""
    selected = []
    for c in COHORTS:
        candidates = [dict(r, creation_cohort=c,
                           lottery_hash=hashlib.sha256(f'{seed}:{r["repository_id"]}'.encode()).hexdigest())
                      for r in rows if creation_cohort(r) == c and parse_iso(r['created_at']) <= cutoff]
        candidates.sort(key=lambda r: (r['lottery_hash'], str(r['repository_id'])))
        for rank, r in enumerate(candidates[:limit], 1):
            r.update(lottery_rank=rank, pilot=rank <= pilot, activity=activity(r, cutoff))
            selected.append(r)
    order = {'recente': 0, 'antiga': 1, 'data_desconhecida': 2}
    for rank, r in enumerate(sorted(selected, key=lambda r: (order[r['activity']], r['creation_cohort'], r['lottery_rank'])), 1):
        r['processing_rank'] = rank
    return selected


def recount(source, out, cutoff):
    rows = read_csv(source)
    filtered = run_filters(rows, historical_config(), out, cutoff)
    candidates = filtered['eligible']
    counts = []
    for c in (*COHORTS, 'fora_das_coortes', 'data_desconhecida'):
        pop = [r for r in rows if creation_cohort(r) == c]
        kept = [r for r in candidates if creation_cohort(r) == c]
        counts.append(dict(creation_cohort=c, population=len(pop), candidates=len(kept),
                           excluded=len(pop)-len(kept), archived_retained=sum(as_bool(r['archived']) for r in kept),
                           old_activity_retained=sum(activity(r, cutoff) == 'antiga' for r in kept),
                           unknown_activity_retained=sum(activity(r, cutoff) == 'data_desconhecida' for r in kept)))
    write_csv(out / 'cohort_counts.csv', counts)
    atomic_json(out / 'recount.json', dict(source=str(source.resolve()), source_sha256=digest(source),
                counted_at=now(), cutoff=cutoff.isoformat(), population=len(rows), candidates=len(candidates),
                activity_exclusion=False, archived_exclusion=False, counts=counts))
    return candidates


def client():
    load_env()
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        # Credential stays in memory, never in argv, output or provenance.
        p = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
        if p.returncode == 0:
            token = p.stdout.strip()
    return GitHubClient(token or '')


def discover(out, original):
    """Resumable per-topic partitions. Complete all topics before freezing sample."""
    out.mkdir(parents=True, exist_ok=True)
    spec_path = out / 'discovery_spec.json'
    if spec_path.exists():
        spec = json.loads(spec_path.read_text())
        if spec['original_sha256'] != digest(original):
            raise ValueError('Original population changed; use a new run')
    else:
        spec = dict(started_at=now(), original=str(original.resolve()), original_sha256=digest(original),
                    topics=list(TOPICS), start_year=2008, end_year=2026)
        atomic_json(spec_path, spec)
    reuse_saved_boot(out, original)
    api = client()
    for topic in TOPICS:
        dest = out / 'discovery' / topic
        if (dest / 'complete.json').exists():
            continue
        cfg = historical_config()
        cfg['discovery'].update(query=f'topic:{topic}', start_year=2008, end_year=2026)
        dest.mkdir(parents=True, exist_ok=True)
        try:
            store = discover_population(api, cfg, dest)
            atomic_json(dest / 'complete.json', dict(completed_at=now(), rows=len(store.seen), config=cfg))
        except Exception as e:
            atomic_json(out / 'discovery_status.json', dict(status='incomplete', topic=topic,
                        error=type(e).__name__, updated_at=now()))
            raise
    union = {}
    sources = [('saved_spring_boot_population', original)] + [(t, out/'discovery'/t/'population.csv') for t in TOPICS]
    for name, path in sources:
        for r in read_csv(path):
            rid = str(r['repository_id'])
            old = union.get(rid)
            provenance = set(old.get('discovery_sources', '').split(';')) if old else set()
            provenance.discard('')
            provenance.add(name)
            # Newest available metadata wins, original-only/deleted candidates retained.
            if old and (r.get('collected_at') or '') < (old.get('collected_at') or ''):
                r = dict(old)
            r['discovery_sources'] = ';'.join(sorted(provenance))
            union[rid] = r
    write_csv(out / 'population.csv', [union[k] for k in sorted(union, key=int)])
    atomic_json(out / 'discovery_status.json', dict(status='complete', completed_at=now(), rows=len(union),
                population_sha256=digest(out/'population.csv'), sources=[dict(name=n, path=str(p), sha256=digest(p)) for n,p in sources]))


def reuse_saved_boot(out, original):
    """Reuse the original *unfiltered* Boot query, explicitly dating this source.

    The union combines the saved Boot population and three new topic queries.
    It does not pretend to be a simultaneous refresh of GitHub's mutable index.
    """
    dest = out/'discovery'/'spring-boot'
    if (dest/'complete.json').exists():
        return
    dest.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(original,dest/'population.csv')
    atomic_json(dest/'complete.json',dict(completed_at=now(), reused=True,
        source=str(original.resolve()), source_sha256=digest(original), rows=len(read_csv(original)),
        query='topic:spring-boot fork:true', source_run='20260920_java',
        caveat='Historical metadata reused; other topics newly discovered; no synchronous census claim'))


def plan(out, seed=20261011, limit=500, pilot=10):
    frozen = out / 'sample_manifest.json'
    if frozen.exists():
        manifest = json.loads(frozen.read_text())
        if manifest['sample_sha256'] != digest(out/'sample.csv'):
            raise ValueError('Frozen sample was modified')
        return manifest
    status = json.loads((out / 'discovery_status.json').read_text())
    if status['status'] != 'complete':
        raise ValueError('Finish all four discovery queries before freezing the sample')
    cutoff = parse_iso(json.loads((out/'discovery_spec.json').read_text())['started_at'])
    candidates = recount(out/'population.csv', out/'selection', cutoff)
    spec = historical_config()['non_software']
    for r in candidates:
        r['review_flags'] = ';'.join(classify_non_software(r, spec)[1])
    selected = sample(candidates, cutoff, seed, limit, pilot)
    write_csv(out/'sample.csv', selected)
    manifest = dict(frozen_at=now(), partial_cutoff=cutoff.isoformat(), seed=seed,
                    maximum_per_cohort=limit, pilot_per_cohort=pilot,
                    sample_sha256=digest(out/'sample.csv'), population_sha256=digest(out/'population.csv'),
                    counts=dict(Counter(r['creation_cohort'] for r in selected)),
                    membership='sha256(seed:repository_id); no replacement',
                    ordering='activity only after membership and pilot are fixed',
                    snapshot_years=list(range(2009, 2027)))
    atomic_json(frozen, manifest)
    return manifest
