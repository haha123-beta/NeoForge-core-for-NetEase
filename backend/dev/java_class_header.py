"""Read class identity/access/parents only. No bytecode evaluation or mod loading."""
import struct

def read(data):
    if data[:4]!=b'\xca\xfe\xba\xbe':raise ValueError('Not a Java class')
    count=struct.unpack_from('>H',data,8)[0];offset=10;pool=[None]*count;index=1
    while index<count:
        tag=data[offset];offset+=1
        if tag==1:
            size=struct.unpack_from('>H',data,offset)[0];offset+=2
            pool[index]=data[offset:offset+size].decode('utf-8',errors='replace');offset+=size
        elif tag in (7,8,16,19,20):pool[index]=struct.unpack_from('>H',data,offset)[0];offset+=2
        elif tag in (3,4,9,10,11,12,17,18):offset+=4
        elif tag in (5,6):offset+=8;index+=1
        elif tag==15:offset+=3
        else:raise ValueError('Unknown constant-pool tag: '+str(tag))
        index+=1
    flags,identity,parent,size=struct.unpack_from('>4H',data,offset);offset+=8
    name=lambda item:pool[pool[item]].replace('/','.') if item else None
    interfaces=[name(struct.unpack_from('>H',data,offset+2*i)[0]) for i in range(size)]
    return dict(access_flags=flags,name=name(identity),superclass=name(parent),interfaces=interfaces)
