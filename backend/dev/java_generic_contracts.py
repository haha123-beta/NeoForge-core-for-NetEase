"""Generic interface substitution and declared ancestry proofs, without erasure guesses."""
import copy,re
from java_method_overloads import canonical
from java_official_type_hierarchy import PARENTS
from java_official_event_hierarchy import PARENTS as EVENT_PARENTS

def substitute(kind,bindings):
    return re.sub(r'\b(?:'+ '|'.join(re.escape(k) for k in bindings)+r')\b',lambda match:bindings[match[0]],kind)

def proves_bound(argument,bound,unit,project_types):
    from java_library_signatures import REVIEWED_PARENTS
    from java_entity_signatures import PARENTS as REGISTRY_PARENTS
    bound=bound.split('<',1)[0];pending=[argument];seen=set()
    while pending:
        identity=pending.pop()
        if identity==bound or bound=='java.lang.Object':return True
        if identity in seen:continue
        seen.add(identity);pending.extend(PARENTS.get(identity,[]));pending.extend(EVENT_PARENTS.get(identity,[]));pending.extend(REVIEWED_PARENTS.get(identity,[]));pending.extend(REGISTRY_PARENTS.get(identity,[]))
        declarations=[r for r in unit.get('_classes',[]) if r['java_name']==identity]
        declarations.extend(r['inheritance_metadata'] for r in project_types.get(identity,[]) if r.get('inheritance_metadata'))
        for row in declarations:
            for raw in (row.get('superclass'),row.get('interfaces'),row.get('interface_extends')):
                if not raw:continue
                raw=raw.removeprefix('implements').removeprefix('extends').strip()
                erased='';depth=0
                for char in raw:
                    if char=='<':depth+=1
                    elif char=='>':depth-=1
                    elif depth==0:erased+=char
                context=dict(row,external=True)
                if 'imports' not in row:context.update(package=unit.get('package'),imports=unit.get('imports',[]))
                pending.extend(canonical(value.strip(),context,unit) for value in erased.split(',') if value.strip())
    return False

def specialize(template,arguments):
    row=copy.deepcopy(template);names=row.pop('type_parameters')
    bindings=dict(zip(names,arguments))
    for method in row['methods']:
        method['parameters']=[substitute(p,bindings) for p in method['parameters']]
        method['return_type']=substitute(method['return_type'],bindings)
    identity=row['java_name'];row['java_name']=identity+'<'+','.join(arguments)+'>'
    row['generic_binding']={'java_name':identity,'arguments':arguments}
    return row
