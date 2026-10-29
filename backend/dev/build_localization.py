"""Translate explicit Java localization keys, with visible source-language fallback."""
import json,re

def build(source, key_map, read):
    languages,issues,fallbacks={},[],[]
    for path in sorted((source/'assets').glob('*/lang/*.json')):
        if not re.fullmatch(r'[a-z]{2}_[a-z]{2}',path.stem):
            raise ValueError('Unsupported locale: '+path.name)
        entries=json.loads(read(path.relative_to(source).as_posix()))
        if not isinstance(entries,dict):raise ValueError('Language must be a key/value object')
        locale=path.stem[:3]+path.stem[3:].upper()
        output=languages.setdefault(locale,{})
        for key,value in entries.items():
            if key not in key_map:
                issues.append({'source':path.relative_to(source).as_posix(),'category':'UNCONVERTED_TRANSLATION','key':key})
                continue
            if not isinstance(value,str) or any(c in value for c in '\r\n\t#%'):
                raise ValueError('Unsupported localized text: '+key)
            for target in key_map[key]:
                if target in output and output[target]!=value:raise ValueError('Conflicting localized key: '+target)
                output[target]=value
    # NetEase Chinese clients do not reliably fall back to another pack locale.
    # Keep the actual English source names; never invent a Chinese translation.
    english=languages.get('en_US',{})
    for locale in sorted(set(languages)|{'zh_CN'}):
        output=languages.setdefault(locale,{})
        for key,value in english.items():
            if key not in output:
                output[key]=value;fallbacks.append({'locale':locale,'key':key,'source_locale':'en_US'})
    required={target for values in key_map.values() for target in values}
    for key in sorted(required-set(english)):
        if not all(key in entries for entries in languages.values()):
            issues.append({'category':'MISSING_TRANSLATION','key':key})
    files={'resource/texts/'+locale+'.lang':''.join(k+'='+v+'\n' for k,v in sorted(entries.items())).encode('utf-8')
           for locale,entries in languages.items()}
    files['resource/texts/languages.json']=json.dumps(sorted(languages)).encode('utf-8')
    return {'files':files,'locales':sorted(languages),'issues':issues,'fallbacks':fallbacks}
