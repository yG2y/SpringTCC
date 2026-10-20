"""Pinned Git DAG, first-parent annual cuts and historically bounded AI evidence."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ck_pipeline.extraction import atomic_json, now, run
from detectar_agentes_ia import ARQUIVOS_AGENTES, BOTS_AUTORES, COAUTHORED_AGENTES, GITIGNORE_AGENTES
from spring_boot_selection.util import parse_iso


def redact(value):
    return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b', '[REDACTED_GITHUB_TOKEN]', str(value))


def git(repo, *args, timeout=600):
    return run(['git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null', *args], cwd=repo, timeout=timeout)


def pin_clone(row, out, timeout=900, reference_repo=None):
    repo = out/'clones'/str(row['repository_id'])
    record = out/'repositories'/str(row['repository_id'])/'reference.json'
    if record.exists():
        ref = json.loads(record.read_text())
        if not repo.exists():
            raise ValueError('Pinned clone missing; restore its objects instead of silently repinning HEAD')
        git(repo, 'cat-file', '-e', ref['tip']+'^{commit}')
        return repo, ref
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', row['full_name']):
        raise ValueError('Invalid GitHub repository name')
    repo.parent.mkdir(parents=True, exist_ok=True)
    temp = repo.with_name(repo.name+'.incomplete')
    if temp.exists():
        shutil.rmtree(temp)
    if not repo.exists():
        reuse = ['--reference-if-able', str(reference_repo), '--dissociate'] if reference_repo else []
        run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', *reuse, '--bare', '--single-branch', '--no-tags',
             'https://github.com/'+row['full_name']+'.git', str(temp)], timeout=timeout)
        temp.rename(repo)
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() != 'false':
        raise ValueError('Incomplete shallow history')
    branch = git(repo, 'symbolic-ref', 'HEAD').strip()
    tip = git(repo, 'rev-parse', 'HEAD').strip()
    git(repo, 'fsck', '--connectivity-only', '--no-dangling', tip, timeout=timeout)
    ref = dict(repository_id=row['repository_id'], full_name=row['full_name'], tip=tip,
               reference=branch, metadata_branch=row.get('default_branch'), pinned_at=now(),
               shallow=False, clone_mode='bare single default branch, all reachable history, no depth limit',
               object_cache=str(reference_repo) if reference_repo else None)
    atomic_json(record, ref)
    return repo, ref


def read_history(repo, tip):
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() != 'false':
        raise ValueError('Incomplete shallow history')
    raw = git(repo, 'log', '--topo-order', '--reverse', '--format=%H%x09%P%x09%cI%x09%aI', tip)
    commits = {}
    anomalies = []
    for line in raw.splitlines():
        sha, parents, committed, authored = line.split('\t')
        cdate, adate = parse_iso(committed), parse_iso(authored)
        if not cdate or not adate:
            raise ValueError('Invalid commit date: '+sha)
        parents = parents.split()
        if any(p not in commits for p in parents):
            raise ValueError('Incomplete or non-topological history: '+sha)
        maximum = max([cdate, adate]+[commits[p]['ancestry_max_date'] for p in parents])
        if any(cdate < commits[p]['committed'] for p in parents) or adate > cdate:
            anomalies.append(dict(sha=sha, kind='non_monotonic_dates', committed_at=committed, authored_at=authored))
        commits[sha] = dict(sha=sha, parents=parents, committed=cdate, authored=adate,
                            ancestry_max_date=maximum, integrated_index=None)
    line = list(reversed(git(repo, 'rev-list', '--first-parent', tip).splitlines()))
    for i, sha in enumerate(line):
        commits[sha]['integrated_index'] = i
    # Walk children before parents: each side-branch commit inherits the first
    # mainline position in which it is reachable, including merge integration.
    for c in reversed(list(commits.values())):
        index = c['integrated_index']
        for p in c['parents']:
            previous = commits[p]['integrated_index']
            commits[p]['integrated_index'] = index if previous is None else min(previous, index)
    return commits, line, anomalies


def annual_snapshots(commits, line, partial_cutoff, start=2009, last_complete=2025):
    cuts = [(y, datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc), False) for y in range(start, last_complete+1)]
    cuts.append((2026, partial_cutoff, True))
    previous = None
    snapshots = []
    for year, cutoff, partial in cuts:
        row = dict(year=year, cutoff=cutoff.isoformat(), partial=partial, status='missing_snapshot',
                   exclusion_reasons='no_history_before_cutoff', eligible=False)
        eligible = [(i, commits[s]) for i,s in enumerate(line) if commits[s]['committed'] <= cutoff]
        if eligible:
            index, c = eligible[-1]
            row.update(sha=c['sha'], mainline_index=index, committed_at=c['committed'].isoformat(),
                       authored_at=c['authored'].isoformat(), ancestry_max_date=c['ancestry_max_date'].isoformat(),
                       no_new_commit=c['sha'] == previous)
            if c['ancestry_max_date'] > cutoff:
                row.update(status='temporal_anomaly', exclusion_reasons='ancestor_or_author_date_after_cutoff')
            else:
                row.update(status='planned', exclusion_reasons='')
                previous = c['sha']
        snapshots.append(row)
    return snapshots


def tree(repo, sha):
    result = []
    for record in git(repo, 'ls-tree', '-r', '-z', sha).split('\x00'):
        if not record:
            continue
        header, path = record.split('\t', 1)
        mode, kind, oid = header.split()
        p = PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or '.git' in p.parts:
            raise ValueError('Unsafe tree path')
        result.append(dict(path=path, mode=mode, kind=kind, oid=oid))
    return result


def blob(repo, oid):
    p = subprocess.run(['git', '--no-replace-objects', 'cat-file', 'blob', oid], cwd=repo,
                       capture_output=True, timeout=120)
    if p.returncode:
        raise ValueError('Unavailable Git blob: '+oid)
    return p.stdout


def materialize(repo, sha, dest, needed):
    """Read blobs directly: no checkout hooks, symlinks, filters or export-ignore."""
    entries = tree(repo, sha)
    selected = [r for r in entries if r['kind']=='blob' and r['mode'] in {'100644','100755'} and needed(r['path'])]
    dest.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(['git', '--no-replace-objects', 'cat-file', '--batch'], cwd=repo,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for item in selected:
            process.stdin.write((item['oid']+'\n').encode()); process.stdin.flush()
            header = process.stdout.readline().decode().strip().split()
            if len(header)!=3 or header[1]!='blob':
                raise ValueError('Missing object: '+item['oid'])
            size = int(header[2])
            target = dest/item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('wb') as handle:
                while size:
                    block = process.stdout.read(min(size, 1024*1024))
                    if not block:
                        raise ValueError('Truncated Git object')
                    handle.write(block); size -= len(block)
            if process.stdout.read(1) != b'\n':
                raise ValueError('Invalid batch delimiter')
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=30)
    return entries


def file_signals(repo, entries):
    paths = {e['path'] for e in entries if e['kind']=='blob' and e['mode'] in {'100644','100755'}}
    result = []
    patterns_by_agent = dict(ARQUIVOS_AGENTES)
    patterns_by_agent['Claude Code'] = list(patterns_by_agent['Claude Code'])+['.claude/']
    for agent, patterns in patterns_by_agent.items():
        for pattern in patterns:
            base = pattern.rstrip('/')
            hits = sorted(p for p in paths if p==base or p.startswith(base+'/'))
            if hits:
                result.append(dict(agent=agent, type='file', path=hits[0]))
    ignore = next((e for e in entries if e['path']=='.gitignore' and e['mode'] in {'100644','100755'}), None)
    if ignore:
        for value in blob(repo, ignore['oid']).decode('utf-8', errors='replace').splitlines():
            value = value.strip()
            if not value or value.startswith(('#', '!')):
                continue
            for agent, patterns in GITIGNORE_AGENTES.items():
                if any(p in value for p in patterns):
                    result.append(dict(agent=agent, type='gitignore', path='.gitignore', line=redact(value)))
    return result


def ai_history(repo, tip, commits, line):
    """Positive evidence only persisted; scan all reachable commit identities/trailers."""
    events = []
    raw = git(repo, 'log', '--format=%H%x00%an%x00%ae%x00%B%x00%x1e', tip)
    for record in raw.split('\x1e'):
        fields = record.strip('\n').split('\x00')
        if len(fields)<4:
            continue
        sha, name, email, message = fields[:4]
        if sha not in commits:
            raise ValueError('Ambiguous commit record')
        identity = (name+' '+email).lower()
        signals = []
        for bot in BOTS_AUTORES:
            if re.search(r'(?<![\w-])'+re.escape(bot.lower())+r'(?![\w-])', identity):
                signals.append(dict(agent=bot, type='author_identity', identity=redact(identity)))
        for trailer in re.findall(r'^Co-authored-by:\s*(.+)$', message, flags=re.I|re.M):
            for agent, patterns in COAUTHORED_AGENTES.items():
                if any(p.lower() in trailer.lower() for p in patterns):
                    signals.append(dict(agent=agent, type='coauthor', trailer=redact(trailer)))
        for signal in signals:
            events.append(dict(signal, sha=sha, integrated_index=commits[sha]['integrated_index']))
    paths = sorted({p.rstrip('/') for patterns in ARQUIVOS_AGENTES.values() for p in patterns}|{'.gitignore','.claude','.codex'})
    changed = set(git(repo, 'log', '--first-parent', '--diff-merges=first-parent', '--format=%H', tip, '--', *paths).splitlines())
    for index, sha in enumerate(line):
        if sha in changed:
            for signal in file_signals(repo, tree(repo, sha)):
                events.append(dict(signal, sha=sha, integrated_index=index))
    for event in events:
        c = commits[event['sha']]
        integration = commits[line[event['integrated_index']]]
        event.update(committed_at=c['committed'].isoformat(), authored_at=c['authored'].isoformat(),
                     integrated_at=integration['committed'].isoformat(),
                     available_at=max(c['ancestry_max_date'], integration['ancestry_max_date']).isoformat())
    return sorted(events, key=lambda e: (e['integrated_index'], e['sha'], e['type']))


def ai_at_snapshot(repo, snapshot, events):
    cutoff = parse_iso(snapshot['cutoff'])
    historical = [e for e in events if e['integrated_index'] <= snapshot['mainline_index'] and parse_iso(e['available_at']) <= cutoff]
    present = file_signals(repo, tree(repo, snapshot['sha']))
    return dict(ia_status='com_evidencia' if historical or present else 'sem_evidencia_detectada',
                ia_present=bool(present), ia_history=bool(historical), present_evidence=present,
                historical_evidence=historical, first_observed=historical[0] if historical else None,
                ia_method='snapshot files and all reachable historical commit traces; first-parent file changes',
                caveat='Evidence observed, not exact first use; absence does not establish non-use')
