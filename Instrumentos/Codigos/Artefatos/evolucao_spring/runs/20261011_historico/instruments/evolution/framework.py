"""Framework declarations at a snapshot, with scope and version provenance.

This is static declaration detection, not dependency resolution or a Maven build.
Unresolved properties remain explicit; catalogs alone do not prove adoption.
"""
from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from ck_pipeline.extraction import IGNORED_PARTS, is_test, read_local

BUILD_NAMES = {'pom.xml', 'build.gradle', 'build.gradle.kts', 'gradle.properties', 'libs.versions.toml'}


def needed(path):
    return Path(path).name in BUILD_NAMES and not any(p in IGNORED_PARTS for p in Path(path).parts)


def resolve(value, props):
    for _ in range(10):
        new = re.sub(r'\$\{([^}]+)\}', lambda m: props.get(m[1], m[0]), value)
        if new == value:
            break
        value = new
    return value


def detect(root, paths, full_name=''):
    evidence, diagnostics = [], []
    builds = {p: read_local(root, p) for p in paths if needed(p)}
    xml = {}
    for path, text in builds.items():
        if Path(path).name != 'pom.xml':
            continue
        try:
            doc = ET.fromstring(text)
            for e in doc.iter():
                e.tag = e.tag.split('}')[-1]
            xml[path] = doc
        except ET.ParseError:
            diagnostics.append(dict(file=path, reason='invalid_pom_xml'))

    def properties(path, visited=None):
        visited = set(visited or ())
        if path in visited or path not in xml:
            return {}
        visited.add(path)
        doc = xml[path]
        relative = doc.findtext('./parent/relativePath', '../pom.xml')
        parent_path = (root/Path(path).parent/relative).resolve() if relative else None
        props = properties(str(parent_path.relative_to(root.resolve())), visited) if parent_path and parent_path.is_relative_to(root.resolve()) else {}
        props.update({n.tag: n.text or '' for n in doc.findall('./properties/*')})
        for field in ('version', 'groupId', 'artifactId'):
            value = doc.findtext(field) or doc.findtext('./parent/'+field, '')
            props['project.'+field] = value
            props['pom.'+field] = value
        return props

    def add(path, coordinate, version, scope, kind, condition=''):
        group = coordinate.split(':')[0]
        if group != 'org.springframework' and not group.startswith('org.springframework.'):
            return
        evidence.append(dict(file=path, coordinate=coordinate, version=version, scope=scope, kind=kind,
                             framework='boot' if group=='org.springframework.boot' else 'spring', condition=condition))

    for path, doc in xml.items():
        props = properties(path)
        ancestry = {child: parent for parent in doc.iter() for child in parent}
        for node in doc.iter():
            if node.tag not in {'parent', 'dependency', 'plugin'}:
                continue
            tags, cursor = [], node
            while cursor in ancestry:
                cursor = ancestry[cursor]; tags.append(cursor.tag)
            group = resolve(node.findtext('groupId', ''), props)
            artifact = resolve(node.findtext('artifactId', ''), props)
            version = resolve(node.findtext('version', ''), props)
            scope = 'production'
            if node.tag == 'parent': scope = 'parent_configuration'
            elif 'pluginManagement' in tags: scope = 'managed_only'
            elif node.tag == 'plugin' or 'plugin' in tags: scope = 'build_only'
            elif 'dependencyManagement' in tags: scope = 'managed_only'
            elif node.findtext('scope') == 'test' or is_test(path): scope = 'test'
            add(path, group+':'+artifact, version, scope, node.tag, 'profile' if 'profile' in tags else '')
        group = resolve(doc.findtext('groupId', ''), props)
        artifact = doc.findtext('artifactId', '')
        if group in {'org.springframework', 'org.springframework.boot'} and artifact in {'spring-core','spring-context','spring-boot','spring-framework','spring-boot-project'}:
            add(path, group+':'+artifact, resolve(doc.findtext('version',''),props), 'framework_source', 'own_artifact')

    catalogs = {}
    for path, text in builds.items():
        if not path.endswith('libs.versions.toml'):
            continue
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            diagnostics.append(dict(file=path, reason='invalid_version_catalog')); continue
        versions = data.get('versions', {})
        for section in ('libraries', 'plugins'):
            for alias, item in data.get(section, {}).items():
                if isinstance(item, str):
                    parts = item.split(':'); coordinate = ':'.join(parts[:2]); version = parts[2] if len(parts)>2 else ''
                elif isinstance(item, dict):
                    coordinate = item.get('module') or (item.get('group','')+':'+item.get('name','')) if section=='libraries' else item.get('id','')
                    version = item.get('version', '')
                    if isinstance(version, dict):
                        version = versions.get(version.get('ref'), version.get('require', version.get('strictly','')))
                else:
                    continue
                if not isinstance(version, str): version = ''
                accessor = 'libs.'+('plugins.' if section=='plugins' else '')+re.sub(r'[-_.]', '.', alias)
                catalogs[accessor] = (path, coordinate, version, section)
                add(path, coordinate, version, 'catalog_only', section)

    for path, text in builds.items():
        if Path(path).name not in {'build.gradle', 'build.gradle.kts'}:
            continue
        clean = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        clean = re.sub(r'^\s*//.*$', '', clean, flags=re.M)
        props = {k:v for k,v in re.findall(r'(\w+)\s*=\s*[\'"]([^\'"]+)[\'"]', clean)}
        for match in re.finditer(r'(?<![\w.])(\w+)\s*\(?\s*[\'"](org\.springframework(?:\.[\w.-]+)*:[\w.-]+)(?::([^\'"\s]+))?[\'"]', clean):
            configuration, coordinate, version = match.groups()
            scope = 'test' if 'test' in configuration.lower() or is_test(path) else ('production' if configuration in {'implementation','api','compile','compileOnly','runtime','runtimeOnly','providedCompile'} else 'build_only')
            version = resolve(version or '', props)
            if version.startswith('$') and not version.startswith('${'): version = props.get(version[1:],version)
            add(path, coordinate, version, scope, 'gradle_dependency')
        for match in re.finditer(r'(?<![\w.])(\w+)\s*\(?\s*group\s*:\s*[\'"](org\.springframework(?:\.[\w.-]+)*)[\'"]\s*,\s*name\s*:\s*[\'"]([\w.-]+)[\'"](?:\s*,\s*version\s*:\s*[\'"]([^\'"]*)[\'"])?',clean):
            configuration,group,artifact,version=match.groups()
            scope='test' if 'test' in configuration.lower() or is_test(path) else ('production' if configuration in {'implementation','api','compile','compileOnly','runtime','runtimeOnly','providedCompile'} else 'build_only')
            add(path,group+':'+artifact,resolve(version or '',props),scope,'gradle_map_dependency')
        for match in re.finditer(r'id\s*\(?\s*[\'"]org\.springframework\.boot[\'"]\s*\)?(?:\s*version\s*\(?\s*[\'"]([^\'"]+)[\'"])?', clean):
            remainder=clean[match.end():].split('\n',1)[0]
            scope='managed_only' if re.search(r'\bapply\s+false\b',remainder) else 'build_only'
            add(path, 'org.springframework.boot', match[1] or '', scope, 'gradle_plugin')
        for accessor, (catalog, coordinate, version, section) in catalogs.items():
            for line in clean.splitlines():
                if not re.search(r'(?<![\w.])'+re.escape(accessor)+r'(?![\w.])', line):
                    continue
                configuration = re.match(r'\s*(\w+)', line)
                config = configuration[1] if configuration else ''
                scope = 'test' if 'test' in config.lower() or is_test(path) else ('production' if section=='libraries' and config in {'implementation','api','compile','compileOnly','runtime','runtimeOnly'} else 'build_only')
                add(path, coordinate, version, scope, 'catalog_usage', catalog)
    source = full_name.lower() in {'spring-projects/spring-framework','spring-projects/spring-boot'} or any(e['scope']=='framework_source' for e in evidence)
    prod = [e for e in evidence if e['scope']=='production']
    boot_config = [e for e in evidence if e['framework']=='boot' and e['scope'] in {'parent_configuration','build_only'}]
    boot = any(e['framework']=='boot' for e in prod) or bool(prod and boot_config)
    spring = bool(prod)
    kind = 'framework_source' if source else ('spring_boot' if boot else ('spring_traditional' if spring else ('test_only' if any(e['scope']=='test' for e in evidence) else 'not_confirmed')))
    versions = {e['version'] for e in evidence if e['version'] and e['scope'] in {'production','parent_configuration','build_only'} and (e['framework']=='boot' if boot else e['framework']=='spring')}
    return dict(framework=kind, framework_confirmed=kind in {'spring_traditional','spring_boot'},
                boot_present=boot and not source, framework_versions=';'.join(sorted(versions)),
                boot_prerelease=boot and any(re.search(r'(?:SNAPSHOT|[.-](?:M\d|RC\d|alpha|beta))',v,re.I) for v in versions),
                evidence=evidence, diagnostics=diagnostics,
                detection='declared dependencies; profiles recorded; no dependency download or project execution')
