"""JLS 21 3.3 Unicode translation, with original UTF-8 byte provenance."""
import string

class UnicodeInputError(ValueError):
    def __init__(self,offset,message):
        self.offset=offset
        super().__init__(message)

def translate(text):
    units=[];offset=0;index=0;slashes=0;last_escape=False;count=0
    while index<len(text):
        char=text[index];start=offset;consumed=1;escaped=False
        if char=='\\' and (last_escape or slashes%2==0) and text[index+1:index+2]=='u':
            end=index+2
            while text[end:end+1]=='u':end+=1
            digits=text[end:end+4]
            if len(digits)!=4 or any(c not in string.hexdigits for c in digits):
                raise UnicodeInputError(start,'Invalid eligible Java Unicode escape')
            char=chr(int(digits,16));consumed=end+4-index;escaped=True;count+=1
        units.append((char,start))
        offset+=len(text[index:index+consumed].encode('utf-8'));index+=consumed
        slashes=slashes+1 if char=='\\' else 0
        last_escape=escaped
    result=[];positions=[];index=0
    while index<len(units):
        char,start=units[index];code=ord(char)
        if 0xD800<=code<=0xDBFF and index+1<len(units) and 0xDC00<=ord(units[index+1][0])<=0xDFFF:
            char=chr(0x10000+((code-0xD800)<<10)+ord(units[index+1][0])-0xDC00);index+=1
        elif 0xD800<=code<=0xDFFF:
            raise UnicodeInputError(start,'Unpaired Unicode surrogate requires UTF-16 token lowering')
        result.append(char);positions.extend([start]*len(char.encode('utf-8')));index+=1
    positions.append(len(text.encode('utf-8')))
    return ''.join(result),positions,count

def line_at(raw,offset):
    prefix=raw[:offset].replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    return prefix.count(b'\n')+1
