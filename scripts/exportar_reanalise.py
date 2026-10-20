#!/usr/bin/env python3
"""Empacota dados para reanálise local; não inclui clones Git nem faz coleta/push."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'Instrumentos/Codigos/codigoCKSpring'
sys.path.insert(0,str(CODE))
from ck_pipeline.extraction import digest
from relatorio_painel_original import validate_existing_report


def package(run,output):
    if output.exists():raise ValueError('Choose a new archive; do not replace existing research artifacts')
    if output.is_relative_to(run):raise ValueError('Archive must be outside the frozen run')
    verified=validate_existing_report(run)
    # Allowlist excludes credentials, .git, work directories and Git object caches.
    files=set(run.glob('*.csv'))|set(run.glob('*.json'))|set(run.glob('*.html'))
    for name in ('repositories','extractions','instruments','figures','recovery_checks'):
        files.update(p for p in (run/name).rglob('*') if p.is_file())
    files.update(CODE.glob('*.py'));files.update(CODE.glob('*.md'));files.update(CODE.glob('requirements*.txt'))
    for name in ('ck_pipeline','evolution','spring_boot_selection','ck_tools','tests','legacy'):
        files.update(p for p in (CODE/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    base=ROOT/'Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java'
    files.update(base/name for name in ('selected_repositories.csv','config.used.yaml','filter_attrition.csv','flagged_non_software.csv'))
    files.update([ROOT/'AGENTS.md',ROOT/'README.md',CODE/'METODOLOGIA_PAINEL_ORIGINAL.md',ROOT/'scripts/verificar.py'])
    files.update((ROOT/'scripts').glob('*.py'))
    files.update(p for p in (ROOT/'docs').rglob('*') if p.is_file())
    files.update(p for p in (ROOT/'Artigo').rglob('*') if p.is_file() and p.suffix in {'.tex','.bib','.sty','.cls','.bst'})
    files.add(ROOT/'output/pdf/Article_auditado_20261015.pdf')
    files.add(ROOT/'output/pdf/build_manifest_auditado_20261015.json')
    files.add(ROOT/'output/pdf/Article_base_original_20261015.pdf')
    files.add(ROOT/'Artigo/TCC_Teamplate__Complexidade_Spring_Boot___New_Version.pdf')
    files.add(ROOT/'LICENSE')
    files.update(ROOT.glob('RELATORIO*.md'))
    files.add(ROOT/'Instrumentos/Codigos/Artefatos/analise_repositorios_java.csv')
    inventory=[]
    for p in sorted(files):
        if p.is_symlink() or not p.is_relative_to(ROOT) or '.env' in p.parts:
            raise ValueError('Unexpected path in package: '+str(p))
        inventory.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p),bytes=p.stat().st_size))
    output.parent.mkdir(parents=True,exist_ok=True);temp=output.with_suffix(output.suffix+'.tmp')
    try:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for item in inventory:archive.write(ROOT/item['path'],'project/'+item['path'])
            archive.writestr('manifest.json',json.dumps(dict(level='reanalysis_without_git_objects',verification=verified,files=inventory),ensure_ascii=False,indent=2))
            archive.writestr('LEIA-ME.txt',
                'Pacote de reanalise do painel original. Inclui lista, SHA, evidencias, CSV brutos CK, fontes e dependencias.\n'
                'Nao inclui clones/objetos Git (aproximadamente 9 GiB), ambiente Python instalado nem JDK.\n'
                'Permite conferir e recalcular as medias a partir dos dados brutos. A auditoria completa de historico e a reextracao CK exigem os clones locais originais.\n'
                'As referencias remotas podem desaparecer; reclonar nao garante recuperacao dos mesmos objetos.\n'
                'O manifesto verifica bytes e SHA-256; nao comprova validade dos construtos ou precisao do detector IA.\n')
        with zipfile.ZipFile(temp) as archive:
            if archive.testzip() is not None:raise ValueError('Corrupt archive')
            for item in inventory:
                with archive.open('project/'+item['path']) as stream:
                    hasher=hashlib.sha256()
                    for block in iter(lambda:stream.read(1024*1024),b''):hasher.update(block)
                if hasher.hexdigest()!=item['sha256']:raise ValueError('Archive hash mismatch: '+item['path'])
        temp.rename(output)
    finally:
        temp.unlink(missing_ok=True)
    result=dict(archive=str(output.relative_to(ROOT)),sha256=digest(output),bytes=output.stat().st_size,files=len(inventory),verification='Every archived file hashed after extraction in memory',level='reanalysis_without_git_objects')
    output.with_suffix('.manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.run.resolve(),args.output.resolve()),ensure_ascii=False,indent=2))
