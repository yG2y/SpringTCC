#!/usr/bin/env python3
"""Independent consistency checks for frozen historical measurements."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ck_pipeline.extraction import CLASS_COLUMNS, METRICS, atomic_json, digest, now
from spring_boot_selection.util import as_bool, parse_iso


def audit(out, scope='all'):
    manifest=json.loads((out/'sample_manifest.json').read_text())
    instrument=json.loads((out/'instrument.json').read_text())
    errors=[]
    if digest(out/'sample.csv')!=manifest['sample_sha256']: errors.append('sample_hash')
    if digest(out/'population.csv')!=manifest['population_sha256']: errors.append('population_hash')
    with (out/'sample.csv').open() as f:
        all_sample=list(csv.DictReader(f))
    sample=[r for r in all_sample if scope=='all' or as_bool(r['pilot'])]
    with (out/'selection/eligible_repositories.csv').open() as f:
        candidates=list(csv.DictReader(f))
    expected_ids=set()
    by_id={r['repository_id']:r for r in all_sample}
    if len(by_id)!=len(all_sample):errors.append('duplicate_sample_id')
    for cohort,lower,upper in [('E1',2009,2013),('E2',2014,2017),('E3',2018,2021),('E4',2022,2026)]:
        pool=[r for r in candidates if parse_iso(r['created_at']) and lower<=parse_iso(r['created_at']).year<=upper and parse_iso(r['created_at'])<=parse_iso(manifest['partial_cutoff'])]
        ranked=sorted((hashlib.sha256((str(manifest['seed'])+':'+r['repository_id']).encode()).hexdigest(),r['repository_id']) for r in pool)
        for rank,(lottery_hash,rid) in enumerate(ranked[:manifest['maximum_per_cohort']],1):
            expected_ids.add(rid)
            r=by_id.get(rid)
            if not r or r['lottery_hash']!=lottery_hash or int(r['lottery_rank'])!=rank or r['creation_cohort']!=cohort:
                errors.append('lottery_membership_or_rank:'+rid)
            elif as_bool(r['pilot'])!=(rank<=manifest['pilot_per_cohort']):errors.append('pilot_membership:'+rid)
    if set(by_id)!=expected_ids:errors.append('frozen_sample_membership')
    activity_order={'recente':0,'antiga':1,'data_desconhecida':2}
    ordered=sorted(all_sample,key=lambda r:(activity_order[r['activity']],r['creation_cohort'],int(r['lottery_rank'])))
    if any(int(r['processing_rank'])!=rank for rank,r in enumerate(ordered,1)):errors.append('processing_order')
    recount=json.loads((out/'selection/recount.json').read_text())
    if recount['activity_exclusion'] or recount['archived_exclusion']:errors.append('activity_or_archive_exclusion')
    ids={r['repository_id'] for r in sample}
    cohort_by_id={r['repository_id']:r['creation_cohort'] for r in sample}
    states=[];snapshots=[];cache_keys=set();evidence_count=0
    for rid in sorted(ids):
        folder=out/'repositories'/rid
        state_file=folder/'status.json'
        if not state_file.exists(): errors.append('unprocessed:'+rid);continue
        state=json.loads(state_file.read_text());states.append(state)
        if state['status'] not in {'complete','error'}:errors.append('unfinished:'+rid);continue
        if state['instrument_hash']!=instrument['instrument_hash']:errors.append('instrument:'+rid)
        records=[json.loads(p.read_text()) for p in sorted((folder/'snapshots').glob('*/result.json'))]
        if len(records)!=18 or {r['year'] for r in records}!=set(range(2009,2027)):errors.append('annual_coverage:'+rid)
        for r in records:
            snapshots.append(r)
            identifier=rid+':'+str(r['year'])
            if str(r['repository_id'])!=rid or r['creation_cohort']!=cohort_by_id[rid]:errors.append('snapshot_identity:'+identifier)
            expected_cutoff=parse_iso(manifest['partial_cutoff']) if r['year']==2026 else datetime(r['year'],12,31,23,59,59,tzinfo=timezone.utc)
            if parse_iso(r['cutoff'])!=expected_cutoff:errors.append('annual_cutoff:'+identifier)
            if bool(r['partial'])!=(r['year']==2026):errors.append('partial_year_flag:'+identifier)
            if r['instrument_hash']!=instrument['instrument_hash']: errors.append('snapshot_instrument:'+identifier)
            if r.get('cache_key'):cache_keys.add(r['cache_key'])
            if r.get('eligible'):
                if r['status']!='ok' or not r.get('framework_confirmed') or r.get('total_loc',0)<2000:
                    errors.append('eligibility:'+identifier)
                if any(r.get(m) is None or not math.isfinite(r[m]) for m in METRICS):errors.append('missing_metric:'+identifier)
                if r.get('source_coverage')!=1.0:errors.append('coverage:'+identifier)
                if r.get('framework')=='framework_source':errors.append('framework_source_in_main:'+identifier)
            if r['status'] in {'missing_snapshot','temporal_anomaly','retrieval_error'}:
                if any(m in r for m in METRICS):errors.append('metric_on_missing_snapshot:'+identifier)
                continue
            if r['status']=='error': continue
            cutoff=parse_iso(r['cutoff'])
            if any(parse_iso(r[key])>cutoff for key in ('committed_at','authored_at','ancestry_max_date')):errors.append('future_code:'+identifier)
            ai=json.loads((folder/'snapshots'/str(r['year'])/'ai_evidence.json').read_text())
            for event in ai['historical_evidence']:
                evidence_count+=1
                if parse_iso(event['available_at'])>cutoff or event['integrated_index']>r['mainline_index']:
                    errors.append('future_ai:'+identifier)
    cached_results={}
    for key in sorted(cache_keys):
        folder=out/'extractions'/key
        measured=json.loads((folder/'result.json').read_text())
        cached_results[key]=measured
        if measured['instrument_hash']!=instrument['instrument_hash']:errors.append('cached_instrument:'+key)
        with gzip.open(folder/'source_inventory.csv.gz','rt') as f:inventory=list(csv.DictReader(f))
        typed_inventory=[dict(file=r['file'],sha256=r['sha256'],sloc=int(r['sloc']),
                              is_test=as_bool(r['is_test']),measurable_type=as_bool(r['measurable_type'])) for r in inventory]
        source_hash=hashlib.sha256(json.dumps(typed_inventory,sort_keys=True).encode()).hexdigest()
        if source_hash!=measured['source_hash']:errors.append('source_inventory_hash:'+key)
        expected_key=hashlib.sha256((source_hash+instrument['instrument_hash']).encode()).hexdigest()
        if expected_key!=key:errors.append('extraction_cache_key:'+key)
        if sum(int(r['sloc']) for r in inventory)!=measured['total_loc']:errors.append('loc_inventory:'+key)
        test_files={r['file'] for r in inventory if as_bool(r['is_test'])}
        for prefix,is_test in [('production_',False),('test_',True)]:
            expected_loc=sum(int(r['sloc']) for r in inventory if (r['file'] in test_files)==is_test)
            if expected_loc!=measured[prefix+'loc']:errors.append('loc_scope:'+key+':'+prefix)
        if measured['status'] not in {'ok','partial_ck'}:continue
        with gzip.open(folder/'class.csv.gz','rt') as f:classes=list(csv.DictReader(f))
        with gzip.open(folder/'method.csv.gz','rt') as f:methods=list(csv.DictReader(f))
        for prefix,test in [('',None),('production_',False),('test_',True)]:
            for metric in METRICS:
                records=methods if metric=='avg_loc_method' else classes
                if test is not None:records=[r for r in records if (r['file'] in test_files)==test]
                field='loc' if metric=='avg_loc_method' else CLASS_COLUMNS[metric]
                values=[float(r[field]) for r in records if r.get(field) not in (None,'') and math.isfinite(float(r[field]))]
                expected=sum(values)/len(values) if values else None
                observed=measured.get(prefix+metric)
                if expected is None or observed is None:
                    if expected!=observed:errors.append('raw_mean:'+key+':'+prefix+metric)
                elif not math.isclose(expected,observed,rel_tol=1e-12,abs_tol=1e-12):errors.append('raw_mean:'+key+':'+prefix+metric)
    for r in snapshots:
        if not r.get('cache_key'):continue
        cached=cached_results[r['cache_key']]
        for prefix in ('','production_','test_'):
            for metric in METRICS:
                if r.get(prefix+metric)!=cached.get(prefix+metric):
                    errors.append('snapshot_cache_mean:'+str(r['repository_id'])+':'+str(r['year'])+':'+prefix+metric)
    result=dict(passed=not errors,checked_at=now(),scope=scope,sample_candidates=len(sample),processed=len(states),
                annual_records=len(snapshots),distinct_extractions=len(cache_keys),historical_evidence_records_checked=evidence_count,
                snapshot_statuses=dict(Counter(r['status'] for r in snapshots)),
                eligible_snapshots=sum(r.get('eligible',False) for r in snapshots),
                errors=errors,script_sha256=digest(__file__),sample_sha256=manifest['sample_sha256'],
                instrument_hash=instrument['instrument_hash'])
    atomic_json(out/('audit_'+scope+'.json'),result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scope',choices=['pilot','all'],default='all')
    args=p.parse_args()
    if not audit(args.output.resolve(),args.scope)['passed']:raise SystemExit(1)
