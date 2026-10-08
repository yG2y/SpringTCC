"""Extraction on immutable commits; never build or execute sampled repositories."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from detectar_agentes_ia import ARQUIVOS_AGENTES, GITIGNORE_AGENTES, BOTS_AUTORES, COAUTHORED_AGENTES

METRICS = ('avg_cbo', 'avg_rfc', 'avg_wmc', 'avg_loc_method', 'avg_dit', 'avg_noc', 'avg_lcom')
CLASS_COLUMNS = {'avg_cbo': 'cbo', 'avg_rfc': 'rfc', 'avg_wmc': 'wmc', 'avg_dit': 'dit', 'avg_noc': 'noc', 'avg_lcom': 'lcom*'}
IGNORED_PARTS = {'.git', 'target', 'build', 'out', 'node_modules', 'vendor', 'generated', 'generated-sources'}
PROTOCOL = 'ck-comparison-v2-epochs-snapshot-aligned'


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    temp.replace(path)


def cohort(created):
    year = datetime.fromisoformat(created.replace('Z', '+00:00')).year
    if 2009 <= year <= 2013: return 'E1'
    if 2014 <= year <= 2017: return 'E2'
    if 2018 <= year <= 2021: return 'E3'
    if year >= 2022: return 'E4'
    return 'fora_das_coortes'


def run(command, cwd=None, timeout=600):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1', LC_ALL='C')
    p = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, errors='replace', timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{command[0]} exit={p.returncode}: {p.stderr[-1500:]} {p.stdout[-500:]}')
    return p.stdout


def is_source(path):
    p = Path(path)
    return p.suffix == '.java' and not any(x in IGNORED_PARTS or x.startswith('.') for x in p.parts)


def is_test(path):
    parts = [p.lower() for p in Path(path).parts]
    return any(p in {'test', 'tests', 'testfixtures', 'integration-test', 'integrationtest', 'inttest', 'dockertest', 'testsupport', 'smoke-test', 'jmh', 'benchmark', 'benchmarks'} for p in parts)


def java_sloc(text):
    """Physical nonblank/noncomment lines, once per file (not sum of nested classes)."""
    state = 'code'
    escape = False
    count = 0
    for line in text.splitlines():
        has_code = False
        i = 0
        while i < len(line):
            c = line[i]
            if state == 'block':
                if line.startswith('*/', i): state = 'code'; i += 2
                else: i += 1
            elif state == 'text':
                has_code = True
                if line.startswith('"""', i) and not escape: state = 'code'; i += 3
                else:
                    escape = c == '\\' and not escape
                    i += 1
            elif state in ('string', 'char'):
                has_code = True
                if c == ('"' if state == 'string' else "'") and not escape: state = 'code'
                escape = c == '\\' and not escape
                i += 1
            elif line.startswith('//', i): break
            elif line.startswith('/*', i): state = 'block'; i += 2
            elif line.startswith('"""', i): state = 'text'; has_code = True; escape = False; i += 3
            elif c in ('"', "'"): state = 'string' if c == '"' else 'char'; escape = False; has_code = True; i += 1
            else:
                has_code |= not c.isspace()
                i += 1
        count += int(has_code)
        if state in ('string', 'char'): state = 'code'
        escape = False
    return count


def has_measurable_type(text):
    """Annotation-only descriptors are not emitted by CK; records remain expected.

    This is only a conservative coverage screen, not a replacement Java parser.
    """
    stripped = re.sub(r'""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/', ' ', text, flags=re.S)
    stripped = re.sub(r'@\s*interface\b', ' ', stripped)
    return bool(re.search(r'\b(?:class|interface|enum|record)\s+[A-Za-z_$]', stripped))


def read_local(repo, path):
    p = repo / path
    if p.is_symlink() or not p.is_file(): return ''
    if not p.resolve().is_relative_to(repo.resolve()): return ''
    return p.read_text(encoding='utf-8', errors='replace')


def detect_ai(repo, paths, commits=30):
    """Local equivalent of two levels, on the same SHA as CK. Errors propagate."""
    paths = set(paths)
    evidence = []
    for agent, patterns in ARQUIVOS_AGENTES.items():
        for pattern in patterns:
            base = pattern.rstrip('/')
            hits = sorted(p for p in paths if p == base or p.startswith(base + '/'))
            if hits:
                evidence.append({'agent': agent, 'type': 'file', 'path': hits[0]})
    # Include directory heuristics explicitly described in the article.
    for agent, base in [('Claude Code', '.claude'), ('Codex / OpenAI', '.codex')]:
        hits = sorted(p for p in paths if p.startswith(base + '/'))
        if hits and not any(e['agent'] == agent for e in evidence):
            evidence.append({'agent': agent, 'type': 'file', 'path': hits[0]})
    if not evidence:
        for line in read_local(repo, '.gitignore').splitlines():
            line = line.strip()
            if not line or line.startswith(('#', '!')): continue
            for agent, patterns in GITIGNORE_AGENTES.items():
                for pattern in patterns:
                    if pattern in line:
                        evidence.append({'agent': agent, 'type': 'gitignore', 'path': '.gitignore', 'line': line})
    recent = []
    if not evidence:
        raw = run(['git', 'log', '-n', str(commits), '--format=%H%x00%aI%x00%an%x00%ae%x00%B%x00%x1e'], cwd=repo)
        for record in raw.split('\x1e'):
            fields = record.strip('\n').split('\x00')
            if len(fields) < 5: continue
            sha, date, author, email, message = fields[:5]
            recent.append({'sha': sha, 'date': date, 'author': author, 'email': email, 'message': message})
            identity = (author + ' ' + email).lower()
            for bot in BOTS_AUTORES:
                # Git data has author name/email, not the REST author's account login.
                if re.search(r'(?<![\w-])' + re.escape(bot.lower()) + r'(?![\w-])', identity):
                    evidence.append({'agent': bot, 'type': 'author_identity', 'sha': sha, 'identity': identity})
            for trailer in re.findall(r'^Co-authored-by:\s*(.+)$', message, flags=re.I | re.M):
                for agent, patterns in COAUTHORED_AGENTES.items():
                    if any(p.lower() in trailer.lower() for p in patterns):
                        evidence.append({'agent': agent, 'type': 'coauthor', 'sha': sha, 'trailer': trailer})
        if not recent: raise ValueError('Histórico indisponível: classificação de IA indeterminada')
    return {'ia_status': 'com_evidencia' if evidence else 'sem_evidencia_detectada',
            'ia_level': 1 if any(e['type'] in ('file', 'gitignore') for e in evidence) else (2 if evidence else 0),
            'ia_agents': '; '.join(sorted({e['agent'] for e in evidence})),
            'ia_method': 'local_files_then_git_last_n', 'ia_commits_requested': commits,
            'ia_commits_scanned': len(recent), 'evidence': evidence, 'commits': recent}


def spring_boot(repo, paths):
    evidence, versions, java_versions = [], set(), set()
    for path in paths:
        if Path(path).name not in {'pom.xml', 'build.gradle', 'build.gradle.kts', 'gradle.properties', 'libs.versions.toml'}: continue
        if any(p in IGNORED_PARTS for p in Path(path).parts): continue
        text = read_local(repo, path)
        clean = re.sub(r'<!--.*?-->', '', text, flags=re.S)
        if Path(path).name == 'pom.xml':
            try:
                root = ET.fromstring(clean)
                for el in root.iter(): el.tag = el.tag.split('}')[-1]
                props = {c.tag: c.text or '' for c in root.findall('./properties/*')}
                for key in ('java.version', 'maven.compiler.source', 'maven.compiler.release'):
                    if props.get(key): java_versions.add(props[key])
                for node in root.iter():
                    if node.tag not in {'parent', 'dependency', 'plugin'}: continue
                    group = node.findtext('groupId', '')
                    artifact = node.findtext('artifactId', '')
                    if group != 'org.springframework.boot': continue
                    evidence.append({'file': path, 'artifact': artifact})
                    v = node.findtext('version', '')
                    if v.startswith('${') and v.endswith('}'): v = props.get(v[2:-1], v)
                    if v: versions.add(v)
                # A Spring Boot source checkout is retained, with explicit provenance.
                if root.findtext('groupId') == 'org.springframework.boot' and root.findtext('artifactId', '').startswith('spring-boot'):
                    evidence.append({'file': path, 'artifact': root.findtext('artifactId'), 'kind': 'framework_source'})
                    if root.findtext('version'): versions.add(root.findtext('version'))
            except ET.ParseError:
                # No positive inference from malformed XML.
                pass
        else:
            clean = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
            clean = re.sub(r'^\s*//.*$', '', clean, flags=re.M)
            if re.search(r'[\'\"]org\.springframework\.boot(?:[:\'\"])', clean):
                evidence.append({'file': path, 'artifact': 'Gradle Spring Boot declaration'})
            for pattern in [r'org\.springframework\.boot[\'\"]\s*\)?\s*version\s*[\(]?\s*[\'\"]([^\'\"]+)',
                            r'org\.springframework\.boot:spring-boot[^:\s\'\"]*:(\d[^\s\'\"]*)',
                            r'(?:springBootVersion|spring-boot(?:\.version)?)\s*[=:]\s*[\'\"]?(\d[\w.\-]+)']:
                versions.update(re.findall(pattern, clean))
    numeric = sorted(v for v in versions if re.fullmatch(r'\d+(?:\.[\w-]+)+', v))
    majors = sorted({v.split('.')[0] for v in numeric})
    return {'spring_boot_confirmed': bool(evidence), 'spring_boot_versions': ';'.join(sorted(versions)),
            'spring_boot_major': majors[0] if len(majors) == 1 else ('multiple' if majors else 'unknown'),
            'java_versions_declared': ';'.join(sorted(java_versions)), 'build_evidence': evidence}


def read_metrics(path):
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows, set(reader.fieldnames or [])


def average(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) not in (None, '') and math.isfinite(float(r[key]))]
    return (sum(values) / len(values) if values else None), len(values)


def aggregate(class_rows, method_rows):
    result = {'classes': len(class_rows), 'methods': len(method_rows)}
    for target, source in CLASS_COLUMNS.items():
        result[target], result['n_' + source.replace('*', '_star')] = average(class_rows, source)
    result['avg_loc_method'], result['n_loc_method'] = average(method_rows, 'loc')
    result['avg_lcom_legacy'], _ = average(class_rows, 'lcom')
    result['ck_class_loc_sum'] = sum(float(r['loc']) for r in class_rows)
    for source in ('cbo', 'rfc', 'wmc'):
        result['sum_' + source] = sum(float(r[source]) for r in class_rows)
    return result


def process_repository(row, config, out, external=None):
    started = time.monotonic()
    rid = row['repository_id']
    result_dir = out / 'repositories' / rid
    result_dir.mkdir(parents=True, exist_ok=True)
    status_file = result_dir / 'result.json'
    result = dict(row, epoch=cohort(row['created_at']), status='running', ia_status='indeterminada',
                  extracted_at=now(), protocol=PROTOCOL, eligible=False)
    atomic_json(status_file, result)
    try:
        with tempfile.TemporaryDirectory(prefix=rid + '-', dir=out / 'work') as temp:
            temp = Path(temp)
            repo, source, raw_dir = temp / 'repo', temp / 'source', temp / 'ck'
            branch = row['default_branch']
            command = ['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--quiet', '--no-tags', '--single-branch',
                       '--depth', str(config['commits']), '--branch', branch, '--', f'https://github.com/{row["full_name"]}.git', str(repo)]
            run(command, timeout=config['clone_timeout'])
            result['commit_sha'] = run(['git', 'rev-parse', 'HEAD'], cwd=repo).strip()
            result['commit_date'] = run(['git', 'show', '-s', '--format=%cI', 'HEAD'], cwd=repo).strip()
            result['snapshot_relation'] = 'head_at_extraction_not_september_snapshot'
            paths = run(['git', 'ls-files', '-z'], cwd=repo).split('\0')
            paths = [p for p in paths if p]
            detection = external if external is not None else (detect_ai(repo, paths, config['commits']) if config.get('detect_ai') else {'ia_status': 'indeterminada', 'ia_method': 'awaiting_external_csv', 'evidence': [], 'commits': []})
            atomic_json(result_dir / 'ia_evidence.json', dict(detection, commit_sha=result['commit_sha'], extracted_at=result['extracted_at']))
            result.update({k: v for k, v in detection.items() if k not in {'evidence', 'commits'}})
            boot = spring_boot(repo, paths)
            atomic_json(result_dir / 'build_evidence.json', boot)
            result.update({k: v for k, v in boot.items() if k != 'build_evidence'})
            inventory = []
            for path in paths:
                if not is_source(path): continue
                original = repo / path
                if original.is_symlink() or not original.is_file(): continue
                content = original.read_bytes()
                sloc = java_sloc(content.decode('utf-8', errors='replace'))
                dest = source / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                inventory.append({'file': path, 'sha256': hashlib.sha256(content).hexdigest(), 'sloc': sloc, 'is_test': is_test(path), 'measurable_type': has_measurable_type(content.decode('utf-8', errors='replace'))})
            result['java_files'] = len(inventory)
            result['total_loc'] = sum(r['sloc'] for r in inventory)
            result['production_loc'] = sum(r['sloc'] for r in inventory if not r['is_test'])
            result['test_loc'] = result['total_loc'] - result['production_loc']
            with gzip.open(result_dir / 'source_inventory.csv.gz', 'wt', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['file', 'sha256', 'sloc', 'is_test', 'measurable_type']); w.writeheader(); w.writerows(inventory)
            if not inventory:
                result['status'] = 'no_java'
                result['exclusion_reasons'] = 'no_java'
            else:
                raw_dir.mkdir()
                ck_entry = ['-cp', config['jar'] + os.pathsep + config['runner_classes'], 'AuditedCKRunner'] if config.get('runner_classes') else ['-jar', config['jar']]
                ck_command = [config['java'], '-Xmx' + config['heap'], *ck_entry, str(source), 'false', str(config['partition']), 'false', str(raw_dir) + os.sep]
                atomic_json(result_dir / 'ck_command.json', ck_command)
                p = subprocess.run(ck_command, capture_output=True, text=True, errors='replace', timeout=config['ck_timeout'])
                log = p.stdout + '\n' + p.stderr
                (result_dir / 'ck.log').write_text(log, encoding='utf-8')
                if p.returncode: raise RuntimeError(f'CK exit={p.returncode}: {log[-1200:]}')
                classes, class_fields = read_metrics(raw_dir / 'class.csv')
                methods, method_fields = read_metrics(raw_dir / 'method.csv')
                if not set(CLASS_COLUMNS.values()).union({'loc', 'file', 'class', 'lcom'}) <= class_fields:
                    raise ValueError('CK sem colunas obrigatórias, incluindo lcom*')
                if not {'loc', 'file', 'class'} <= method_fields: raise ValueError('method.csv sem colunas obrigatórias')
                for name, rows, fields in [('class', classes, class_fields), ('method', methods, method_fields)]:
                    for record in rows:
                        record['file'] = str(Path(record['file']).relative_to(source))
                    with gzip.open(result_dir / f'{name}.csv.gz', 'wt', newline='', encoding='utf-8') as f:
                        w = csv.DictWriter(f, fieldnames=sorted(fields)); w.writeheader(); w.writerows(rows)
                if not classes or not methods: raise ValueError('CK não retornou classes e métodos analisáveis')
                result.update(aggregate(classes, methods))
                name_counts = Counter(r['class'] for r in classes)
                result['duplicate_class_names'] = sum(n > 1 for n in name_counts.values())
                result['classes_with_duplicate_names'] = sum(n for n in name_counts.values() if n > 1)
                atomic_json(result_dir / 'duplicate_class_names.json', {name:n for name,n in name_counts.items() if n > 1})
                production = aggregate([r for r in classes if not is_test(r['file'])], [r for r in methods if not is_test(r['file'])])
                result.update({'production_' + k: v for k, v in production.items()})
                files_parsed = {r['file'] for r in classes}
                expected = {r['file'] for r in inventory if Path(r['file']).name not in {'package-info.java', 'module-info.java'} and r['sloc'] > 0 and r['measurable_type']}
                missing = sorted(expected - files_parsed)
                atomic_json(result_dir / 'coverage.json', {'expected_files': len(expected), 'files_with_classes': len(files_parsed), 'files_without_class_output': missing})
                result['files_without_class_output'] = len(missing)
                result['source_coverage'] = len(expected & files_parsed) / len(expected) if expected else 0
                result['ck_error_signals'] = len(re.findall(r'CK_FILE_ERROR:|(?m:^.*(?:Exception in thread|java\.[\w.]*Exception|ERROR|Error parsing).*$)', log))
                result['status'] = 'ok' if not missing and not result['ck_error_signals'] else 'partial_ck'
                reasons = []
                if result['status'] != 'ok': reasons.append('incomplete_ck_coverage')
                if not result['spring_boot_confirmed']: reasons.append('spring_boot_not_confirmed')
                if result['total_loc'] < config['min_loc']: reasons.append('below_min_loc')
                # Extraction eligibility is independent of the availability of an IA label.
                if result['epoch'] == 'fora_das_coortes': reasons.append('outside_epochs')
                if any(result[m] is None for m in METRICS): reasons.append('missing_metric')
                result['exclusion_reasons'] = ';'.join(reasons)
                result['eligible'] = not reasons
                result['comparison_eligible'] = result['eligible'] and result['ia_status'] in {'com_evidencia', 'sem_evidencia_detectada'}
                for metric in ('cbo', 'rfc', 'wmc'):
                    result['density_' + metric + '_kloc'] = result['sum_' + metric] * 1000 / result['total_loc'] if result['total_loc'] else None
    except Exception as exc:
        result['status'] = 'error'
        result['comparison_eligible'] = False
        result['error'] = f'{type(exc).__name__}: {exc}'[:2500]
        result['eligible'] = False
    result['duration_seconds'] = round(time.monotonic() - started, 3)
    result['finished_at'] = now()
    atomic_json(status_file, result)
    return result
