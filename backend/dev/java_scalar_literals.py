"""Reviewed character literals. Unicode preprocessing remains a diagnostic."""
import json,re

def character(raw,node,error):
    token=raw[1:-1]
    if '\\u' in token:raise error(node,'Java Unicode pre-lexing requires source mapping')
    escapes={'b':'\b','t':'\t','n':'\n','f':'\f','r':'\r','s':' ','"':'"',"'":"'",'\\':'\\'}
    if token.startswith('\\'):
        tail=token[1:]
        if tail in escapes:value=escapes[tail]
        elif re.fullmatch(r'[0-7]{1,2}|[0-3][0-7]{2}',tail):value=chr(int(tail,8))
        else:raise error(node,'Unreviewed character escape')
    else:value=token
    if len(value)!=1 or ord(value)>65535:raise error(node,'Character literal must be one UTF-16 unit')
    return 'u'+json.dumps(value,ensure_ascii=True)
