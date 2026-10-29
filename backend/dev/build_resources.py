"""Desktop-only conservative resource staging. Never rewrites the extracted mod."""
import argparse
import json
from pathlib import Path
import re
import uuid


def build(source, output, pack_id):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('Source directory does not exist')
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}', pack_id):
        raise ValueError('Invalid pack ID')
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Output and source must be separate trees')
    if output.exists():
        raise ValueError('Output already exists; choose a new build directory')
    files, translations, issues, copied = {}, {}, [], []
    def issue(path, reason):
        issues.append({'source': path.as_posix(), 'reason': reason})
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if source not in path.resolve().parents:
            raise ValueError('Input symlink escapes source: ' + str(relative))
        parts = relative.parts
        if not parts or parts[0] not in ('assets', 'data'):
            continue
        if len(parts) >= 4 and parts[0] == 'assets' and parts[2] == 'lang' and path.suffix == '.json':
            language = path.stem
            if not re.fullmatch(r'[a-z]{2}_[a-z]{2}', language):
                issue(relative, 'Unsupported locale code')
                continue
            language = language[:3] + language[3:].upper()
            payload = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(payload, dict):
                raise ValueError('Language JSON must be an object: ' + str(relative))
            entries = translations.setdefault(language, {})
            for key, value in sorted(payload.items()):
                if not isinstance(value, str) or not key or any(c in key for c in '=\r\n#\t'):
                    issue(relative, 'Invalid translation entry: ' + key)
                    continue
                if any(c in value for c in '\r\n#\t%'):
                    issue(relative, 'Requires text/format semantic conversion: ' + key)
                    continue
                if key in entries and entries[key] != value:
                    raise ValueError('Conflicting translation: ' + key)
                entries[key] = value
        elif len(parts) >= 4 and parts[0] == 'assets' and parts[2] == 'textures' and path.suffix == '.png':
            data = path.read_bytes()
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid PNG signature: ' + str(relative))
            target = Path('textures', parts[1], *parts[3:]).as_posix()
            if target.lower() in {name.lower() for name in files}:
                raise ValueError('Conflicting texture path: ' + target)
            files[target] = data
            copied.append({'source': relative.as_posix(), 'output': target})
        else:
            issue(relative, 'No converter for this resource; manual port required')
    for language, entries in sorted(translations.items()):
        files['texts/' + language + '.lang'] = ''.join(
            key + '=' + value + '\n' for key, value in sorted(entries.items())).encode('utf-8')
    files['texts/languages.json'] = json.dumps(sorted(translations)).encode('utf-8')
    stable_id = lambda name: str(uuid.uuid5(uuid.NAMESPACE_URL, 'neocore:' + pack_id + ':' + name))
    manifest = {'format_version': 2, 'header': {'name': pack_id + ' resource staging',
        'description': 'NeoCore partial conversion; inspect build_report.json',
        'uuid': stable_id('header'), 'version': [1, 0, 0], 'min_engine_version': [1, 20, 0]},
        'modules': [{'type': 'resources', 'uuid': stable_id('resources'), 'version': [1, 0, 0]}]}
    report = {'status': 'partial' if issues else 'staged', 'engine_verified': False,
        'source': str(source), 'textures': copied, 'issues': issues,
        'limits': ['Textures are copied but not bound to entities/items/blocks.',
                   'Translation keys are preserved; engine naming needs explicit mapping.',
                   'Java models, recipes, animations, shaders and bytecode are not converted.']}
    files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    files['build_report.json'] = json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')
    output.mkdir(parents=True)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--pack-id', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.pack_id), ensure_ascii=False, indent=2))
