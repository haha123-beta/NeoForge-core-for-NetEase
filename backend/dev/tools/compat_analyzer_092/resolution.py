"""Read-only symbolic resolution, reusing the 0.9.1 class reader/index.

Resolution does not prove access, dispatch selection or class initialization.
"""
import sys
from pathlib import Path
SHARED=Path(__file__).resolve().parents[1]/'compat_analyzer_091'
sys.path.insert(0,str(SHARED))
from abi import Index as PreviousIndex

class Index(PreviousIndex):
    def member(self,owner,name,desc,kind):
        if owner.startswith('['):
            if kind=='method' and name=='clone' and desc=='()Ljava/lang/Object;':return dict(status='ARRAY_CLONE',declaring_type=owner,access_check='NOT_PERFORMED',initialization='NOT_EXECUTED')
            if kind=='method':return self.member('java.lang.Object',name,desc,kind)
            return dict(status='MEMBER_NOT_FOUND',searched=[owner],unresolved_ancestors=[])
        if owner in ('java.lang.invoke.MethodHandle','java.lang.invoke.VarHandle'):
            return super().member(owner,name,desc,kind)
        searched=set();unknown=set()
        def row(identity):
            searched.add(identity);value=self.classes.get(identity)
            if value is None or value.get('ambiguous'):
                unknown.add(identity);return None
            return value
        def declared(identity,value):
            return next((m for m in value.get('fields' if kind=='field' else 'methods',[])
                         if m['name']==name and m['descriptor']==desc),None)
        def found(identity,m):
            return dict(status='FOUND',declaring_type=identity,member=m,origin=self.classes[identity].get('origin',{}),
                        access_check='NOT_PERFORMED',initialization='NOT_EXECUTED',dispatch='NOT_EXECUTED')
        def field(identity,seen):
            if identity in seen:return None
            seen.add(identity);value=row(identity)
            if value is None:return None
            item=declared(identity,value)
            if item:return found(identity,item)
            # JVMS 5.4.3.2: direct superinterfaces recursively, then superclass.
            for parent in value.get('interfaces',[]):
                result=field(parent,seen)
                if result:return result
            if value.get('superclass'):return field(value['superclass'],seen)
        if kind=='field':
            result=field(owner,set())
            if result and not unknown:return result
        else:
            value=row(owner)
            if value is not None:
                item=declared(owner,value)
                if item:return found(owner,item)
                if name in ('<init>','<clinit>'):
                    return dict(status='MEMBER_NOT_FOUND',searched=[owner],unresolved_ancestors=[])
                roots=[];seen=set();current=owner
                is_interface=bool(value.get('access',0)&0x200)
                if is_interface:
                    # Interface resolution may select public instance Object methods.
                    obj=row('java.lang.Object')
                    item=declared('java.lang.Object',obj) if obj else None
                    if item and item['access']&1 and not item['access']&8:return found('java.lang.Object',item)
                    roots.extend(value.get('interfaces',[]))
                else:
                    # JVMS 5.4.3.3: class chain precedes any interface methods.
                    while current and current not in seen:
                        seen.add(current);v=row(current)
                        if v is None:break
                        item=declared(current,v)
                        if item:return found(current,item)
                        roots.extend(v.get('interfaces',[]));current=v.get('superclass')
                candidates={};parents={};pending=list(roots);seen=set()
                while pending:
                    current=pending.pop()
                    if current in seen:continue
                    seen.add(current);v=row(current)
                    if v is None:continue
                    parents[current]=v.get('interfaces',[]);pending.extend(parents[current])
                    item=declared(current,v)
                    if item and not item['access']&(8|2):candidates[current]=item
                def descends(child,ancestor):
                    todo=list(parents.get(child,[]));visited=set()
                    while todo:
                        x=todo.pop()
                        if x==ancestor:return True
                        if x not in visited:visited.add(x);todo.extend(parents.get(x,[]))
                    return False
                maximal={n:m for n,m in candidates.items() if not any(descends(other,n) for other in candidates if other!=n)}
                concrete={n:m for n,m in maximal.items() if not m['access']&0x400}
                if not unknown:
                    if len(concrete)==1:
                        n=next(iter(concrete));return found(n,concrete[n])
                    if len(concrete)>1:return dict(status='DEFAULT_METHOD_CONFLICT',candidates=sorted(concrete))
                    if len(maximal)==1:
                        n=next(iter(maximal));return found(n,maximal[n])
                    if maximal:return dict(status='ABSTRACT_METHOD_SET',candidates=sorted(maximal),selection='JVM_ARBITRARY_NOT_GUESSED')
        return dict(status='UNKNOWN_HIERARCHY' if unknown else 'MEMBER_NOT_FOUND',
                    searched=sorted(searched),unresolved_ancestors=sorted(unknown))
