"""Resumable collection, frozen references and a pilot gate before expansion."""
from __future__ import annotations

import fcntl
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ck_pipeline.extraction import atomic_json, cohort, digest, is_source, now, write_csv
from evolution.framework import detect, needed
from evolution.history import (ai_at_snapshot, ai_history, annual_snapshots, git, materialize,
                               pin_clone, read_history, redact)
from evolution.measurement import CODE, eligibility, instrument, measure
from evolution.selection import read_csv
from spring_boot_selection.util import as_bool, parse_iso


def storage_bytes(folder):
    return sum(p.stat().st_size for p in folder.rglob('*') if p.is_file() and not p.is_symlink()) if folder.exists() else 0


def process(row, config, out, cutoff, retry_errors=False):
    rid = str(row['repository_id'])
    dest = out/'repositories'/rid
    dest.mkdir(parents=True,exist_ok=True)
    started = time.monotonic()
    status = dict(repository_id=rid, full_name=row['full_name'], creation_cohort=row['creation_cohort'],
                  instrument_hash=config['instrument_hash'], started_at=now(), status='running')
    atomic_json(dest/'status.json',status)
    try:
        repo, ref = pin_clone(row,out,config['clone_timeout'])
        commits, line, anomalies = read_history(repo,ref['tip'])
        created = parse_iso(row['created_at'])
        if commits[line[0]]['committed'] < created:
            anomalies.append(dict(kind='history_predates_github_creation', root_sha=line[0],
                                  root_date=commits[line[0]]['committed'].isoformat(), created_at=row['created_at']))
        snapshots = annual_snapshots(commits,line,cutoff)
        atomic_json(dest/'history_diagnostics.json', dict(total_commits=len(commits), first_parent_commits=len(line),
                    roots=[c['sha'] for c in commits.values() if not c['parents']], anomalies=anomalies,
                    limitation='Completeness is relative to the available Git DAG; deleted/migrated history cannot be proved absent'))
        write_csv(dest/'snapshot_plan.csv', snapshots)
        ai_file = dest/'ai_history.json'
        if ai_file.exists():
            history = json.loads(ai_file.read_text())
            if history['instrument_hash']!=config['instrument_hash'] or history['tip']!=ref['tip']:
                raise ValueError('AI history provenance mismatch')
            events = history['events']
        else:
            events = ai_history(repo,ref['tip'],commits,line)
            atomic_json(ai_file,dict(tip=ref['tip'], instrument_hash=config['instrument_hash'],
                        scanned_commits=len(commits), events=events))
        results = []
        measured_shas = {}
        for snapshot in snapshots:
            year = snapshot['year']
            result_file = dest/'snapshots'/str(year)/'result.json'
            if result_file.exists():
                previous = json.loads(result_file.read_text())
                if previous['instrument_hash'] != config['instrument_hash']:
                    raise ValueError('Snapshot instrument mismatch')
                if not retry_errors or previous['status'] not in {'error','partial_ck','retrieval_error'}:
                    results.append(previous)
                    if previous.get('sha') and previous['status'] not in {'error','temporal_anomaly','missing_snapshot','partial_ck'}:
                        measured_shas[previous['sha']] = (previous,result_file.parent)
                    continue
            result = dict(snapshot, repository_id=rid, full_name=row['full_name'],
                          creation_cohort=row['creation_cohort'], created_at=row['created_at'],
                          epoch=cohort(str(year)+'-01-01T00:00:00Z'),
                          measurement_period='2026_partial' if snapshot['partial'] else cohort(str(year)+'-01-01T00:00:00Z'),
                          pinned_tip=ref['tip'], instrument_hash=config['instrument_hash'], ia_status='indeterminada',
                          review_flags=row.get('review_flags',''))
            if snapshot['status']=='planned':
                try:
                    prior=measured_shas.get(snapshot['sha'])
                    if prior:
                        previous,previous_folder=prior
                        # Same SHA implies the same reachable history. Annual
                        # dates/flags remain those of the new observation.
                        temporal_keys={'year','cutoff','partial','no_new_commit','epoch','measurement_period'}
                        result.update({k:v for k,v in previous.items() if k not in temporal_keys})
                        result.update(cache_hit=True,identical_snapshot_reused=True)
                        result_file.parent.mkdir(parents=True,exist_ok=True)
                        for name in ('framework_evidence.json','ai_evidence.json'):
                            shutil.copyfile(previous_folder/name,result_file.parent/name)
                    else:
                        with tempfile.TemporaryDirectory(dir=out/'work',prefix=rid+'-') as work:
                            source = Path(work)
                            entries = materialize(repo,snapshot['sha'],source,lambda p: is_source(p) or needed(p))
                            paths = [e['path'] for e in entries if e['kind']=='blob' and e['mode'] in {'100644','100755'}]
                            framework = detect(source,paths,row['full_name'])
                            ai = ai_at_snapshot(repo,snapshot,events)
                            measured = measure(source,paths,config,out,retry_errors)
                            submodules = sum(e['kind']=='commit' for e in entries)
                            reasons = eligibility(measured,framework,submodules)
                            result.update(measured)
                            result.update({k:v for k,v in framework.items() if k not in {'evidence','diagnostics'}})
                            result.update({k:v for k,v in ai.items() if k not in {'present_evidence','historical_evidence','first_observed'}})
                            result.update(eligible=not reasons, exclusion_reasons=';'.join(reasons),
                                          submodules=submodules, tree_sha=git(repo,'rev-parse',snapshot['sha']+'^{tree}').strip())
                            atomic_json(result_file.parent/'framework_evidence.json',framework)
                            atomic_json(result_file.parent/'ai_evidence.json',ai)
                except Exception as e:
                    result.update(status='error', eligible=False, exclusion_reasons='snapshot_error', error=redact(type(e).__name__+': '+str(e))[:1000])
            atomic_json(result_file,result)
            if result.get('sha') and result['status'] not in {'error','temporal_anomaly','missing_snapshot','partial_ck'}:
                measured_shas[result['sha']] = (result,result_file.parent)
            results.append(result)
        status.update(status='complete', snapshots=len(results), eligible_snapshots=sum(r['eligible'] for r in results),
                      errors=sum(r['status'] in {'error','partial_ck','retrieval_error'} for r in results), tip=ref['tip'],
                      clone_storage_bytes=storage_bytes(repo), unique_snapshot_shas=len({r['sha'] for r in results if r.get('sha')}),
                      reused_extractions=sum(bool(r.get('cache_hit')) for r in results))
    except Exception as e:
        status.update(status='error', error=redact(type(e).__name__+': '+str(e))[:1600])
        for snapshot in annual_snapshots({},[],cutoff):
            target=dest/'snapshots'/str(snapshot['year'])/'result.json'
            if target.exists(): continue
            atomic_json(target,dict(snapshot,repository_id=rid,full_name=row['full_name'],
                creation_cohort=row['creation_cohort'],created_at=row['created_at'],
                epoch=cohort(str(snapshot['year'])+'-01-01T00:00:00Z'),
                measurement_period='2026_partial' if snapshot['partial'] else cohort(str(snapshot['year'])+'-01-01T00:00:00Z'),
                status='retrieval_error',eligible=False,exclusion_reasons='history_retrieval_error',
                error=status['error'],ia_status='indeterminada',instrument_hash=config['instrument_hash']))
    status.update(finished_at=now(), duration_seconds=round(time.monotonic()-started,3))
    atomic_json(dest/'status.json',status)
    return status


def selected(out):
    manifest = json.loads((out/'sample_manifest.json').read_text())
    if digest(out/'sample.csv')!=manifest['sample_sha256']:
        raise ValueError('Frozen sample hash mismatch')
    if digest(out/'population.csv')!=manifest['population_sha256']:
        raise ValueError('Frozen population hash mismatch')
    return manifest, read_csv(out/'sample.csv')


def collect(out, scope='pilot', workers=2, retry_errors=False):
    if workers<1 or workers>8:
        raise ValueError('Use 1–8 workers')
    manifest, rows = selected(out)
    config = instrument(out)
    if scope=='all':
        gate = validate_pilot(out)
        if not gate['passed']:
            raise ValueError('Pilot not validated: '+', '.join(gate['pending']))
    else:
        rows = [r for r in rows if as_bool(r['pilot'])]
    rows.sort(key=lambda r:int(r['processing_rank']))
    (out/'work').mkdir(exist_ok=True)
    (out/'clones').mkdir(exist_ok=True)
    with (out/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        started=time.monotonic()
        todo = []
        for row in rows:
            p = out/'repositories'/row['repository_id']/'status.json'
            if p.exists():
                old=json.loads(p.read_text())
                if old.get('instrument_hash')!=config['instrument_hash']:
                    raise ValueError('Repository instrument mismatch')
                if old['status']=='complete' and not (retry_errors and old.get('errors')): continue
                if old['status']=='error' and not retry_errors: continue
            todo.append(row)
        atomic_json(out/'collection_status.json',dict(status='running',scope=scope,started_at=now(),
                    selected=len(rows), pending=len(todo),workers=workers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(process,r,config,out,parse_iso(manifest['partial_cutoff']),retry_errors) for r in todo]
            for index,future in enumerate(as_completed(jobs),1):
                result=future.result()
                print(json.dumps(dict(done=index,total=len(todo),repository=result['full_name'],status=result['status'],
                                      snapshots=result.get('snapshots'),eligible=result.get('eligible_snapshots'))),flush=True)
                atomic_json(out/'collection_status.json',dict(status='running',scope=scope,updated_at=now(),
                            selected=len(rows),remaining=len(todo)-index,workers=workers))
        atomic_json(out/'collection_status.json',dict(status='complete',scope=scope,finished_at=now(),selected=len(rows),
                    wall_seconds=round(time.monotonic()-started,3),clone_storage_bytes=storage_bytes(out/'clones'),
                    extraction_storage_bytes=storage_bytes(out/'extractions')))
    from evolution.reporting import report
    report(out)


def validate_pilot(out):
    """Validate temporal invariants and explicit manual review, never outcome thresholds."""
    manifest, rows = selected(out)
    pilot = [r for r in rows if as_bool(r['pilot'])]
    pending=[]
    measurements=[]
    failures=[]
    for row in pilot:
        dest=out/'repositories'/row['repository_id']
        p=dest/'status.json'
        if not p.exists() or json.loads(p.read_text())['status']=='running':
            pending.append('unprocessed:'+row['repository_id']); continue
        state=json.loads(p.read_text())
        if state['status']=='error':
            failures.append(dict(repository_id=row['repository_id'],error=state['error'])); continue
        for file in (dest/'snapshots').glob('*/result.json'):
            r=json.loads(file.read_text()); measurements.append(r)
            if r['status'] not in {'missing_snapshot','temporal_anomaly','error'}:
                if parse_iso(r['ancestry_max_date'])>parse_iso(r['cutoff']): pending.append('future_code:'+str(file))
                ai=json.loads((file.parent/'ai_evidence.json').read_text())
                if any(parse_iso(e['available_at'])>parse_iso(r['cutoff']) or e['integrated_index']>r['mainline_index'] for e in ai['historical_evidence']): pending.append('future_ai:'+str(file))
    review_path=out/'pilot_manual_review.json'
    if not review_path.exists():
        pending.append('manual_review_missing')
    else:
        review=json.loads(review_path.read_text())
        if review.get('sample_sha256')!=manifest['sample_sha256']: pending.append('manual_review_sample_mismatch')
        if review.get('instrument_hash')!=json.loads((out/'instrument.json').read_text())['instrument_hash']: pending.append('manual_review_instrument_mismatch')
        old_ids={r['repository_id'] for r in pilot if r['creation_cohort']=='E1'}
        reviewed={str(r['repository_id']) for r in review.get('repositories',[]) if r.get('assessment')}
        if not old_ids<=reviewed: pending.append('old_project_review_incomplete')
    test_path=out/'instrument_validation.json'
    if not test_path.exists() or not json.loads(test_path.read_text()).get('passed'): pending.append('instrument_tests_not_recorded')
    elif json.loads(test_path.read_text()).get('instrument_hash')!=json.loads((out/'instrument.json').read_text())['instrument_hash']:
        pending.append('instrument_tests_hash_mismatch')
    result=dict(passed=not pending, checked_at=now(), pending=pending, pilot_candidates=len(pilot),
                recorded_snapshots=len(measurements), eligible_snapshots=sum(r.get('eligible',False) for r in measurements),
                collection_failures=failures, rule='No substitution or stopping based on CK values or IA prevalence')
    atomic_json(out/'pilot_validation.json',result)
    return result


def validate_instrument(out):
    config=instrument(out)
    command=[sys.executable,'-m','unittest','discover','-s','tests','-v']
    started=time.monotonic()
    p=subprocess.run(command,cwd=CODE,capture_output=True,text=True,timeout=300)
    (out/'instrument_tests.log').write_text(p.stdout+'\n'+p.stderr)
    result=dict(passed=p.returncode==0,checked_at=now(),instrument_hash=config['instrument_hash'],
        duration_seconds=round(time.monotonic()-started,3),command=command,
        test_sources={str(f.relative_to(CODE)):digest(f) for f in sorted((CODE/'tests').glob('*.py'))},
        log_sha256=digest(out/'instrument_tests.log'))
    atomic_json(out/'instrument_validation.json',result)
    return result
