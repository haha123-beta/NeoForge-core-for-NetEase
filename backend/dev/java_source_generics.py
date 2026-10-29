"""Source-owned generic ancestor views; runtime class identity remains erased."""
import copy,re
from java_library_signatures import generic_arguments

def parameters(raw):
    result={}
    if not raw:return result
    for item in generic_arguments('_'+raw,allow_wildcards=True):
        pair=re.split(r'\s+extends\s+',item.strip(),maxsplit=1)
        name=pair[0].strip()
        if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*',name) or name in result:raise ValueError('Invalid generic type parameter')
        bound=pair[1].strip() if len(pair)>1 else 'java.lang.Object'
        if '&' in bound:raise ValueError('Generic intersection bound requires lowering')
        result[name]=bound
    return result

def specialize(metadata,arguments,unit,project_types,error_type,origin):
    from java_method_overloads import canonical,erased_signature
    from java_generic_contracts import substitute,proves_bound
    try:names=parameters(metadata.get('type_parameters'))
    except ValueError as error:raise error_type(origin,str(error))
    if not names or len(arguments)!=len(names):raise error_type(origin,'Source generic ancestor requires matching type argument count')
    if any(a in ('boolean','byte','short','char','int','long','float','double','void') or '?' in a for a in arguments):raise error_type(origin,'Source generic ancestor requires reference type arguments without wildcards')
    bindings=dict(zip(names,arguments));context=dict(metadata,external=True)
    for name,bound in names.items():
        expected=canonical(substitute(bound,bindings),context,unit)
        argument=bindings[name]
        if '<' in expected or not proves_bound(argument.split('<',1)[0],expected,unit,project_types):raise error_type(origin,'Source generic ancestor bound needs reviewed subtype proof',{'parameter':name,'argument':argument,'bound':expected})
    row=copy.deepcopy(metadata)
    identity=row['java_name'];row['erased_java_name']=identity
    row['java_name']=identity+'<'+','.join(arguments)+'>'
    row['type_parameters']=None;row['generic_bindings']=bindings
    for key in ('superclass','interfaces','interface_extends'):
        if row.get(key):row[key]=substitute(row[key],bindings)
    for member in row['fields']:
        member['declared_type']=substitute(member['declared_type'],bindings)
    for original,method in zip(metadata['methods'],row['methods']):
        if set(parameters(method.get('type_parameters')))&set(bindings):raise error_type(origin,'Shadowed method generic parameters require lowering')
        method['_nc_runtime_signature']=erased_signature(original,context,unit)
        for parameter in method['parameters']:parameter['declared_type']=substitute(parameter['declared_type'],bindings)
        if method.get('return_type'):method['return_type']=substitute(method['return_type'],bindings)
    return row

def runtime_signature(method,owner,unit):
    from java_method_overloads import signature
    if method.get('type_parameters'):
        from java_method_overloads import erased_signature
        return erased_signature(method,owner,unit)
    return tuple(method['_nc_runtime_signature']) if '_nc_runtime_signature' in method else signature(method,owner,unit)
