#!/usr/bin/env python3
"""Create an auditable derived run with supplemental Gradle catalog resolution.

CK, AI evidence, sample, source SHAs and cuts remain byte-for-byte unchanged.
The CK producer fingerprint remains the original; framework classification gets
its own fingerprint. Never collect CK directly into this derived run.
"""
import argparse
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from catalogos_gradle import supplemental,amend
from ck_pipeline.extraction import IGNORED_PARTS,atomic_json,digest,now,write_csv
from evolution.history import materialize
from evolution.measurement import eligibility


def derive(source,out):
    state=json.loads((source/'collection_status.json').read_text())
    if state['status']!='complete' or state['scope']!='all':raise ValueError('Complete the frozen collection first')
    if out.exists():raise ValueError('Choose a new destination; prior runs remain immutable')
    out.mkdir(parents=True)
    def link(src,dst):
        dst.parent.mkdir(parents=True,exist_ok=True);dst.symlink_to(os.path.relpath(src,dst.parent),target_is_directory=src.is_dir())
    for name in ('population.csv','sample.csv','sample_manifest.json','selection','discovery','original_recount','clones','extractions','instrument.json','instruments','pilot_snapshot','instrument_validation.json','pilot_validation.json','pilot_manual_review.json','audit_pilot.json','python_environment.json','discovery_spec.json','discovery_status.json','recovery_checks.json','historical_case_checks.json','pilot_amendment_audit.json'):
        if (source/name).exists():link(source/name,out/name)
    scripts=out/'classification_instruments';scripts.mkdir()
    for name in ('catalogos_gradle.py','reclassificar_frameworks.py','tests/test_catalogos_gradle.py'):
        p=Path(__file__).parent/name;target=scripts/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    fingerprint=digest(scripts/'catalogos_gradle.py')
    atomic_json(out/'classification_manifest.json',dict(status='running',started_at=now(),source_run=os.path.relpath(source,out),
        ck_producer_hash=json.loads((source/'instrument.json').read_text())['instrument_hash'],framework_classification_hash=fingerprint,
        source_files={str(p.relative_to(scripts)):digest(p) for p in scripts.rglob('*') if p.is_file()},
        reason='Resolve actual uses of literal applied Groovy dependency maps, including default TOML catalogs',
        invariant='CK values, source SHA, temporal cuts, sample and AI evidence unchanged; derived metadata only'))
    changed=[];count=Counter();failures=[]
    for index,repo in enumerate(sorted((source/'repositories').iterdir()),1):
        target=out/'repositories'/repo.name;target.mkdir(parents=True);cache={};eligible_count=0
        for p in repo.iterdir():
            if p.name not in {'snapshots','status.json'}:link(p,target/p.name)
        for p in sorted((repo/'snapshots').glob('*/result.json')):
            dest=target/'snapshots'/p.parent.name;dest.mkdir(parents=True)
            old=json.loads(p.read_text());new=dict(old);fw_file=p.parent/'framework_evidence.json'
            if fw_file.exists():
                original=json.loads(fw_file.read_text());sha=old['sha']
                if sha not in cache:
                    with tempfile.TemporaryDirectory(prefix='spring-catalog-') as tmp:
                        root=Path(tmp)
                        materialize(source/'clones'/repo.name,sha,root,lambda x:x.endswith(('.gradle','.gradle.kts','gradle.properties','libs.versions.toml')) and not any(q in IGNORED_PARTS for q in Path(x).parts))
                        builds={str(f.relative_to(root)):f.read_text(errors='replace') for f in root.rglob('*') if f.is_file()}
                        cache[sha]=supplemental(builds)
                extra=cache[sha];framework=amend(original,extra)
                framework['framework_classification_hash']=fingerprint
                atomic_json(dest/'framework_evidence.json',framework)
                if extra['evidence']:
                    new.update({k:v for k,v in framework.items() if k not in {'evidence','diagnostics','catalog_resolution_diagnostics'}})
                    reasons=eligibility(old,framework,old.get('submodules',0))
                    new.update(eligible=not reasons,exclusion_reasons=';'.join(reasons))
                    count['snapshots_with_supplemental_evidence']+=1
                new['framework_classification_hash']=fingerprint
                if original['framework']!=framework['framework'] or old['eligible']!=new['eligible']:
                    changed.append(dict(repository_id=repo.name,full_name=old['full_name'],year=old['year'],sha=sha,
                        old_framework=old['framework'],new_framework=new['framework'],old_eligible=old['eligible'],new_eligible=new['eligible'],
                        supplemental_evidence=len(extra['evidence']),unresolved=len(extra['unresolved'])))
            if (p.parent/'ai_evidence.json').exists():link(p.parent/'ai_evidence.json',dest/'ai_evidence.json')
            # Every field except the documented classification fields must match.
            allowed={'framework','framework_confirmed','boot_present','framework_versions','boot_prerelease','detection','eligible','exclusion_reasons','framework_classification_hash'}
            diffs=[k for k in set(old)|set(new) if old.get(k)!=new.get(k) and k not in allowed]
            if diffs:failures.append(dict(repository_id=repo.name,year=old['year'],fields=diffs))
            atomic_json(dest/'result.json',new);eligible_count+=new['eligible'];count['snapshots']+=1
        status=json.loads((repo/'status.json').read_text());status['eligible_snapshots']=eligible_count
        status['framework_classification_hash']=fingerprint;atomic_json(target/'status.json',status)
        if index%100==0:print(json.dumps(dict(repositories=index,changes=len(changed))),flush=True)
    write_csv(out/'classification_changes.csv',changed)
    atomic_json(out/'classification_invariance_audit.json',dict(passed=not failures,checked_at=now(),script_sha256=digest(__file__),
        snapshots=count['snapshots'],allowed_changes=sorted(allowed),unexpected_changes=failures,
        changed_snapshots=len(changed),changed_projects=len({r['repository_id'] for r in changed}),
        ck_reexecuted=False,raw_extraction_shared_with=os.path.relpath(source/'extractions',out),
        ai_evidence_shared_with_source=True))
    manifest=json.loads((out/'classification_manifest.json').read_text());manifest.update(status='complete',finished_at=now(),counts=dict(count),changes_sha256=digest(out/'classification_changes.csv'))
    atomic_json(out/'classification_manifest.json',manifest)
    state.update(derived_from=os.path.relpath(source,out),framework_classification_hash=fingerprint)
    atomic_json(out/'collection_status.json',state)
    print(json.dumps(dict(counts=dict(count),changes=len(changed),failures=failures)),flush=True)
    if failures:raise ValueError('Unexpected changes to extraction fields')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();derive(a.source.resolve(),a.output.resolve())
