"""Audit every active AT row against actual runtime identities; never infer satisfaction."""
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path
import sys


def audit(path,catalog):
    rows=[]
    for number,line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(),1):
        text=line.split('#',1)[0].strip()
        if not text:continue
        parts=text.split();row={'line':number,'declaration':text,'status':'UNVERIFIED'}
        if len(parts) not in (2,3):row['status']='MALFORMED';rows.append(row);continue
        access,identity=parts[:2];target=catalog.get(identity)
        row.update(java_class=identity,access=access)
        if target is None:row['status']='MISSING_CLASS'
        elif len(parts)==2:row['status']='CLASS_PRESENT_ACCESS_UNRESTRICTED'
        else:
            member=parts[2];row['member']=member
            if '(' in member:
                name=member.split('(',1)[0]
                row['status']='METHOD_PRESENT_DESCRIPTOR_UNVERIFIED' if hasattr(target,name) else 'MISSING_METHOD'
            elif hasattr(target,member):row['status']='STATIC_FIELD_PRESENT_TYPE_UNVERIFIED'
            else:
                # Field spelling in source is evidence of declaration, not proof of per-instance initialization.
                try:source=inspect.getsource(target)
                except (OSError,TypeError):source=''
                import ast
                declared=False
                try:
                    tree=ast.parse(source)
                    declared=any(isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Store) and n.attr==member and isinstance(n.value,ast.Name) and n.value.id=='self' for n in ast.walk(tree))
                except (SyntaxError,IndentationError):pass
                row['status']='INSTANCE_FIELD_DECLARED_INITIALIZATION_UNVERIFIED' if declared else 'MISSING_OR_DYNAMIC_FIELD'
        rows.append(row)
    return {'scope':'runtime_presence_only_not_full_AT_equivalence','rows':rows,'active_rows':len(rows),
        'counts':dict(Counter(row['status'] for row in rows)), 'automatically_satisfied':False,
        'limits':['Descriptors, final writes and instance initialization require behavioral validation.','Python accessibility alone does not establish Java field or method semantics.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    from harness import Package
    pkg=Package();catalog=pkg.load('core.java_api').collect_java_api()
    result=audit(a.config,catalog);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'active_rows':result['active_rows'],'counts':result['counts']},ensure_ascii=False))


if __name__=='__main__':main()
