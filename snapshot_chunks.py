"""Split a generated core snapshot without changing the BUNDLE contract."""
import ast
import json
from pathlib import Path


def split_snapshot(path):
    path=Path(path)
    tree=ast.parse(path.read_bytes().decode('utf-8'))
    value=next(n.value for n in tree.body if isinstance(n,ast.Assign)
               and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
               and n.targets[0].id=='BUNDLE')
    if not (isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute)
            and isinstance(value.func.value,ast.Name) and value.func.value.id=='json'
            and value.func.attr=='loads' and len(value.args)==1 and not value.keywords):
        raise ValueError('Expected a fresh generated json.loads snapshot')
    payload=ast.literal_eval(value.args[0]);bundle=json.loads(payload)
    parts=[payload[i:i+65536] for i in range(0,len(payload),65536)]
    names=['_snapshot_data_%03d'%i for i in range(len(parts))]
    if any((path.parent/(name+'.py')).exists() for name in names):
        raise ValueError('Snapshot chunk destination already exists')
    for name,part in zip(names,parts):
        (path.parent/(name+'.py')).write_text('# Generated data; regenerate with scripts/build_addon.py\nDATA = '+repr(part)+'\n',encoding='ascii')
    code='# NeoCore snapshot chunks v1; generated data, same BUNDLE contract.\nimport json\n'
    code+=''.join('from .'+name+' import DATA as _p'+str(i)+'\n' for i,name in enumerate(names))
    code+='BUNDLE = json.loads('+ ' + '.join('_p'+str(i) for i in range(len(parts))) +')\n'
    code+='del '+', '.join('_p'+str(i) for i in range(len(parts)))+'\n'
    path.write_text(code,encoding='ascii')
    return dict(parts=len(parts),modules=len(bundle['sources']))
