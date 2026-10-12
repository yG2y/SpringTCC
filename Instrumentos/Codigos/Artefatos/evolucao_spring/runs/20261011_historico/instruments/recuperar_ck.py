#!/usr/bin/env python3
"""Merge completed operational retries, checking identical scientific settings."""
import argparse
import json
from pathlib import Path
import shutil
from ck_pipeline.extraction import atomic_json,digest,now


def merge(parent,recovery):
    parent=parent.resolve();recovery=recovery.resolve()
    main_config=json.loads((parent/'config.json').read_text())['config']
    retry_config=json.loads((recovery/'config.json').read_text())['config']
    # Only the candidate list and its size differ. Version, JVM, code, parameters,
    # evidence detector and binary hashes must all agree.
    allowed={'input_sha256','population','classification_scope_size'}
    left={k:v for k,v in main_config.items() if k not in allowed}
    right={k:v for k,v in retry_config.items() if k not in allowed}
    if left!=right:raise ValueError('Recovery scientific configuration differs from parent')
    state=json.loads((recovery/'status.json').read_text())
    if not state['complete']:raise ValueError('Recovery is not finished')
    spec=json.loads((recovery/'recovery_manifest.json').read_text())
    approved=set(spec['target_ids'])
    manifest=[]
    for rid in sorted(approved):
        src=recovery/'repositories'/rid;dest=parent/'repositories'/rid
        old=json.loads((dest/'result.json').read_text())
        new=json.loads((src/'result.json').read_text())
        if old.get('recovery_source')==str(recovery):continue
        if old['status']!='error' or 'Could not resolve host' not in old.get('error',''):raise ValueError('Target no longer has the recorded DNS failure: '+rid)
        if new['status']=='running' or new['repository_id']!=rid or new['full_name']!=old['full_name']:raise ValueError('Recovery identity/state mismatch: '+rid)
        backup=recovery/'initial_failures'/rid/'result.json'
        if not backup.exists() or digest(backup)!=digest(dest/'result.json'):raise ValueError('Original failure backup mismatch: '+rid)
        for item in src.iterdir():
            if item.is_file() and item.name!='result.json':shutil.copyfile(item,dest/item.name)
        new['recovery_source']=str(recovery)
        new['previous_attempt_status']='error_dns'
        atomic_json(dest/'result.json',new)
        manifest.append({'repository_id':rid,'new_status':new['status'],'eligible':new.get('comparison_eligible',False),'commit_sha':new.get('commit_sha'),'source_result_sha256':digest(src/'result.json')})
    atomic_json(recovery/'merge_audit.json',{'merged_at':now(),'same_scientific_config':True,'count':len(manifest),'entries':manifest})
    print(json.dumps({'merged':len(manifest),'remaining_error':sum(r['new_status']=='error' for r in manifest),'eligible':sum(r['eligible'] for r in manifest)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True);p.add_argument('--recovery',type=Path,required=True)
    args=p.parse_args();merge(args.parent,args.recovery)
