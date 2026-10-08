#!/usr/bin/env python3
"""Resolve Boot versions by TOML coordinates/references at the measured commit.

A metadata QA amendment: retain raw extraction; apply catalog corrections only
in analysis. Select all eligible repositories with detected version catalogs,
without inspecting metric outcomes. No checkout or project code is executed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import tomllib
import urllib.parse
import urllib.request
from ck_pipeline.extraction import atomic_json,digest,now


def catalog_versions(text):
    data=tomllib.loads(text)
    versions=data.get('versions',{})
    def resolve(value):
        if isinstance(value,str):return value
        if not isinstance(value,dict):return ''
        if 'ref' in value:return resolve(versions.get(value['ref'],''))
        return next((resolve(value[k]) for k in ('strictly','require','prefer') if k in value),'')
    found=[]
    for kind in ('plugins','libraries'):
        for alias,item in data.get(kind,{}).items():
            coordinate='';version=''
            if isinstance(item,str) and kind=='libraries':
                parts=item.split(':');coordinate=':'.join(parts[:2]);version=parts[2] if len(parts)>2 else ''
            elif isinstance(item,dict):
                coordinate=item.get('id','') if kind=='plugins' else item.get('module',item.get('group','')+':'+item.get('name',''))
                version=resolve(item.get('version',''))
            target=coordinate=='org.springframework.boot' if kind=='plugins' else coordinate.startswith('org.springframework.boot:')
            if target and re.fullmatch(r'\d+(?:\.[\w-]+)+',version):
                found.append({'kind':kind,'alias':alias,'coordinate':coordinate,'version':version})
    return found


def audit(out):
    targets=[]
    for path in sorted((out/'repositories').glob('*/result.json')):
        result=json.loads(path.read_text())
        if not result.get('comparison_eligible'):continue
        evidence=json.loads((path.parent/'build_evidence.json').read_text())['build_evidence']
        catalogs=sorted({e['file'] for e in evidence if e['file'].endswith('libs.versions.toml')})
        if catalogs:targets.append((result,evidence,catalogs))
    def check(item):
        result,evidence,catalogs=item;rid=result['repository_id'];sources=[];resolved=set()
        for filename in catalogs:
            url=f"https://raw.githubusercontent.com/{result['full_name']}/{result['commit_sha']}/"+urllib.parse.quote(filename,safe='/')
            path=out/'boot_catalog_qc/sources'/rid/filename
            if not path.exists():
                with urllib.request.urlopen(url,timeout=60) as response:contents=response.read()
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(contents)
            parsed=catalog_versions(path.read_text())
            resolved.update(p['version'] for p in parsed)
            sources.append({'file':filename,'local_path':str(path.relative_to(out)),'sha256':digest(path),'url':url,'resolved':parsed})
        # Catalog-only declarations are resolved entirely through explicit GAV/plugin
        # identity. Mixed builds retain other declarations conservatively.
        only_catalogs=all(e['file'].endswith('libs.versions.toml') for e in evidence)
        old=set(filter(None,result.get('spring_boot_versions','').split(';')))
        new=resolved if only_catalogs else old|resolved
        majors=sorted({v.split('.')[0] for v in new if re.fullmatch(r'\d+(?:\.[\w-]+)+',v)})
        major=majors[0] if len(majors)==1 else ('multiple' if majors else 'unknown')
        return {'repository_id':rid,'full_name':result['full_name'],'commit_sha':result['commit_sha'],
                'original_major':result['spring_boot_major'],'original_versions':result['spring_boot_versions'],
                'spring_boot_major':major,'spring_boot_versions':';'.join(sorted(new)),
                'only_catalog_declarations':only_catalogs,'sources':sources,
                'changed':major!=result['spring_boot_major'] or ';'.join(sorted(new))!=result['spring_boot_versions']}
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,targets))
    spec={'audited_at':now(),'scope':'all eligible repositories with detected libs.versions.toml; selected by metadata format, not CK outcome',
          'stage':'metadata quality amendment after initial analysis; raw extraction preserved',
          'script_sha256':digest(Path(__file__)),'repositories':len(rows),'changed_major':sum(r['original_major']!=r['spring_boot_major'] for r in rows),'entries':rows}
    atomic_json(out/'boot_catalog_qc.json',spec)
    print(json.dumps({'catalogs_checked':len(rows),'changed_major':spec['changed_major'],'changes':[(r['full_name'],r['original_major'],r['spring_boot_major']) for r in rows if r['original_major']!=r['spring_boot_major']]}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output.resolve())
