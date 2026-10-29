"""Bounded, non-executing JVMS class reader. No production/runtime imports."""
import bisect
import re
import struct


class ClassFormatError(ValueError):
    pass


class Reader:
    def __init__(self,data):self.data=data;self.pos=0
    def take(self,n):
        if n<0 or self.pos+n>len(self.data):raise ClassFormatError('Truncated class/attribute')
        value=self.data[self.pos:self.pos+n];self.pos+=n;return value
    def u1(self):return self.take(1)[0]
    def u2(self):return struct.unpack('>H',self.take(2))[0]
    def u4(self):return struct.unpack('>I',self.take(4))[0]
    def done(self):
        if self.pos!=len(self.data):raise ClassFormatError('Trailing attribute/class bytes')


def mutf8(data):
    units=[];i=0
    while i<len(data):
        a=data[i];i+=1
        if 1<=a<128:units.append(a);continue
        if a&224==192:
            if i>=len(data) or data[i]&192!=128:raise ClassFormatError('Invalid modified UTF8')
            value=((a&31)<<6)|(data[i]&63);i+=1
            if value<128 and not (a==192 and value==0):raise ClassFormatError('Overlong modified UTF8')
        elif a&240==224:
            if i+1>=len(data) or any(x&192!=128 for x in data[i:i+2]):raise ClassFormatError('Invalid modified UTF8')
            value=((a&15)<<12)|((data[i]&63)<<6)|(data[i+1]&63);i+=2
            if value<2048:raise ClassFormatError('Overlong modified UTF8')
        else:raise ClassFormatError('Invalid modified UTF8 lead')
        units.append(value)
    return b''.join(struct.pack('>H',v) for v in units).decode('utf-16-be',errors='surrogatepass')


def descriptor_types(value):
    """Descriptor/signature grammar, so TLEVEL; is not a fake class EVEL."""
    value=value or '';pos=0;result=set()
    def type_():
        nonlocal pos
        if pos>=len(value):raise ClassFormatError('Truncated type signature')
        token=value[pos];pos+=1
        if token in 'BCDFIJSZV*':return
        if token in '[+-^':type_();return
        if token=='T':
            end=value.find(';',pos)
            if end<0:raise ClassFormatError('Unclosed type variable')
            pos=end+1;return
        if token!='L':raise ClassFormatError('Invalid type signature token: '+token)
        name=''
        while pos<len(value):
            start=pos
            while pos<len(value) and value[pos] not in '<.;':pos+=1
            name+=value[start:pos]
            if not name or pos>=len(value):raise ClassFormatError('Unclosed class signature')
            result.add(name.replace('/','.'))
            if value[pos]=='<':
                pos+=1
                while pos<len(value) and value[pos]!='>':type_()
                if pos>=len(value):raise ClassFormatError('Unclosed type arguments')
                pos+=1
            if pos<len(value) and value[pos]=='.':name+='$';pos+=1;continue
            if pos<len(value) and value[pos]==';':pos+=1;return
            raise ClassFormatError('Invalid class signature suffix')
        raise ClassFormatError('Unclosed class signature')
    if value.startswith('<'):
        pos=1
        while pos<len(value) and value[pos]!='>':
            end=value.find(':',pos)
            if end<pos+1:raise ClassFormatError('Invalid type parameter')
            pos=end+1
            if pos<len(value) and value[pos]!=':':type_()
            while pos<len(value) and value[pos]==':':pos+=1;type_()
        if pos>=len(value):raise ClassFormatError('Unclosed type parameters')
        pos+=1
    while pos<len(value):
        if value[pos] in '()':pos+=1
        else:type_()
    return sorted(result)


def descriptor(value):
    """Validate field/method descriptors and expose exact parameter/return types."""
    pos=0
    def one(allow_void=False):
        nonlocal pos
        start=pos
        while pos<len(value) and value[pos]=='[':pos+=1
        rank=pos-start
        if pos>=len(value):raise ClassFormatError('Invalid descriptor')
        c=value[pos];pos+=1
        if c=='L':
            end=value.find(';',pos)
            if end<pos+1:raise ClassFormatError('Invalid reference descriptor')
            name=value[pos:end].replace('/','.');pos=end+1
        elif c in 'ZBCSIJFD':name=dict(Z='boolean',B='byte',C='char',S='short',I='int',J='long',F='float',D='double')[c]
        elif c=='V' and allow_void and not rank:name='void'
        else:raise ClassFormatError('Invalid descriptor type')
        return name+'[]'*rank
    if value.startswith('('):
        pos=1;args=[]
        while pos<len(value) and value[pos]!=')':args.append(one())
        if pos>=len(value):raise ClassFormatError('Unclosed method descriptor')
        pos+=1;result={'parameters':args,'return_type':one(True)}
    else:result={'field_type':one()}
    if pos!=len(value):raise ClassFormatError('Trailing descriptor bytes')
    return result


def read(data,code=True):
    r=Reader(data)
    if r.take(4)!=b'\xca\xfe\xba\xbe':raise ClassFormatError('Not a class')
    minor,major=r.u2(),r.u2();count=r.u2();pool=[None]*count;i=1
    while i<count:
        tag=r.u1()
        if tag==1:value=mutf8(r.take(r.u2()))
        elif tag in (3,4):value=r.take(4).hex()
        elif tag in (5,6):value=r.take(8).hex()
        elif tag in (7,8,16,19,20):value=r.u2()
        elif tag in (9,10,11,12,17,18):value=(r.u2(),r.u2())
        elif tag==15:value=(r.u1(),r.u2())
        else:raise ClassFormatError('Unknown constant pool tag '+str(tag))
        pool[i]=(tag,value);i+=2 if tag in (5,6) else 1
    def item(index,expected=None):
        if not 0<index<len(pool) or pool[index] is None:raise ClassFormatError('Invalid pool index')
        tag,value=pool[index]
        if expected is not None and tag!=expected:raise ClassFormatError('Wrong pool tag')
        return tag,value
    def utf(index):return item(index,1)[1]
    def cls(index):return utf(item(index,7)[1]).replace('/','.') if index else None
    def member(index):
        tag,value=item(index)
        if tag not in (9,10,11):raise ClassFormatError('Expected member reference')
        owner,nt=value;name,desc=item(nt,12)[1]
        return {'kind':'field' if tag==9 else 'interface_method' if tag==11 else 'method',
                'owner':cls(owner),'name':utf(name),'descriptor':utf(desc)}
    types=set();annotations=[];bootstrap=[];calls=[]
    def add_descriptor(text):types.update(descriptor_types(text))
    def element(a):
        tag=chr(a.u1())
        if tag in 'BCDFIJSZs':a.u2()
        elif tag=='e':add_descriptor(utf(a.u2()));a.u2()
        elif tag=='c':add_descriptor(utf(a.u2()))
        elif tag=='@':annotation(a)
        elif tag=='[':
            for _ in range(a.u2()):element(a)
        else:raise ClassFormatError('Invalid annotation value')
    def annotation(a):
        value=utf(a.u2());add_descriptor(value);annotations.append(value)
        for _ in range(a.u2()):a.u2();element(a)
    def attributes(a,context):
        found={};annotation_start=len(annotations)
        for _ in range(a.u2()):
            name=utf(a.u2());raw=a.take(a.u4());sub=Reader(raw);known=True
            if name=='SourceFile':found['source_file']=utf(sub.u2())
            elif name=='Signature':found['signature']=utf(sub.u2());add_descriptor(found['signature'])
            elif name=='ConstantValue':
                tag,value=item(sub.u2())
                if tag not in (3,4,5,6,8):raise ClassFormatError('Invalid ConstantValue tag')
                found['constant_value']={'tag':tag,'utf8':utf(value)} if tag==8 else {'tag':tag,'raw_bits_hex':value}
            elif name=='Record':
                components=[]
                for _ in range(sub.u2()):
                    component={'name':utf(sub.u2()),'descriptor':utf(sub.u2())};add_descriptor(component['descriptor'])
                    component.update(attributes(sub,component));components.append(component)
                found['record_components']=components
            elif name in ('NestHost','ModuleMainClass'):found[name]=cls(sub.u2())
            elif name in ('NestMembers','PermittedSubclasses'):found[name]=[cls(sub.u2()) for _ in range(sub.u2())]
            elif name=='EnclosingMethod':
                owner=cls(sub.u2());index=sub.u2();found['enclosing_method']={'owner':owner}
                if index:
                    n,d=item(index,12)[1];found['enclosing_method'].update(name=utf(n),descriptor=utf(d));add_descriptor(utf(d))
            elif name=='Exceptions':found['exceptions']=[cls(sub.u2()) for _ in range(sub.u2())];types.update(found['exceptions'])
            elif name in ('RuntimeVisibleAnnotations','RuntimeInvisibleAnnotations'):
                for _ in range(sub.u2()):annotation(sub)
            elif name in ('RuntimeVisibleParameterAnnotations','RuntimeInvisibleParameterAnnotations'):
                for _ in range(sub.u1()):
                    for _ in range(sub.u2()):annotation(sub)
            elif name in ('RuntimeVisibleTypeAnnotations','RuntimeInvisibleTypeAnnotations'):
                sizes={0:1,1:1,16:2,17:2,18:2,19:0,20:0,21:0,22:1,23:2,66:2,67:2,68:2,69:2,70:2,71:3,72:3,73:3,74:3,75:3}
                for _ in range(sub.u2()):
                    target=sub.u1()
                    if target in (64,65):sub.take(sub.u2()*6)
                    elif target in sizes:sub.take(sizes[target])
                    else:raise ClassFormatError('Unknown type annotation target')
                    sub.take(sub.u1()*2);annotation(sub)
            elif name=='AnnotationDefault':element(sub)
            elif name=='BootstrapMethods':
                for _ in range(sub.u2()):bootstrap.append({'method_handle':sub.u2(),'arguments':[sub.u2() for _ in range(sub.u2())]})
            elif name=='Code' and code:
                sub.u2();sub.u2();bytecode=sub.take(sub.u4())
                for _ in range(sub.u2()):
                    sub.u2();sub.u2();sub.u2();catch=cls(sub.u2())
                    if catch:types.add(catch)
                info=attributes(sub,context);lines=info.get('line_numbers',[])
                offsets=[v[0] for v in lines]
                for call in instructions(bytecode):
                    cp=call.pop('cp_index',None)
                    if cp is not None:
                        tag,value=item(cp)
                        if tag in (9,10,11):call['target']=member(cp)
                        elif tag in (17,18):
                            n,d=item(value[1],12)[1];call['dynamic']={'bootstrap_index':value[0],'name':utf(n),'descriptor':utf(d)}
                        elif tag==7:call['type']=cls(cp)
                        elif tag==15:call['method_handle']=member(value[1])
                        elif tag==16:add_descriptor(utf(value))
                    call.update(method=context['name'],method_descriptor=context['descriptor'])
                    line_index=bisect.bisect_right(offsets,call['offset'])-1
                    call['line']=lines[line_index][1] if line_index>=0 else None
                    calls.append(call)
            elif name=='LineNumberTable':found['line_numbers']=sorted((sub.u2(),sub.u2()) for _ in range(sub.u2()))
            elif name in ('LocalVariableTable','LocalVariableTypeTable'):
                for _ in range(sub.u2()):sub.u2();sub.u2();sub.u2();add_descriptor(utf(sub.u2()));sub.u2()
            else:known=False
            if known:sub.done()
        if len(annotations)>annotation_start:found['annotations']=sorted(set(annotations[annotation_start:]))
        return found
    flags,name,parent=r.u2(),cls(r.u2()),cls(r.u2())
    interfaces=[cls(r.u2()) for _ in range(r.u2())]
    members={}
    for kind in ('fields','methods'):
        rows=[]
        for _ in range(r.u2()):
            row={'access':r.u2(),'name':utf(r.u2()),'descriptor':utf(r.u2())}
            descriptor(row['descriptor']);add_descriptor(row['descriptor'])
            row.update(attributes(r,row));rows.append(row)
        members[kind]=rows
    meta=attributes(r,{});r.done();refs=[]
    for index,entry in enumerate(pool):
        if entry is None:continue
        tag,value=entry
        if tag==7:
            value=cls(index)
            if value.startswith('['):add_descriptor(value.replace('.','/'))
            else:types.add(value)
        elif tag in (9,10,11):
            ref=member(index);types.add(ref['owner']);add_descriptor(ref['descriptor']);refs.append(ref)
        elif tag==16:add_descriptor(utf(value))
        elif tag in (17,18):add_descriptor(utf(item(value[1],12)[1][1]))
    for call in calls:
        if 'dynamic' not in call:continue
        n=call['dynamic']['bootstrap_index']
        if n>=len(bootstrap):raise ClassFormatError('Invalid bootstrap index')
        targets=[]
        for cp in [bootstrap[n]['method_handle']]+bootstrap[n]['arguments']:
            tag,value=item(cp)
            if tag==15:targets.append(dict(member(value[1]),handle_kind=value[0]))
        call['dynamic']['method_handles']=targets
    types.discard(name)
    result=dict(name=name,superclass=parent,interfaces=interfaces,access=flags,major=major,minor=minor,
        type_references=sorted(types),member_references=refs,calls=calls,**members,**meta)
    result['annotations']=sorted(set(annotations))
    return result


def instructions(code):
    """Only expose reference-bearing opcodes; parse every instruction boundary."""
    widths={**dict.fromkeys([16,18,*range(21,26),*range(54,59),169,188],1),
            **dict.fromkeys([17,19,20,132,*range(153,169),*range(178,185),187,189,192,193,198,199],2),
            185:4,186:4,197:3,200:4,201:4}
    refs={18:'ldc',19:'ldc_w',20:'ldc2_w',178:'getstatic',179:'putstatic',180:'getfield',181:'putfield',
          182:'invokevirtual',183:'invokespecial',184:'invokestatic',185:'invokeinterface',186:'invokedynamic',
          187:'new',189:'anewarray',192:'checkcast',193:'instanceof',197:'multianewarray'}
    pc=0
    while pc<len(code):
        start=pc;op=code[pc];pc+=1
        if op>201:raise ClassFormatError('Reserved bytecode opcode')
        if op in (170,171):
            pc+=(4-pc%4)%4
            if pc+8>len(code):raise ClassFormatError('Truncated switch')
            if op==170:
                if pc+12>len(code):raise ClassFormatError('Truncated tableswitch')
                low,high=struct.unpack_from('>ii',code,pc+4);count=high-low+1;size=12+4*count
                if count<1:raise ClassFormatError('Invalid tableswitch bounds')
            else:
                count=struct.unpack_from('>i',code,pc+4)[0];size=8+8*count
                if count<0:raise ClassFormatError('Invalid lookupswitch count')
            pc+=size
        elif op==196:
            if pc>=len(code) or code[pc] not in (*range(21,26),*range(54,59),132,169):raise ClassFormatError('Invalid wide instruction')
            pc+=5 if code[pc]==132 else 3
        else:
            width=widths.get(op,0)
            if op in refs:
                if pc+width>len(code):raise ClassFormatError('Truncated operand')
                index=code[pc] if op==18 else struct.unpack_from('>H',code,pc)[0]
                yield {'offset':start,'opcode':refs[op],'cp_index':index}
            pc+=width
        if pc>len(code):raise ClassFormatError('Truncated instruction')
