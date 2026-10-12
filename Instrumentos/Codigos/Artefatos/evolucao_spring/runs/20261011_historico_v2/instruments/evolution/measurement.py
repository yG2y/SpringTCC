"""Audited CK metrics, immutable source/instrument cache, explicit coverage."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ck_pipeline.extraction import (CLASS_COLUMNS, METRICS, aggregate, atomic_json, digest,
    has_measurable_type, is_source, is_test, java_sloc, now, read_metrics)
from evolution import PROTOCOL

CODE = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
CACHE_LOCKS = {}


def instrument(out):
    tools = CODE/'ck_tools'
    java_candidates = sorted(Path('/opt/homebrew/Cellar/openjdk@17').glob('*/libexec/openjdk.jdk/Contents/Home/bin/java'))
    java = os.environ.get('JAVA_HOME')
    java = str(Path(java)/'bin/java') if java else (str(java_candidates[-1]) if java_candidates else shutil.which('java'))
    if not java:
        raise ValueError('Java 17 runtime not found')
    version = subprocess.run([java, '-version'], capture_output=True, text=True, check=True).stderr.strip()
    sources = [CODE/'analisar_evolucao.py', CODE/'detectar_agentes_ia.py', CODE/'ck_pipeline/extraction.py']
    sources += sorted((CODE/'evolution').glob('*.py'))
    sources += sorted((CODE/'spring_boot_selection').glob('*.py'))
    sources += [CODE/'spring_boot_selection/config.yaml']
    hashes = {str(p.relative_to(CODE)): digest(p) for p in sources}
    manifest = json.loads((tools/'manifest.json').read_text())
    for relative in ('ck-8a1ef916.jar','classes/AuditedCKRunner.class','classes/AuditedCKRunner$1.class'):
        actual = digest(tools/relative)
        if actual != manifest['files'][relative]:
            raise ValueError('Audited CK artifact changed: '+relative)
        hashes['ck_tools/'+relative] = actual
    config = dict(protocol=PROTOCOL, java=java, java_version=version, jar=str(tools/'ck-8a1ef916.jar'),
                  runner_classes=str(tools/'classes'), heap='2g', partition=100, ck_timeout=1800,
                  clone_timeout=900, min_loc=2000, loc_scope='production and tests, physical Java SLOC',
                  hashes=hashes)
    config['instrument_hash'] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    path = out/'instrument.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if previous['instrument_hash'] != config['instrument_hash']:
            raise ValueError('Instrument changed after freezing; record an amendment in a new run')
        return previous
    for p in sources:
        target = out/'instruments'/p.relative_to(CODE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    atomic_json(path, config)
    return config


def gz_csv(path, rows, fields):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def measure(source, paths, config, out, retry_errors=False):
    inventory = []
    for path in sorted(paths):
        if not is_source(path) or not (source/path).is_file():
            continue
        content = (source/path).read_bytes()
        text = content.decode('utf-8',errors='replace')
        inventory.append(dict(file=path, sha256=hashlib.sha256(content).hexdigest(), sloc=java_sloc(text),
                              is_test=is_test(path), measurable_type=has_measurable_type(text)))
    source_hash = hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
    key = hashlib.sha256((source_hash+config['instrument_hash']).encode()).hexdigest()
    dest = out/'extractions'/key
    with LOCK:
        lock = CACHE_LOCKS.setdefault(key, threading.Lock())
    with lock:
        existing = dest/'result.json'
        if existing.exists():
            cached = json.loads(existing.read_text())
            if not retry_errors or cached['status'] not in {'error', 'partial_ck'}:
                return dict(cached, cache_hit=True)
        dest.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        result = dict(cache_key=key, cache_hit=False, source_hash=source_hash, instrument_hash=config['instrument_hash'],
                      extracted_at=now(), status='running', java_files=len(inventory),
                      total_loc=sum(r['sloc'] for r in inventory),
                      production_loc=sum(r['sloc'] for r in inventory if not r['is_test']),
                      test_loc=sum(r['sloc'] for r in inventory if r['is_test']))
        gz_csv(dest/'source_inventory.csv.gz', inventory, ['file','sha256','sloc','is_test','measurable_type'])
        try:
            if not inventory:
                result['status'] = 'no_java'
            else:
                with tempfile.TemporaryDirectory(dir=out/'work', prefix='ck-') as work:
                    work = Path(work)
                    java_sources = work/'source'
                    raw = work/'raw'
                    raw.mkdir()
                    for item in inventory:
                        target = java_sources/item['file']
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source/item['file'],target)
                    command = [config['java'], '-Xmx'+config['heap'], '-cp', config['jar']+os.pathsep+config['runner_classes'],
                               'AuditedCKRunner', str(java_sources), 'false', str(config['partition']), 'false', str(raw)+os.sep]
                    atomic_json(dest/'ck_command.json', command)
                    p = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=config['ck_timeout'])
                    log = p.stdout+'\n'+p.stderr
                    (dest/'ck.log').write_text(log)
                    # Preserve any raw output even on a nonzero return; never turn it into success.
                    for name in ('class','method'):
                        file = raw/(name+'.csv')
                        if file.exists():
                            with file.open('rb') as f, gzip.open(dest/(name+'.original.csv.gz'),'wb') as g:
                                shutil.copyfileobj(f,g)
                    if p.returncode:
                        raise ValueError('CK exit='+str(p.returncode)+'; see ck.log')
                    classes, cf = read_metrics(raw/'class.csv')
                    methods, mf = read_metrics(raw/'method.csv')
                    if not set(CLASS_COLUMNS.values()).union({'loc','file','class','lcom'}) <= cf:
                        raise ValueError('CK class output missing required columns')
                    if not {'file','class','loc'} <= mf:
                        raise ValueError('CK method output missing required columns')
                    for name, rows, fields in [('class',classes,cf),('method',methods,mf)]:
                        for record in rows:
                            record['file'] = str(Path(record['file']).relative_to(java_sources))
                        gz_csv(dest/(name+'.csv.gz'), rows, sorted(fields))
                    if not classes or not methods:
                        raise ValueError('CK returned no measurable classes or methods')
                    result.update(aggregate(classes,methods))
                    for prefix, test in [('production_',False),('test_',True)]:
                        values = aggregate([r for r in classes if is_test(r['file'])==test], [r for r in methods if is_test(r['file'])==test])
                        result.update({prefix+k:v for k,v in values.items()})
                    expected = {r['file'] for r in inventory if r['sloc']>0 and r['measurable_type'] and Path(r['file']).name not in {'package-info.java','module-info.java'}}
                    parsed = {r['file'] for r in classes}
                    missing = sorted(expected-parsed)
                    atomic_json(dest/'coverage.json',dict(expected_files=len(expected), files_with_classes=len(parsed), files_without_class_output=missing))
                    result.update(source_coverage=len(expected&parsed)/len(expected) if expected else None,
                                  files_without_class_output=len(missing),
                                  ck_error_signals=len(re.findall(r'CK_FILE_ERROR:|(?m:^.*(?:Exception in thread|java\.[\w.]*Exception|ERROR|Error parsing).*$)',log)))
                    result['status'] = 'partial_ck' if missing or result['ck_error_signals'] else 'ok'
        except Exception as exc:
            result.update(status='error', error=type(exc).__name__+': '+str(exc)[:800])
        result['duration_seconds'] = round(time.monotonic()-started,3)
        atomic_json(existing, result)
        return result


def eligibility(measured, framework, submodules=0):
    reasons = []
    if measured['status'] != 'ok': reasons.append(measured['status'])
    if not framework['framework_confirmed']: reasons.append(framework['framework'])
    if framework['diagnostics']: reasons.append('framework_parse_diagnostic')
    if measured.get('total_loc',0) < 2000: reasons.append('below_2000_loc')
    if submodules: reasons.append('uninspected_submodule')
    if any(measured.get(m) is None or not math.isfinite(measured[m]) for m in METRICS): reasons.append('missing_metric')
    return reasons
