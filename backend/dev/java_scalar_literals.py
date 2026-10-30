"""Java string and character escapes after JLS Unicode preprocessing."""
import json,re

def string_value(raw,node,error):
    token=raw[1:-1];result=[];index=0
    escapes={'b':'\b','t':'\t','n':'\n','f':'\f','r':'\r','s':' ','"':'"',"'":"'",'\\':'\\'}
    while index<len(token):
        char=token[index];index+=1
        if char in '\r\n':raise error(node,'Line terminator is invalid in a Java string literal')
        if char=='\\':
            if index==len(token):raise error(node,'Incomplete Java string escape')
            char=token[index];index+=1
            if char in escapes:char=escapes[char]
            elif char in '01234567':
                digits=char;limit=3 if char in '0123' else 2
                while index<len(token) and len(digits)<limit and token[index] in '01234567':
                    digits+=token[index];index+=1
                char=chr(int(digits,8))
            else:raise error(node,'Invalid Java literal escape after Unicode preprocessing')
        result.append(char)
    return ''.join(result)

def character(raw,node,error):
    token=raw[1:-1]
    escapes={'b':'\b','t':'\t','n':'\n','f':'\f','r':'\r','s':' ','"':'"',"'":"'",'\\':'\\'}
    if token.startswith('\\'):
        tail=token[1:]
        if tail in escapes:value=escapes[tail]
        elif re.fullmatch(r'[0-7]{1,2}|[0-3][0-7]{2}',tail):value=chr(int(tail,8))
        else:raise error(node,'Unreviewed character escape')
    else:value=token
    if len(value)!=1 or ord(value)>65535:raise error(node,'Character literal must be one UTF-16 unit')
    return 'u'+json.dumps(value,ensure_ascii=True)
