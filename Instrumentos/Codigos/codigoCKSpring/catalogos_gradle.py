"""Supplemental, static Groovy map/catalog resolution at one Git snapshot.

No Gradle execution. Only maps reachable through literal `apply from` links,
with an actual dependency-configuration use, count. Dynamic expressions stay
unresolved. This supplement has its own fingerprint, separate from CK extraction.
"""
import re
import tomllib
from pathlib import PurePosixPath
from ck_pipeline.extraction import is_test

TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_$][\w$-]*|[^\s]', re.S)
PRODUCTION = {'implementation','api','compile','compileOnly','runtime','runtimeOnly','providedCompile'}
TEST = {'testImplementation','testCompile','testRuntime','testRuntimeOnly','testCompileOnly','testApi','testFixturesImplementation','testFixturesApi','integrationTestImplementation','integrationTestCompile'}
COORD = re.compile(r'^(org\.springframework(?:\.[\w.-]+)*):([\w.-]+)(?::(.+))?$')


def tokenize(text):
    return [(m[0],m.start()) for m in TOKEN.finditer(text) if not m[0].startswith(('//','/*'))]


def entries(tokens, start):
    """Map entries with nested lists, closures and strings kept intact."""
    items=[]; depth=0; begin=start+1
    for i in range(start+1,len(tokens)):
        t=tokens[i][0]
        if t==']' and depth==0:
            items.append(tokens[begin:i]);break
        if t==',' and depth==0:items.append(tokens[begin:i]);begin=i+1
        elif t in ('[','{','('):depth+=1
        elif t in (']','}',')'):depth-=1
    return [(x[0][0].strip('\'"'),x[2:]) for x in items if len(x)>2 and x[1][0]==':']


def strip_comments(text):
    chars=list(text)
    for m in TOKEN.finditer(text):
        if m[0].startswith(('//','/*')):
            chars[m.start():m.end()]=['\n' if c=='\n' else ' ' for c in m[0]]
    return ''.join(chars)


def resolve_version(value, props):
    for _ in range(10):
        new=re.sub(r'\$\{(\w+)\}|\$(\w+)',lambda m:props.get(m[1] or m[2],m[0]),value)
        if new==value:break
        value=new
    return value


def supplemental(builds):
    builds={p:strip_comments(t) for p,t in builds.items()}
    roots={p for p in builds if PurePosixPath(p).name in {'build.gradle','build.gradle.kts'}}
    links={p:set() for p in builds}
    # Literal paths only. A script's directory is not Gradle's project directory;
    # unqualified paths resolve against the applying build's project directory.
    apply_re=re.compile(r'\bapply\s+from\s*:\s*(?:(rootProject\.)?file\s*\(\s*)?[\'"]([^\'"\n]+)[\'"]')
    closures={}
    for root in sorted(roots):
        seen=set();todo=[root]
        while todo:
            path=todo.pop()
            if path in seen:continue
            seen.add(path)
            for match in apply_re.finditer(builds[path]):
                raw=match[2];rooted=bool(match[1]) or raw.startswith(('$rootDir/','${rootDir}/','$rootProject.projectDir/'))
                raw=re.sub(r'^\$(?:rootDir|rootProject\.projectDir)/|^\$\{rootDir\}/','',raw)
                if '$' in raw or '..' in PurePosixPath(raw).parts:continue
                target=str(PurePosixPath(raw) if rooted else PurePosixPath(root).parent/raw)
                if target in builds:todo.append(target);links[path].add(target)
        closures[root]=seen
    active=set().union(*closures.values()) if closures else set()
    definitions={};tokens_by_path={p:tokenize(builds[p]) for p in active}
    for path,tokens in tokens_by_path.items():
        for i in range(len(tokens)-4):
            if [x[0] for x in tokens[i:i+2]]==['ext','.'] and tokens[i+3][0]=='=' and tokens[i+4][0]=='[':
                name=tokens[i+2][0]
                for alias,value in entries(tokens,i+4):definitions.setdefault((name,alias),[]).append((path,value))
    evidence=[];unresolved=[]
    declared_props={p:re.findall(r'\b(\w+)\s*=\s*[\'"]([^\'"]*)[\'"]',t) for p,t in builds.items()}
    property_files={p:re.findall(r'(?m)^\s*(\w+)\s*=\s*([^\n\r]*)',t) for p,t in builds.items() if PurePosixPath(p).name=='gradle.properties'}
    parsed_catalogs={}
    for p,t in builds.items():
        if PurePosixPath(p).name!='libs.versions.toml':continue
        try:parsed_catalogs[p]=tomllib.loads(t)
        except tomllib.TOMLDecodeError:continue
    for path,tokens in sorted(tokens_by_path.items()):
        project_roots=[r for r in roots if PurePosixPath(r).parent in [PurePosixPath(path).parent,*PurePosixPath(path).parents]]
        accessible=set().union(*(closures[r] for r in project_roots)) if project_roots else set()
        # Applied root scripts inherit the root project's declarations.
        for root,closure in closures.items():
            if path in closure:accessible.update(closure)
        props={};conflicts=set()
        def property_value(k,v):
            if k in props and props[k]!=v:conflicts.add(k)
            else:props[k]=v
        for p,t in builds.items():
            if p in accessible:
                for k,v in declared_props[p]:property_value(k,v)
            if PurePosixPath(p).name=='gradle.properties' and PurePosixPath(p).parent in [PurePosixPath(path).parent,*PurePosixPath(path).parents]:
                for k,v in property_files[p]:property_value(k,v.strip())
        for k in conflicts:props.pop(k,None)
        catalogs={}
        for p,data in parsed_catalogs.items():
            # Default catalog belongs to <project>/gradle/libs.versions.toml.
            if PurePosixPath(p).parent.name!='gradle' or PurePosixPath(p).parent.parent not in [PurePosixPath(path).parent,*PurePosixPath(path).parents]:continue
            for alias,item in data.get('libraries',{}).items():
                if isinstance(item,str):coordinate=item
                elif isinstance(item,dict):
                    coordinate=item.get('module') or item.get('group','')+':'+item.get('name','')
                    version=item.get('version','')
                    if isinstance(version,dict):version=data.get('versions',{}).get(version.get('ref'),version.get('require',version.get('strictly','')))
                    coordinate+=':'+str(version)
                else:continue
                catalogs['libs.'+re.sub('[-_.]','.',alias)]=(coordinate,p)
        words=[x[0] for x in tokens]
        for i,config in enumerate(words):
            if config not in PRODUCTION|TEST:continue
            j=i+1
            if j<len(words) and words[j]=='(':j+=1
            if j+2>=len(words) or words[j+1]!='.':continue
            name,alias=words[j],words[j+2]
            choices=[(p,value) for p,value in definitions.get((name,alias),[]) if p in accessible]
            if not choices:continue
            distinct={tuple(x[0] for x in value) for p,value in choices}
            if len(distinct)!=1:
                unresolved.append(dict(file=path,alias=name+'.'+alias,reason='ambiguous_catalog_definition'));continue
            provider,value=choices[0];coordinates=[];braces=0;k=0
            while k<len(value):
                t=value[k][0]
                if t=='{':braces+=1
                elif t=='}':braces-=1
                elif braces==0:
                    if t[:1] in ('\'','"') and COORD.fullmatch(t[1:-1]):coordinates.append((t[1:-1],provider))
                    elif t=='libs' and k+2<len(value) and value[k+1][0]=='.':
                        parts=['libs'];end=k+1
                        while end+1<len(value) and value[end][0]=='.' and re.fullmatch(r'[\w$-]+',value[end+1][0]):
                            if value[end+1][0]=='get':break
                            parts.append(value[end+1][0]);end+=2
                        accessor='.'.join(parts)
                        if accessor in catalogs:coordinates.append(catalogs[accessor])
                        k=end-1
                k+=1
            for coordinate,catalog in sorted(set(coordinates)):
                match=COORD.fullmatch(coordinate)
                if not match:continue
                group,artifact,version=match.groups();scope='test' if config in TEST or is_test(path) else 'production'
                evidence.append(dict(file=path,line=builds[path].count('\n',0,tokens[i][1])+1,coordinate=group+':'+artifact,
                    version=resolve_version(version or '',props),scope=scope,kind='groovy_catalog_usage',
                    framework='boot' if group=='org.springframework.boot' else 'spring',condition='static declaration; no Gradle execution',
                    alias=name+'.'+alias,provider=provider,catalog=catalog))
    unique={tuple(sorted(e.items())):e for e in evidence}
    return dict(evidence=list(unique.values()),unresolved=unresolved)


def amend(original, extra):
    result=dict(original);result['evidence']=original['evidence']+extra['evidence']
    result['catalog_resolution_diagnostics']=extra['unresolved']
    if not extra['evidence']:return result
    source=original['framework']=='framework_source'
    prod=[e for e in result['evidence'] if e['scope']=='production']
    boot=any(e['framework']=='boot' for e in prod) or bool(prod and any(e['framework']=='boot' and e['scope'] in {'parent_configuration','build_only'} for e in result['evidence']))
    kind='framework_source' if source else ('spring_boot' if boot else ('spring_traditional' if prod else ('test_only' if any(e['scope']=='test' for e in result['evidence']) else 'not_confirmed')))
    versions={e['version'] for e in result['evidence'] if e['version'] and e['scope'] in {'production','parent_configuration','build_only'} and e['framework']==('boot' if boot else 'spring')}
    result.update(framework=kind,framework_confirmed=kind in {'spring_boot','spring_traditional'},boot_present=boot and not source,
        framework_versions=';'.join(sorted(versions)),boot_prerelease=boot and any(re.search(r'(?:SNAPSHOT|[.-](?:M\d|RC\d|alpha|beta))',v,re.I) for v in versions),
        detection=original['detection']+'; supplemental reachable Groovy map/catalog usage')
    return result
