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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from analisar_painel_original import ERA_BOUNDS, choose, validate_filter
from ck_pipeline.extraction import CLASS_COLUMNS, METRICS, atomic_json, digest, is_source, is_test, java_sloc, now
from evolution.history import file_signals, git, materialize, read_history, tree
from evolution.framework import detect, needed
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
                size=int(header[2]);hasher=hashlib.sha256();chunks=[]
                while size:
                    block=process.stdout.read(min(size,1024*1024))
                    if not block: raise ValueError('Truncated pinned source blob')
                    hasher.update(block);chunks.append(block);size-=len(block)
                if process.stdout.read(1)!=b'\n': raise ValueError('Invalid Git batch delimiter')
                object_hashes[oid]=(hasher.hexdigest(),java_sloc(b''.join(chunks).decode('utf-8',errors='replace')))
            if item['sha256']!=object_hashes[oid][0]:
                errors.append('source_blob_not_from_snapshot:'+item['file'])
            if 'sloc' in item and int(item['sloc'])!=object_hashes[oid][1]:
                errors.append('source_loc_not_from_blob:'+item['file'])
        process.stdin.close()
        process.wait(timeout=30)
    return errors


def record_contract(result, candidate, instrument, manifest=None):
    """Check scientific eligibility and era boundaries independently of the producer."""
    errors=[]
    era=result['era']
    if era not in ERA_BOUNDS:
        return ['unknown_era']
    first,last=ERA_BOUNDS[era]
    start=datetime(first,1,1,tzinfo=timezone.utc)
    end=parse_iso(manifest['partial_cutoff']) if era=='E4' and manifest else datetime(last,12,31,23,59,59,tzinfo=timezone.utc)
    if parse_iso(result.get('period_start',''))!=start: errors.append('wrong_era_start')
    if parse_iso(result.get('cutoff',''))!=end: errors.append('wrong_era_cutoff')
    if result.get('created_at')!=candidate['created_at']: errors.append('creation_metadata_mismatch')
    if result.get('status') not in {'ok','missing_snapshot','retrieval_error','no_java','error','partial_ck','temporal_anomaly'}:
        errors.append('nonfinal_status')
    if not isinstance(result.get('eligible'),bool): errors.append('eligibility_not_boolean')
    if result.get('eligible'):
        if result.get('status')!='ok' or not result.get('sha') or not result.get('cache_key'):
            errors.append('eligible_without_successful_extraction')
        if result.get('framework') not in {'spring_boot','spring_traditional'} or result.get('framework_confirmed') is not True:
            errors.append('eligible_without_confirmed_framework')
        if result.get('exclusion_reasons') or result.get('submodules')!=0:
            errors.append('eligible_with_exclusion')
        if result.get('source_coverage')!=1 or result.get('files_without_class_output')!=0 or result.get('ck_error_signals')!=0:
            errors.append('eligible_without_complete_coverage')
        if result.get('java_files',-1)<instrument.get('min_java_files',10) or result.get('total_loc',-1)<instrument.get('min_loc',2000):
            errors.append('eligible_size')
        if any(not isinstance(result.get(m),(int,float)) or not math.isfinite(result[m]) for m in METRICS):
            errors.append('eligible_missing_metric')
    elif not result.get('exclusion_reasons'):
        errors.append('ineligible_without_reason')
    return errors


def audit(out, report_path=None):
    rows = validate_filter(out)
    allowed = {r['repository_id']:r for r in rows}
    manifest_path = out/'sample_manifest.json'
    chosen = None
    expected = set()
    instrument = json.loads((out/'instrument.json').read_text())
    manifest = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if digest(out/'sample.csv') != manifest['sample_sha256']:
            raise ValueError('Sample hash mismatch')
        with (out/'sample.csv').open(newline='',encoding='utf-8') as handle:
            saved_sample=list(csv.DictReader(handle))
        expected_sample=choose(rows,manifest['mode'],manifest['seed'])
        if saved_sample!=expected_sample:
            raise ValueError('Sample differs from authorized population, even with rewritten hash')
        chosen = {r['repository_id'] for r in expected_sample}
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
    framework_cache={}
    event_cache={}
    for path in sorted((out/'repositories').glob('*/snapshots/*/result.json')):
        result = json.loads(path.read_text())
        result_hashes[str(path.relative_to(out))]=digest(path)
        rid, era = result['repository_id'], result['era']
        if rid!=previous_rid:
            object_hashes.clear();framework_cache.clear();event_cache.clear();previous_rid=rid
        key = (rid, era)
        def check(condition, message):
            if not condition:
                errors.append(dict(repository_id=rid, era=era, check=message))
        check(key not in seen,'duplicate_project_era');seen.add(key)
        check(rid in allowed,'foreign_id')
        if rid not in allowed:
            continue
        check(path.parent.name==era and path.parents[2].name==rid,'result_path_identity')
        for problem in record_contract(result,allowed[rid],instrument,manifest): check(False,problem)
        check(result['full_name']==allowed[rid]['full_name'],'name_mismatch')
        check(result['instrument_hash']==instrument['instrument_hash'],'instrument_hash')
        check(era!='E1' or parse_iso(allowed[rid]['created_at']).year<=2013,'e1_outside_original20')
        check(era=='E1' or chosen is not None and rid in chosen,'outside_frozen_sample')
        if era not in ERA_BOUNDS:
            continue
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
            else:
                check(commits[result['sha']]['ancestry_max_date']>end,'false_temporal_anomaly')
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
                    for prefix,test in [('',None),('production_',False),('test_',True)]:
                        source=methods if metric=='avg_loc_method' else classes
                        source=[r for r in source if test is None or is_test(r['file'])==test]
                        values=[float(r[column]) for r in source if r.get(column) not in (None,'') and math.isfinite(float(r[column]))]
                        expected_mean=statistics.mean(values) if values else None
                        actual=result.get(prefix+metric)
                        check(actual is None and expected_mean is None or actual is not None and expected_mean is not None and math.isclose(actual,expected_mean,rel_tol=1e-10,abs_tol=1e-10),'mean_'+prefix+metric)
                        denominator='n_loc_method' if metric=='avg_loc_method' else 'n_'+column.replace('*','_star')
                        check(result.get(prefix+denominator)==len(values),'denominator_'+prefix+metric)
                check(len({(r['file'],r['class']) for r in classes})==len(classes),'duplicate_raw_classes')
                extracted+=1
            if result['eligible']:
                check(result['java_files']>=10 and result['total_loc']>=2000,'eligible_size')
        framework_file=path.parent/'framework_evidence.json'
        if result.get('cache_key'):
            check(framework_file.exists(),'missing_framework_evidence')
        if framework_file.exists():
            framework=json.loads(framework_file.read_text())
            if result['sha'] not in framework_cache:
                with tempfile.TemporaryDirectory(prefix='spring-framework-audit-') as tmp:
                    source=Path(tmp)
                    entries=materialize(out/'clones'/rid,result['sha'],source,needed)
                    paths=[e['path'] for e in entries if e['kind']=='blob' and e['mode'] in {'100644','100755'}]
                    framework_cache[result['sha']]=detect(source,paths,result['full_name'])
            check(framework==framework_cache[result['sha']],'framework_not_from_snapshot')
            for field in ('framework','framework_confirmed','boot_present','framework_versions'):
                check(result.get(field)==framework.get(field),'framework_result_'+field)
            if result['eligible']: check(not framework['diagnostics'],'eligible_framework_diagnostic')
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
                if event['sha'] not in commits: continue
                c=commits[event['sha']];integration=commits[line[c['integrated_index']]]
                check(parse_iso(event['available_at'])==max(c['ancestry_max_date'],integration['ancestry_max_date']),'ai_availability_from_git')
                check(event['integrated_index']==c['integrated_index'],'ai_integration_index')
                cache_key=(event['sha'],event['type'])
                if cache_key not in event_cache:
                    event_cache[cache_key]=(file_signals(repo,tree(repo,event['sha'])) if event['type'] in {'file','gitignore'} else git(repo,'show','-s','--format=%an%x00%ae%x00%B',event['sha']))
                raw=event_cache[cache_key]
                if event['type'] in {'file','gitignore'}:
                    keys=('agent','type','path')+(('line',) if event['type']=='gitignore' else ())
                    check(any(all(e.get(k)==event.get(k) for k in keys) for e in raw),'ai_historical_file_not_from_git')
                elif event['type']=='coauthor':
                    check(any(line.lower().startswith('co-authored-by:') and line.split(':',1)[1].strip()==event['trailer'] for line in raw.split('\x00',2)[2].splitlines()),'ai_trailer_not_from_git')
                elif event['type']=='author_identity':
                    name,email,_=raw.split('\x00',2)
                    check(event['identity']==(name+' '+email).lower(),'ai_identity_not_from_git')
                else: check(False,'unknown_ai_evidence_type')
    for rid,era in sorted(expected-seen):
        errors.append(dict(repository_id=rid,era=era,check='missing_planned_slot'))
    for rid,era in sorted(seen-expected):
        errors.append(dict(repository_id=rid,era=era,check='unplanned_slot'))
    result=dict(passed=not errors,checked_at=now(),snapshots=len(seen),raw_ck_snapshots=extracted,
                expected_slots=len(expected),missing_slots=len(expected-seen),
                result_set_hash=hashlib.sha256(json.dumps(result_hashes,sort_keys=True).encode()).hexdigest(),
                auditor_sha256=digest(Path(__file__)),errors=errors)
    atomic_json(report_path or out/'audit.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report-path',type=Path,help='Save a new audit outside the frozen run')
    args=parser.parse_args()
    result=audit(args.output.resolve(),args.report_path)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
