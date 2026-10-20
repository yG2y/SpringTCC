#!/usr/bin/env python3
"""Conferência local de artefatos, limitações e agregações; não altera a execução."""
import argparse
import ast
import csv
import hashlib
import importlib.metadata
import json
import math
import random
import re
import statistics
import subprocess
import sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'Instrumentos/Codigos/codigoCKSpring'
sys.path.insert(0,str(CODE))
from ck_pipeline.extraction import METRICS,digest,write_csv,atomic_json
from relatorio_painel_original import validate_existing_report


def inspect(run,out):
    out.mkdir(parents=True,exist_ok=True)
    base=ROOT/'Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java'
    def rows(path):
        with path.open(encoding='utf-8',newline='') as handle:return list(csv.DictReader(handle))
    provenance=validate_existing_report(run)
    records=[json.loads(p.read_text()) for p in sorted((run/'repositories').glob('*/snapshots/*/result.json'))]
    sample=rows(run/'sample.csv');sample_ids={r['repository_id'] for r in sample}
    integrity=[]
    for item in json.loads((run/'reproduction_manifest.json').read_text())['files']:
        path=run/item['path']
        integrity.append(dict(path=item['path'],expected_sha256=item['sha256'],actual_sha256=digest(path) if path.is_file() else '',
                              passed=path.is_file() and digest(path)==item['sha256']))
    write_csv(out/'integridade_execucao.csv',integrity)
    instrument=json.loads((run/'instrument.json').read_text())
    eligibility_mismatches=[]
    for record in records:
        if not record.get('cache_key'): continue
        evidence=run/'repositories'/record['repository_id']/'snapshots'/record['era']/'framework_evidence.json'
        framework=json.loads(evidence.read_text()) if evidence.exists() else {}
        expected=(record['status']=='ok' and framework.get('framework_confirmed') is True and not framework.get('diagnostics') and
                  record.get('java_files',-1)>=10 and record.get('total_loc',-1)>=2000 and record.get('submodules')==0 and
                  all(isinstance(record.get(m),(float,int)) and math.isfinite(record[m]) for m in METRICS))
        if record['eligible']!=expected:eligibility_mismatches.append(dict(repository_id=record['repository_id'],era=record['era']))
    producer=[]
    for name,expected in instrument['hashes'].items():
        path=CODE/name
        producer.append(dict(path=name,expected_sha256=expected,actual_sha256=digest(path) if path.is_file() else '',passed=path.is_file() and digest(path)==expected))
    selector=json.loads((run/'panel_instrument.json').read_text())['selector_sha256']
    producer.append(dict(path='analisar_painel_original.py',expected_sha256=selector,actual_sha256=digest(CODE/'analisar_painel_original.py'),passed=digest(CODE/'analisar_painel_original.py')==selector))
    write_csv(out/'integridade_produtor.csv',producer)
    flags=[r for r in rows(base/'flagged_non_software.csv') if r['repository_id'] in sample_ids]
    eligible_by_id=defaultdict(list)
    for r in records:
        if r['eligible']:eligible_by_id[r['repository_id']].append(r['era'])
    for row in flags:row['eligible_eras']=';'.join(sorted(eligible_by_id[row['repository_id']]))
    write_csv(out/'revisao_educacional_pendente.csv',flags)
    fields=['repository_id','full_name','era','classes','n_lcom_star','avg_lcom','production_loc','test_loc','total_loc','framework_versions']
    observations=[]
    for row in records:
        if not row['eligible']:continue
        observations.append({**{k:row.get(k) for k in fields},'undefined_lcom_classes':row['classes']-row['n_lcom_star'],
                             'production_below_2000':row['production_loc']<2000,'missing_framework_version':not row.get('framework_versions')})
    write_csv(out/'cobertura_metricas.csv',observations)
    distribution=[]
    for era in ('E1','E2','E3','E4'):
        eligible=[r for r in records if r['era']==era and r['eligible']]
        groups={'todos':eligible}
        if era=='E4':groups.update({g:[r for r in eligible if r['ia_status']==g] for g in ('com_evidencia','sem_evidencia_detectada')})
        for group,subset in groups.items():
            for metric in (*METRICS,'total_loc','java_files'):
                values=[r[metric] for r in subset]
                distribution.append(dict(era=era,group=group,metric=metric,n_projects=len(values),mean=statistics.mean(values) if values else None,
                    standard_deviation=statistics.stdev(values) if len(values)>1 else None,minimum=min(values) if values else None,maximum=max(values) if values else None))
    write_csv(out/'dispersao_descritiva.csv',distribution)
    timing=[]
    for group in ('com_evidencia','sem_evidencia_detectada'):
        selected=[r for r in records if r['era']=='E4' and r['eligible'] and r['ia_status']==group]
        dates=[datetime.fromisoformat(r['committed_at']) for r in selected]
        lags=[(datetime.fromisoformat(r['cutoff'])-datetime.fromisoformat(r['committed_at'])).total_seconds()/86400 for r in selected]
        timing.append(dict(group=group,n_projects=len(selected),earliest_snapshot=min(dates).isoformat() if dates else None,
            latest_snapshot=max(dates).isoformat() if dates else None,mean_days_before_cutoff=statistics.mean(lags) if lags else None))
    write_csv(out/'datas_snapshots_e4.csv',timing)
    same=defaultdict(set)
    for r in records:
        if r['eligible']:same[(r['era'],r['source_hash'])].add(r['repository_id'])
    duplicate_groups=[dict(era=e,source_hash=h,repository_ids=';'.join(sorted(ids))) for (e,h),ids in same.items() if len(ids)>1]
    write_csv(out/'inventarios_identicos.csv',duplicate_groups,['era','source_hash','repository_ids'])
    old=rows(ROOT/'Instrumentos/Codigos/Artefatos/analise_repositorios_java.csv')
    matching=sum(math.isclose(float(r['code_duplication_percent']),round(random.Random(int(r['total_java_files'])).uniform(5,15),2),abs_tol=1e-9) for r in old)
    tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
    entries=[];credential_paths=[];pattern=re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b')
    for name in tracked:
        p=ROOT/name
        entries.append(dict(path=name,kind='symlink' if p.is_symlink() else 'file' if p.is_file() else 'missing',bytes=p.stat().st_size if p.exists() else None))
        if p.is_file() and not p.is_symlink() and p.suffix in {'.py','.md','.tex','.json','.yaml','.yml','.toml','.txt','.csv','.log','.html'} and p.stat().st_size<50000000:
            if pattern.search(p.read_bytes()):credential_paths.append(name)
    write_csv(out/'inventario_versionado.csv',entries)
    code_files=list(CODE.rglob('*.py'))
    for p in code_files:ast.parse(p.read_text(),filename=str(p))
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    atomic_json(out/'python_environment.json',dict(python=sys.version,packages=dict(sorted(packages.items()))))
    summary=dict(checked_at=datetime.now(timezone.utc).isoformat(),run=str(run.relative_to(ROOT)),script_sha256=digest(Path(__file__)),
        passed=all(r['passed'] for r in integrity+producer) and not eligibility_mismatches,provenance=provenance,eligibility_mismatches=eligibility_mismatches,
        frozen_files_checked=len(integrity),frozen_file_failures=[r['path'] for r in integrity if not r['passed']],
        producer_failures=[r['path'] for r in producer if not r['passed']],
        tracked_files=len(entries),python_files_parsed=len(code_files),credential_pattern_paths=credential_paths,
        credential_scan_scope='Tracked text files below 50 MB; pattern scan, not a guarantee of absence of every secret',
        flagged_candidates=len(flags),flagged_ever_eligible=sum(bool(r['eligible_eras']) for r in flags),
        eligible_snapshots=len(observations),snapshots_with_undefined_lcom=sum(r['undefined_lcom_classes']>0 for r in observations),
        snapshots_production_below_2000=sum(r['production_below_2000'] for r in observations),
        snapshots_missing_version=sum(r['missing_framework_version'] for r in observations),identical_inventory_groups=len(duplicate_groups),
        legacy_rows=len(old),legacy_duplication_matches_seeded_random=matching,
        caveats=['No manual review or new collection performed','No fuzzy code-clone detection; only exact path/content inventories compared','Supplementary descriptive dispersion; no inferential tests'])
    atomic_json(out/'artifact_audit.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();out=args.output.resolve()
    if out==run or out.is_relative_to(run):parser.error('Audit outputs must be outside the frozen run')
    result=inspect(run,out);print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
