# -*- coding: utf-8 -*-
"""Official 1.21.1 payload and StreamCodec interface method contracts."""
from __future__ import absolute_import
from neoforge.network import CustomPacketPayload, StreamCodec
PAYLOAD='net.minecraft.network.protocol.common.custom.CustomPacketPayload'
CODEC='net.minecraft.network.codec.StreamCodec'
def method(name,args,result):return dict(name=name,parameters=args,return_type=result,static=False,abstract=True,visibility='public')
INTERFACE_CONTRACTS={PAYLOAD:dict(abi=1,helper_abi=6,java_name=PAYLOAD,methods=[method('type',[],PAYLOAD+'.Type<? extends '+PAYLOAD+'>')])}
INTERFACE_TYPES={PAYLOAD:CustomPacketPayload}
GENERIC_INTERFACES={CODEC:dict(abi=1,java_name=CODEC,type_parameters=['B','V'],methods=[method('decode',['B'],'V'),method('encode',['B','V'],'void')])}
GENERIC_TYPES={CODEC:StreamCodec}
from minecraft.official_interfaces import GENERIC_INTERFACES as OFFICIAL_GENERICS, GENERIC_TYPES as OFFICIAL_GENERIC_TYPES
GENERIC_INTERFACES.update(OFFICIAL_GENERICS)
GENERIC_TYPES.update(OFFICIAL_GENERIC_TYPES)
from minecraft.callback_contracts import GENERIC_INTERFACES as CALLBACK_GENERICS, GENERIC_TYPES as CALLBACK_GENERIC_TYPES
GENERIC_INTERFACES.update(CALLBACK_GENERICS)
GENERIC_TYPES.update(CALLBACK_GENERIC_TYPES)
from neoforge.interface_contracts import GENERIC_INTERFACES as PLATFORM_GENERICS, GENERIC_TYPES as PLATFORM_GENERIC_TYPES
GENERIC_INTERFACES.update(PLATFORM_GENERICS)
GENERIC_TYPES.update(PLATFORM_GENERIC_TYPES)
from minecraft.world_contracts import GENERIC_INTERFACES as WORLD_GENERICS, GENERIC_TYPES as WORLD_GENERIC_TYPES
GENERIC_INTERFACES.update(WORLD_GENERICS)
GENERIC_TYPES.update(WORLD_GENERIC_TYPES)

from neoforge.menu_interfaces import GENERIC_INTERFACES as MENU_GENERICS, GENERIC_TYPES as MENU_GENERIC_TYPES
GENERIC_INTERFACES.update(MENU_GENERICS)
GENERIC_TYPES.update(MENU_GENERIC_TYPES)
from minecraft.holder_contracts import GENERIC_INTERFACES as HOLDER_GENERICS, GENERIC_TYPES as HOLDER_TYPES
GENERIC_INTERFACES.update(HOLDER_GENERICS)
GENERIC_TYPES.update(HOLDER_TYPES)

def specialize(identity,arguments):
    import copy,re
    template=GENERIC_INTERFACES.get(identity)
    if template is None or len(arguments)!=len(template['type_parameters']) or any(not isinstance(a,(type(u''),str)) or not a or a in ('int','byte','short','long','char','float','double','boolean','void') or any(c in a for c in '<>[]?') for a in arguments):raise TypeError('Unreviewed generic interface binding')
    row=copy.deepcopy(template);mapping=dict(zip(row.pop('type_parameters'),arguments));row['java_name']=identity+'<'+','.join(arguments)+'>'
    # Java bounds are a compiler obligation. Runtime interface identity is erased;
    # checking source ancestry here would require loading not-yet-defined classes.
    def replace(kind):return re.sub(r'\b(?:'+'|'.join(re.escape(k) for k in mapping)+r')\b',lambda match:mapping[match.group(0)],kind)
    for m in row['methods']:
        m['parameters']=[replace(p) for p in m['parameters']];m['return_type']=replace(m['return_type'])
    row['generic_binding']={'java_name':identity,'arguments':list(arguments)}
    return row
