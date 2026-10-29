"""Explicit input locks. Analysis never imports production implementations."""
from pathlib import Path
import hashlib,json,re,tomllib,zipfile,xml.etree.ElementTree as ET

VERSION='0.9.1'
MOD_SHA='78d1ae72dcf675d8dfe892a4a2b6949ad507c184a6b39e2d3413c03a783c5407'
RELEASE_SHA='4c092522d558a2a2f7d4c4533a8cb1fbca59f275e6a0dda0eda1c389c21a5659'
PINNED_BINARY_SHA={
 'minecraft_base':'a649bd3ce77f122d0f83ae1b37b4b303e662470f928b9bee5fbc76580805ffd4',
 'minecraft_patches':'76eb8896e24abc0f815b7752366217cb6e170630fdba2f31cab10a88734b38ae',
 'neoforge':'ff997bfd7db9735755545a0d073bfb56bef55a8c9dd17bc1bba215a5dd55fc0d'}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2),encoding='utf-8')
def locked(path,**extra):
    path=Path(path).resolve()
    return dict(path=str(path),sha256=digest(path),size=path.stat().st_size,**extra)
def numeric_range(version,expression):
    expression=''.join(expression.split())
    def number(value):
        if not re.fullmatch(r'\d+(?:\.\d+)*',value):raise ValueError('Unreviewed version comparator input')
        return tuple(int(v) for v in value.split('.'))+(0,)*8
    actual=number(version)
    # Pad to equal length so 1.21 == 1.21.0.
    def compare(v):
        a=list(actual);b=list(number(v));size=max(len(a),len(b));return (a+[0]*size)[:size],(b+[0]*size)[:size]
    if expression.startswith('[') and expression.endswith(']') and ',' not in expression:
        a,b=compare(expression[1:-1]);return a==b
    if not expression or expression[0] not in '[(' or expression[-1] not in '])' or expression.count(',')!=1:raise ValueError('Unreviewed version range')
    low,high=expression[1:-1].split(',')
    if low:
        a,b=compare(low)
        if a<b or a==b and expression[0]=='(':return False
    if high:
        a,b=compare(high)
        if a>b or a==b and expression[-1]==')':return False
    return True
def verify(lock):
    if lock['target']!={'minecraft':'1.21.1','neoforge':'21.1.233','fml':'4.0.42','jdk':'21.0.10','namespace':'named'}:
        raise ValueError('Unreviewed target version/namespace profile')
    for row in lock['inputs'].values():
        if digest(row['path'])!=row['sha256']:raise ValueError('Input hash mismatch: '+row['path'])
    for row in lock['artifacts']:
        if digest(row['path'])!=row['sha256']:raise ValueError('Artifact hash mismatch: '+row['id'])
        if row['role'] in PINNED_BINARY_SHA and row['sha256']!=PINNED_BINARY_SHA[row['role']]:raise ValueError('Unreviewed official binary version: '+row['id'])
        if row.get('origin') in lock['inputs'] and row.get('origin_sha256')!=lock['inputs'][row['origin']]['sha256']:raise ValueError('Artifact provenance mismatch')
    loader=next(a for a in lock['artifacts'] if a['coordinate']=='net.neoforged.fancymodloader:loader:4.0.42')
    with zipfile.ZipFile(loader['path']) as z:
        if 'Build-Number: 4.0.42' not in z.read('META-INF/MANIFEST.MF').decode('utf-8'):raise ValueError('FML manifest version mismatch')
    frozen=Path(lock['frozen_release'])
    if lock['inputs']['release_archive']['sha256']!=RELEASE_SHA:raise ValueError('Not the frozen 0.9.0 release')
    with zipfile.ZipFile(lock['inputs']['release_archive']['path']) as archive:
        prefix='NeoCore-0.9.0/'
        for input_key,filename in [('baseline','真实后台转换报告.json'),('baseline_validation','后台产物校验.json'),
                                   ('review_zip','砧板-32of130-源码审查.zip'),('release_manifest','发行校验.json')]:
            if hashlib.sha256(archive.read(prefix+filename)).hexdigest()!=lock['inputs'][input_key]['sha256']:
                raise ValueError('Baseline input differs from frozen release: '+input_key)
    expected={k:v for k,v in load(lock['inputs']['release_manifest']['path'])['files'].items() if k.startswith('backend/')}
    if lock['production_files']!=expected:raise ValueError('Production protection manifest altered')
    for rel,expected in lock['production_files'].items():
        if digest(frozen/rel)!=expected:raise ValueError('Frozen production source mismatch: '+rel)

def create_default(destination):
    release=Path(r'C:\Users\YOUR_USER\Downloads\neocore\NeoCore-0.9.0')
    evidence=Path(r'D:\NeoCore工具\dev\builds\gpt_values_090')
    official=Path(r'D:\NeoCore工具\neoforge官方文件');libs=Path(r'F:\PCL\.minecraft\libraries')
    ref=Path(r'D:\NeoCore工具\dev\references\minecraft-1.21.1')
    jar=Path(r'D:\NeoCore工具\dev\references\partial-0.8.1\input\ManaitaPlus-NeoForge-1.21.1-0.1.1.1.jar')
    if digest(jar)!=MOD_SHA:raise ValueError('Wrong fixed mod JAR')
    inputs={'mod':locked(jar),'baseline':locked(evidence/'final_report.json'),
            'baseline_validation':locked(evidence/'backend_validation.json'),
            'review_zip':locked(release/'砧板-32of130-源码审查.zip'),
            'production_index':locked(release/'backend/dev/java_import_index.json'),
            'release_manifest':locked(release/'发行校验.json'),
            'release_archive':locked(release.parent/'NeoCore-0.9.0-完整发行.zip'),
            'pom':locked(official/'neoforge-21.1.233.pom'),
            'installer':locked(official/'neoforge-21.1.233-installer.jar'),
            'official_sources':locked(official/'neoforge-21.1.233-sources.jar'),
            'minecraft_version':locked(ref/'version.json'),
            'minecraft_mappings':locked(ref/'client_mappings.txt')}
    with zipfile.ZipFile(inputs['installer']['path']) as z:install=json.loads(z.read('version.json'))
    if install['inheritsFrom']!='1.21.1':raise ValueError('Installer Minecraft version mismatch')
    pom=ET.parse(inputs['pom']['path']);ns={'m':'http://maven.apache.org/POM/4.0.0'}
    deps={}
    for d in pom.findall('m:dependencies/m:dependency',ns):
        get=lambda name:d.findtext('m:'+name,namespaces=ns)
        deps[(get('groupId'),get('artifactId'))]=get('version')
    if deps.get(('net.neoforged.fancymodloader','loader'))!='4.0.42':raise ValueError('Wrong loader pin')
    selections={};missing=[]
    for origin,rows in [('minecraft_version',load(ref/'version.json')['libraries']),('installer',install['libraries'])]:
        for row in rows:
            coordinate=row['name'];parts=coordinate.split(':');artifact=row.get('downloads',{}).get('artifact')
            if not artifact:continue
            group,name,version=parts[:3];key=(group,name,parts[3] if len(parts)>3 else '')
            path=libs/artifact['path']
            if path.is_file():
                if artifact.get('sha1') and hashlib.sha1(path.read_bytes()).hexdigest()!=artifact['sha1']:raise ValueError('Maven SHA1 mismatch '+coordinate)
                selections[key]=locked(path,id=coordinate,coordinate=coordinate,version=version,
                    role='platform_library',origin=origin,origin_sha256=inputs[origin]['sha256'],
                    expected_sha1=artifact.get('sha1'),namespace='named',multi_release_target=21)
            else:missing.append({'coordinate':coordinate,'expected_path':str(path),'origin':origin})
    explicit=[('minecraft-named-base','net.minecraft:client:1.21.1-20240808.144430:srg','minecraft_base',libs/'net/minecraft/client/1.21.1-20240808.144430/client-1.21.1-20240808.144430-srg.jar'),
              ('neoforge-patches','net.neoforged:neoforge:21.1.233:client','minecraft_patches',libs/'net/neoforged/neoforge/21.1.233/neoforge-21.1.233-client.jar'),
              ('neoforge','net.neoforged:neoforge:21.1.233:universal','neoforge',official/'neoforge-21.1.233-universal.jar')]
    artifacts=list(selections.values())
    explicit_paths={str(p.resolve()) for _,_,_,p in explicit}
    artifacts=[a for a in artifacts if a['path'] not in explicit_paths]
    for id,coord,role,path in explicit:
        artifacts.append(locked(path,id=id,coordinate=coord,version='21.1.233' if role!='minecraft_base' else '1.21.1-20240808.144430',role=role,
            origin='installer',origin_sha256=inputs['installer']['sha256'],namespace='named',multi_release_target=21))
    # JDK modules are explicitly scoped; absence outside these modules is UNKNOWN.
    jdk=Path(r'E:\Java\jdk-21.0.10')
    inputs['jdk_release']=locked(jdk/'release')
    if 'JAVA_VERSION="21.0.10"' not in (jdk/'release').read_text():raise ValueError('JDK version mismatch')
    for name in ('java.base','java.desktop','java.logging','java.management','java.naming','jdk.unsupported'):
        artifacts.append(locked(jdk/'jmods'/ (name+'.jmod'),id='jdk:'+name,coordinate='jdk:'+name+':21.0.10',version='21.0.10',
            role='jdk',origin='jdk_release',origin_sha256=inputs['jdk_release']['sha256'],namespace='named',multi_release_target=21))
    curios=Path(r'F:\PCL\.minecraft\versions\我这混乱的模组包\mods\curios-neoforge-9.5.1+1.21.1.jar')
    third=[]
    if curios.is_file():
        with zipfile.ZipFile(curios) as z:
            meta_name=next(n for n in ('META-INF/neoforge.mods.toml','META-INF/mods.toml') if n in z.namelist())
            meta=tomllib.loads(z.read(meta_name).decode('utf-8'));mod=next(x for x in meta['mods'] if x['modId']=='curios')
            constraints=meta.get('dependencies',{}).get('curios',[])
            version=mod['version']
            if version=='${file.jarVersion}':
                manifest=z.read('META-INF/MANIFEST.MF').decode('utf-8')
                version=next(line.split(': ',1)[1] for line in manifest.splitlines() if line.startswith('Implementation-Version: '))
            mc=next(x['versionRange'] for x in constraints if x['modId']=='minecraft')
            # This profile is deliberately narrow, not a permissive Maven range parser.
            neo=next(x['versionRange'] for x in constraints if x['modId']=='neoforge')
            if version!='9.5.1+1.21.1' or not numeric_range('1.21.1',mc) or not numeric_range('21.1.233',neo):raise ValueError('Curios version/range mismatch: '+str((version,mc,neo)))
            row=locked(curios,id='thirdparty:curios',coordinate='curios:'+version,version=version,role='third_party',origin='embedded_mod_metadata',
                mod_id='curios',minecraft_constraint=mc,neoforge_constraint=neo,metadata_entry=meta_name,metadata_sha256=hashlib.sha256(z.read(meta_name)).hexdigest(),
                selection='analysis_test_pin; consumer does not declare a required version',namespace='named',multi_release_target=21)
            artifacts.append(row);third.append({'id':'curios','state':'VERSION_PINNED_ANALYSIS_ONLY','artifact':row['id'],'production_implementation':'NOT_SUPPLIED'})
    third.append({'id':'jei','state':'UNRESOLVED_VERSION','reason':'No verified NeoForge 1.21.1 candidate selected; a Fabric 1.21.11 JAR is not a substitute'})
    production={k:v for k,v in load(release/'发行校验.json')['files'].items() if k.startswith('backend/')}
    lock={'schema_version':1,'analyzer_version':VERSION,'target':{'minecraft':'1.21.1','neoforge':'21.1.233','fml':'4.0.42','jdk':'21.0.10','namespace':'named'},
        'frozen_release':str(release),'inputs':inputs,'artifacts':artifacts,'third_party':third,'unavailable_declared_artifacts':missing,
        'production_files':production,'precedence':'minecraft_patches overrides minecraft_base; other duplicate classes require review',
        'excluded_sources':[{'path':str(official/'FancyModLoader-main'),'reason':'Unpinned main; Java25/test MC26.1, not FML4.0.42'}]}
    verify(lock);save(destination,lock);return lock
