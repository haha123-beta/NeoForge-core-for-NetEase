"""Versioned classpath index and conservative JVM symbolic lookup."""
import gzip,hashlib,json,zipfile
from classfile import read,ClassFormatError


def archive_classes(path,target=21):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate ZIP names: '+str(path))
        manifest=z.read('META-INF/MANIFEST.MF').decode('utf-8',errors='replace') if 'META-INF/MANIFEST.MF' in z.namelist() else ''
        multi='multi-release: true' in manifest.lower();chosen={}
        for info in z.infolist():
            name=info.filename
            if not name.endswith('.class'):continue
            level=0
            if name.startswith('META-INF/versions/'):
                parts=name.split('/',3)
                if not multi or len(parts)!=4 or not parts[2].isdigit():continue
                level=int(parts[2]);name=parts[3]
                if level>target:continue
            if name.startswith('classes/'):name=name[8:]
            if name=='module-info.class':continue
            if level>chosen.get(name,(-1,None))[0]:chosen[name]=(level,info)
        for name,(level,info) in sorted(chosen.items()):
            if info.file_size>32*1024*1024:raise ValueError('Oversize class entry')
            yield name,z.read(info),level


class Index:
    def __init__(self,classes):self.classes=classes
    def type(self,name):
        if name.startswith('['):return {'status':'ARRAY_TYPE','name':name}
        row=self.classes.get(name)
        if row is None:return {'status':'NOT_IN_SELECTED_ABI','name':name}
        return {'status':'AMBIGUOUS_PROVIDER' if row.get('ambiguous') else 'FOUND','name':name,'definition':row}
    def member(self,owner,name,desc,kind):
        if owner.startswith('[') and name=='clone':return {'status':'ARRAY_CLONE','declaring_type':owner}
        if owner in ('java.lang.invoke.MethodHandle','java.lang.invoke.VarHandle'):
            row=self.classes.get(owner,{})
            if any(m['name']==name and any('PolymorphicSignature' in a for a in m.get('annotations',[])) for m in row.get('methods',[])):
                return {'status':'SIGNATURE_POLYMORPHIC','declaring_type':owner,'runtime_semantics':'JVM_ONLY_NOT_IMPLEMENTED'}
        todo=[owner];seen=set();unknown=[]
        while todo:
            current=todo.pop(0)
            if current in seen:continue
            seen.add(current);row=self.classes.get(current)
            if row is None or row.get('ambiguous'):
                unknown.append(current);continue
            for item in row['fields' if kind=='field' else 'methods']:
                if item['name']==name and item['descriptor']==desc:
                    return {'status':'FOUND','declaring_type':current,'member':item,'origin':row['origin']}
            if name not in ('<init>','<clinit>'):
                todo.extend(row.get('interfaces',[]));parent=row.get('superclass')
                if parent:todo.append(parent)
        return {'status':'UNKNOWN_HIERARCHY' if unknown else 'MEMBER_NOT_FOUND','unresolved_ancestors':sorted(unknown),'searched':sorted(seen)}


def build(lock,output):
    classes={};counts={};errors=[];overrides=[]
    for artifact in lock['artifacts']:
        count=0
        for entry,raw,level in archive_classes(artifact['path'],artifact['multi_release_target']):
            try:row=read(raw,code=False)
            except (ValueError,IndexError,KeyError) as error:
                errors.append({'artifact':artifact['id'],'entry':entry,'error':str(error)});continue
            if row['name'].replace('.','/')+'.class'!=entry:raise ValueError('Class entry/name mismatch: '+entry)
            if row['major']>65:raise ValueError('Class newer than selected Java21 target: '+entry)
            row={key:row[key] for key in ('name','superclass','interfaces','access','major','minor','fields','methods','annotations','signature','record_components','NestHost','NestMembers','PermittedSubclasses','enclosing_method') if key in row}
            row.update(class_sha256=hashlib.sha256(raw).hexdigest(),origin={'artifact':artifact['id'],'path':artifact['path'],'sha256':artifact['sha256'],
                'entry':entry,'multi_release_version':level,'version':artifact['version'],'role':artifact['role']})
            old=classes.get(row['name'])
            if old:
                if old['class_sha256']==row['class_sha256']:
                    old.setdefault('identical_origins',[]).append(row['origin']);count+=1;continue
                roles={old['origin']['role'],artifact['role']}
                if roles=={'minecraft_base','minecraft_patches'}:
                    if artifact['role']=='minecraft_patches':
                        row['overridden_base']=old['origin'];classes[row['name']]=row
                    else:old['overridden_base']=row['origin']
                    overrides.append(row['name'])
                else:
                    old['ambiguous']=True;old.setdefault('conflicting_origins',[]).append(row['origin'])
            else:classes[row['name']]=row
            count+=1
        counts[artifact['id']]=count
    if errors:raise ValueError('ABI parse errors are fatal, not skipped: '+json.dumps(errors[:5]))
    result={'schema_version':1,'target':lock['target'],'counts_by_artifact':counts,'classes':classes,
        'patch_overrides':sorted(set(overrides)),'ambiguous_types':sorted(n for n,r in classes.items() if r.get('ambiguous')),
        'limits':['Selected classpath and explicit JDK modules only','Presence is not a NeoCore runtime implementation','No access/initialization/dynamic-dispatch proof']}
    with gzip.GzipFile(filename=str(output),mode='wb',mtime=0) as stream:
        stream.write(json.dumps(result,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode())
    return result


def load_index(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)
