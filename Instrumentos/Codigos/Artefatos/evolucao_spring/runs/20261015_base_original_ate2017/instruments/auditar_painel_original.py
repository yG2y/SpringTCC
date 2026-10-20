#!/usr/bin/env python3
"""Audita procedência, limites das eras e médias contra os CSVs brutos."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

from analisar_painel_original import ERA_BOUNDS, choose, validate_filter
from ck_pipeline.extraction import CLASS_COLUMNS, atomic_json, digest, is_source, now
from evolution.history import file_signals, read_history, tree
from spring_boot_selection.util import parse_iso


def verify_source_tree(repo, sha, inventory, object_hashes):
    """Compare the actual pinned Git blobs to the files sent to CK, without checkout."""
    entries={e['path']:e for e in tree(repo,sha)
             if e['kind']=='blob' and e['mode'] in {'100644','100755'} and is_source(e['path'])}
    if set(entries)!={r['file'] for r in inventory}:
        return ['source_paths_not_from_snapshot']
    errors=[]
    with subprocess.Popen(['git','--no-replace-objects','cat-file','--batch'],cwd=repo,
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as process:
        for item in inventory:
            oid=entries[item['file']]['oid']
            if oid not in object_hashes:
                process.stdin.write((oid+'\n').encode());process.stdin.flush()
                header=process.stdout.readline().decode().strip().split()
                if len(header)!=3 or header[1]!='blob':
                    raise ValueError('Missing pinned source blob')
                size=int(header[2]);hasher=hashlib.sha256()
                while size:
                    block=process.stdout.read(min(size,1024*1024))
                    if not block: raise ValueError('Truncated pinned source blob')
                    hasher.update(block);size-=len(block)
                if process.stdout.read(1)!=b'\n': raise ValueError('Invalid Git batch delimiter')
                object_hashes[oid]=hasher.hexdigest()
            if item['sha256']!=object_hashes[oid]:
                errors.append('source_blob_not_from_snapshot:'+item['file'])
        process.stdin.close()
        process.wait(timeout=30)
    return errors


def audit(out):
    rows = validate_filter(out)
    allowed = {r['repository_id']:r for r in rows}
    manifest_path = out/'sample_manifest.json'
    chosen = None
    expected = set()
    instrument = json.loads((out/'instrument.json').read_text())
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if digest(out/'sample.csv') != manifest['sample_sha256']:
            raise ValueError('Sample hash mismatch')
        chosen = {r['repository_id'] for r in choose(rows,manifest['mode'],manifest['seed'])}
        for row in rows:
            rid = row['repository_id']
            if rid in chosen:
                expected.update((rid,era) for era in ERA_BOUNDS if era!='E1' or parse_iso(row['created_at']).year<=2013)
            elif parse_iso(row['created_at']).year<=2013:
                expected.add((rid,'E1'))
    else:
        expected = {(r['repository_id'],'E1') for r in rows if parse_iso(r['created_at']).year<=2013}
    errors = []
    seen = set()
    extracted = 0
    histories = {}
    object_hashes = {}
    previous_rid = None
    result_hashes = {}
    for path in sorted((out/'repositories').glob('*/snapshots/*/result.json')):
        result = json.loads(path.read_text())
        result_hashes[str(path.relative_to(out))]=digest(path)
        rid, era = result['repository_id'], result['era']
        if rid!=previous_rid:
            object_hashes.clear();previous_rid=rid
        key = (rid, era)
        def check(condition, message):
            if not condition:
                errors.append(dict(repository_id=rid, era=era, check=message))
        check(key not in seen,'duplicate_project_era');seen.add(key)
        check(rid in allowed,'foreign_id')
        if rid not in allowed:
            continue
        check(result['full_name']==allowed[rid]['full_name'],'name_mismatch')
        check(result['instrument_hash']==instrument['instrument_hash'],'instrument_hash')
        check(era!='E1' or parse_iso(allowed[rid]['created_at']).year<=2013,'e1_outside_original20')
        check(era=='E1' or chosen is not None and rid in chosen,'outside_frozen_sample')
        if result.get('sha'):
            reference=json.loads((out/'repositories'/rid/'reference.json').read_text())
            check(str(reference['repository_id'])==rid and reference['full_name']==allowed[rid]['full_name'],'reference_identity')
            check(reference['tip']==result['pinned_tip'],'pinned_tip_mismatch')
            if rid not in histories:
                # Paths are ordered by repository: retain one DAG, not all 540.
                histories.clear()
                histories[rid] = read_history(out/'clones'/rid,result['pinned_tip'])
            commits,line,_ = histories[rid]
            start,end = parse_iso(result['period_start']),parse_iso(result['cutoff'])
            candidates = [sha for sha in line if start<=commits[sha]['committed']<=end]
            check(bool(candidates) and candidates[-1]==result['sha'],'not_last_commit_inside_era')
            check(commits[result['sha']]['committed'].isoformat()==result['committed_at'],'committed_date')
            check(commits[result['sha']]['authored'].isoformat()==result['authored_at'],'authored_date')
            if era=='E4':
                check(result['cutoff']==manifest['partial_cutoff'],'e4_frozen_cutoff')
            if result['status']!='temporal_anomaly':
                check(commits[result['sha']]['ancestry_max_date']<=end,'future_ancestry')
        elif result['status']=='missing_snapshot':
            if rid not in histories:
                histories.clear()
                ref=json.loads((out/'repositories'/rid/'reference.json').read_text())
                histories[rid]=read_history(out/'clones'/rid,ref['tip'])
            commits,line,_=histories[rid]
            start,end=parse_iso(result['period_start']),parse_iso(result['cutoff'])
            check(not any(start<=commits[s]['committed']<=end for s in line),'false_missing_snapshot')
        if result.get('cache_key'):
            folder=out/'extractions'/result['cache_key']
            with gzip.open(folder/'source_inventory.csv.gz','rt') as f:
                inventory=list(csv.DictReader(f))
            check(len({r['file'] for r in inventory})==len(inventory),'duplicate_source_paths')
            check(result['java_files']==len(inventory),'file_count')
            check(result['total_loc']==sum(int(r['sloc']) for r in inventory),'loc_count')
            check(result['production_loc']+result['test_loc']==result['total_loc'],'loc_scope_balance')
            check(result['production_java_files']+result['test_java_files']==result['java_files'],'file_scope_balance')
            typed=[dict(file=r['file'],sha256=r['sha256'],sloc=int(r['sloc']),
                        is_test=r['is_test']=='True',measurable_type=r['measurable_type']=='True') for r in inventory]
            source_hash=hashlib.sha256(json.dumps(typed,sort_keys=True).encode()).hexdigest()
            check(result['source_hash']==source_hash,'source_inventory_hash')
            check(result['cache_key']==hashlib.sha256((source_hash+instrument['instrument_hash']).encode()).hexdigest(),'cache_provenance')
            for problem in verify_source_tree(out/'clones'/rid,result['sha'],inventory,object_hashes):
                check(False,problem)
            if result['status']=='ok':
                with gzip.open(folder/'class.csv.gz','rt') as f:
                    classes=list(csv.DictReader(f))
                with gzip.open(folder/'method.csv.gz','rt') as f:
                    methods=list(csv.DictReader(f))
                for metric,column in {**CLASS_COLUMNS,'avg_loc_method':'loc'}.items():
                    source=methods if metric=='avg_loc_method' else classes
                    values=[float(r[column]) for r in source if r.get(column) not in (None,'') and math.isfinite(float(r[column]))]
                    expected_mean=statistics.mean(values) if values else None
                    actual=result.get(metric)
                    check(actual is None and expected_mean is None or actual is not None and expected_mean is not None and math.isclose(actual,expected_mean,rel_tol=1e-10,abs_tol=1e-10),'mean_'+metric)
                extracted+=1
            if result['eligible']:
                check(result['java_files']>=10 and result['total_loc']>=2000,'eligible_size')
        evidence=path.parent/'ai_evidence.json'
        if result['status'] in {'ok','partial_ck','no_java'}:
            check(evidence.exists(),'missing_ai_classification')
        if evidence.exists():
            ai=json.loads(evidence.read_text())
            check(result['ia_status']==ai['ia_status'],'ai_label_mismatch')
            positive=bool(ai.get('present_evidence') or ai.get('historical_evidence'))
            check(ai['ia_status']==('com_evidencia' if positive else 'sem_evidencia_detectada'),'ai_label_without_evidence')
            repo=out/'clones'/rid
            check(ai['present_evidence']==file_signals(repo,tree(repo,result['sha'])),'ai_present_not_from_snapshot')
            if rid not in histories:
                histories.clear();histories[rid]=read_history(repo,result['pinned_tip'])
            commits,line,_=histories[rid]
            index=line.index(result['sha'])
            for event in ai.get('historical_evidence',[]):
                check(parse_iso(event['available_at'])<=parse_iso(result['cutoff']),'future_ai_evidence')
                check(event['sha'] in commits and commits[event['sha']]['integrated_index']<=index,'ai_not_reachable_at_snapshot')
    for rid,era in sorted(expected-seen):
        errors.append(dict(repository_id=rid,era=era,check='missing_planned_slot'))
    for rid,era in sorted(seen-expected):
        errors.append(dict(repository_id=rid,era=era,check='unplanned_slot'))
    result=dict(passed=not errors,checked_at=now(),snapshots=len(seen),raw_ck_snapshots=extracted,
                expected_slots=len(expected),missing_slots=len(expected-seen),
                result_set_hash=hashlib.sha256(json.dumps(result_hashes,sort_keys=True).encode()).hexdigest(),
                auditor_sha256=digest(Path(__file__)),errors=errors)
    atomic_json(out/'audit.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.output.resolve())
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
