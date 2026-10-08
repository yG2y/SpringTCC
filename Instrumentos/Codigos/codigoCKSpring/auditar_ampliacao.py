#!/usr/bin/env python3
"""Audit the completed expanded run against raw metrics and frozen selection."""
import argparse
import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path
from ck_pipeline.extraction import METRICS, atomic_json, cohort, digest, now


def csv_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def audit(out):
    config=json.loads((out/'config.json').read_text())['config']
    planned=csv_rows(out/'sampling_plan.csv')
    original=csv_rows(out.parents[2]/'selecao_spring_boot/runs/20260920_java/selected_repositories.csv')
    originals={r['repository_id']:r for r in original}
    ids=[r['repository_id'] for r in planned]
    assert len(ids)==len(set(ids))==1520
    assert Counter(cohort(r['created_at']) for r in planned)=={'E1':20,'E2':500,'E3':500,'E4':500}
    for row in planned:
        assert row['repository_id'] in originals
        assert all(row[k]==v for k,v in originals[row['repository_id']].items())
    assert digest(out/'sampling_plan.csv')==config['input_sha256']
    assert digest(Path(config['jar']))==config['ck_sha256']
    for name,expected in config['runner_sha256'].items():
        assert digest(Path(config['runner_classes'])/name)==expected
    for name,expected in config['pipeline_sha256'].items():
        assert digest(out/'instruments'/name)==expected
    saved={p.parent.name:json.loads(p.read_text()) for p in (out/'repositories').glob('*/result.json')}
    assert set(saved)==set(ids)
    assert all(r['status']!='running' for r in saved.values())
    checks=Counter()
    class_columns={'avg_cbo':'cbo','avg_rfc':'rfc','avg_wmc':'wmc','avg_dit':'dit','avg_noc':'noc','avg_lcom':'lcom*'}
    for rid,r in saved.items():
        folder=out/'repositories'/rid
        assert r['full_name']==originals[rid]['full_name']
        if r['ia_status']!='indeterminada':
            ev=json.loads((folder/'ia_evidence.json').read_text())
            assert ev['commit_sha']==r['commit_sha']
            assert ev['ia_status']==r['ia_status']
            if r['ia_status']=='com_evidencia':assert ev['evidence']
            else:assert not ev['evidence'] and r['ia_level']==0
            checks['classification_same_commit']+=1
        invpath=folder/'source_inventory.csv.gz'
        if invpath.exists():
            inv=csv_rows(invpath)
            assert len({x['file'] for x in inv})==len(inv)==r['java_files']
            assert sum(int(x['sloc']) for x in inv)==r['total_loc']
            assert sum(int(x['sloc']) for x in inv if x['is_test']=='False')==r['production_loc']
            checks['source_inventory']+=1
        if r.get('eligible'):
            assert r['status']=='ok' and r['total_loc']>=2000 and r['spring_boot_confirmed']
            assert r['source_coverage']==1 and r['ck_error_signals']==0
            assert all(math.isfinite(r[m]) for m in METRICS)
            cov=json.loads((folder/'coverage.json').read_text())
            assert not cov['files_without_class_output']
            classes=csv_rows(folder/'class.csv.gz');methods=csv_rows(folder/'method.csv.gz')
            assert len(classes)==r['classes'] and len(methods)==r['methods']
            assert len({(x['file'],x['class']) for x in classes})==len(classes)
            for target,column in {**class_columns,'avg_loc_method':'loc'}.items():
                source=methods if target=='avg_loc_method' else classes
                values=[float(x[column]) for x in source if x[column] and math.isfinite(float(x[column]))]
                mean=math.fsum(values)/len(values)
                assert math.isclose(mean,r[target],rel_tol=1e-11,abs_tol=1e-11),(rid,target,mean,r[target])
                denominator='n_loc_method' if target=='avg_loc_method' else 'n_'+column.replace('*','_star')
                assert len(values)==r[denominator]
            checks['raw_metric_aggregates']+=1
        else:assert not r.get('comparison_eligible',False)
    main=csv_rows(out/'analysis_main.csv')
    main_by_id={r['repository_id']:r for r in main}
    catalog=out/'boot_catalog_qc.json'
    if catalog.exists():
        for entry in json.loads(catalog.read_text())['entries']:
            assert entry['commit_sha']==saved[entry['repository_id']]['commit_sha']
            assert entry['spring_boot_major']==main_by_id[entry['repository_id']]['spring_boot_major']
            for source in entry['sources']:assert digest(out/source['local_path'])==source['sha256']
    assert {r['repository_id'] for r in main}=={rid for rid,r in saved.items() if r.get('comparison_eligible')}
    cell_ids=[]
    for p in (out/'subsets').glob('*/*.csv'):
        for r in csv_rows(p):
            assert r['epoch']==p.parent.name and r['ia_status']==p.stem
            cell_ids.append(r['repository_id'])
    assert Counter(cell_ids)==Counter(r['repository_id'] for r in main)
    pairs=csv_rows(out/'matched_pairs.csv')
    assert len({r['ia_repository_id'] for r in pairs})==len(pairs)
    assert len({r['control_repository_id'] for r in pairs})==len(pairs)
    for pair in pairs:
        a,b=saved[pair['ia_repository_id']],saved[pair['control_repository_id']]
        assert a['ia_status']=='com_evidencia' and b['ia_status']=='sem_evidencia_detectada'
        assert a['epoch']==b['epoch']
        am=main_by_id[pair['ia_repository_id']]['spring_boot_major']
        bm=main_by_id[pair['control_repository_id']]['spring_boot_major']
        assert am.isdigit() and am==bm
        assert .5-1e-12<=a['total_loc']/b['total_loc']<=2+1e-12
    for row in csv_rows(out/'epoch_ia_mann_whitney.csv'):
        if row['p_raw']:
            assert math.isclose(float(row['p_adjusted']),min(1,7*float(row['p_raw'])))
            if row['family'].startswith('IA_within_'):
                assert math.isclose(float(row['p_adjusted_across_4_epochs']),min(1,28*float(row['p_raw'])))
    assert len(list((out/'figures').glob('*.png')))==18
    assert len(list((out/'figures').glob('*.svg')))==18
    result={'audited_at':now(),'passed':True,'planned':len(planned),'finished':len(saved),
            'checks':dict(checks),'eight_cells_partition_main':True,'matched_pairs':len(pairs),
            'figures_png':18,'figures_svg':18,'audit_script_sha256':digest(Path(__file__))}
    atomic_json(out/'validation_audit.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output.resolve())
