"""Derive event marker facts from pinned original source jars, without executing them."""
import hashlib,json,zipfile
from java_frontend import parse_source
from java_symbols import declarations
from java_method_overloads import canonical
from workspace_paths import DEV_ROOT

def export():
    records={};sources=[];unparsed=[]
    for filename in ('neoforge-21.1.233-sources.jar','fml-4.0.42-sources.jar'):
        path=DEV_ROOT/'references'/filename
        sources.append({'file':filename,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith('.java'):continue
                ir=parse_source(archive.read(name),origin=name)
                if ir['parse_status']!='PARSED':unparsed.append({'jar':filename,'file':name,'errors':ir['syntax_errors']});continue
                for cls in declarations(ir)['classes']:
                    records[cls['java_name']]={'source_jar':filename,'source':name,'superclass':(cls['superclass'] or '').split('<',1)[0],'interfaces':cls['interfaces'] or '', 'imports':ir['imports'],'package':ir['package'],'name':cls['name'],'java_name':cls['java_name'],'external':True,'abstract':'abstract' in cls.get('modifiers',[])}
    def resolve(raw,row):
        if not raw:return None
        name=canonical(raw,row,{'_classes':[],'_project_types':records})
        if name in records:return name
        prefix=row['java_name'].rsplit('.',1)[0]
        while prefix and prefix.startswith(row['package']):
            if prefix+'.'+raw in records:return prefix+'.'+raw
            prefix=prefix.rsplit('.',1)[0]
        return name
    def related(name,target,seen=()):
        if name==target:return True
        if name in seen:raise ValueError('Cyclic source type '+name)
        row=records.get(name)
        if row is None:return False
        interfaces=row['interfaces'].replace('implements','',1).replace('extends','',1).strip().split(',')
        return any(resolve(raw.strip(),row)==target for raw in interfaces if raw.strip()) or related(resolve(row['superclass'],row),target,seen+(name,))
    events=[name for name in records if related(name,'net.neoforged.bus.api.Event')]
    mod=sorted(name for name in events if related(name,'net.neoforged.fml.event.IModBusEvent'))
    game=sorted(set(events)-set(mod))
    (DEV_ROOT/'java_event_bus_facts.py').write_text('"""Event bus facts from NeoForge21.1.233/FML4.0.42 original hierarchy."""\nMOD_BUS_TYPES = '+repr(tuple(mod))+'\nGAME_BUS_TYPES = '+repr(tuple(game))+'\nABSTRACT_EVENT_TYPES = '+repr(tuple(sorted(name for name in events if records[name]['abstract'])))+'\n',encoding='utf-8')
    (DEV_ROOT/'references/event_bus_facts_manifest.json').write_text(json.dumps({'source_jars':sources,'unparsed_sources':unparsed,'events':events,'mod_bus':mod,'game_bus':game,'records':{name:records[name] for name in events},'limits':'Known source Event inheritance only; unknown types require review.'},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'source_types':len(records),'events':len(events),'mod':len(mod),'game':len(game),'unparsed':len(unparsed)}
if __name__=='__main__':print(export())
