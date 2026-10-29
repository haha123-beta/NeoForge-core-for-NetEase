"""Development-only evidence records; never equate harness success with engine verification."""
import hashlib
import json
from pathlib import Path


def source_fingerprint(pack_root):
    root = Path(pack_root)
    paths = set((root / 'NeoForgeCoreScripts').rglob('*.py'))
    from workspace_paths import PACK_ROOT, DEV_ROOT
    dev = DEV_ROOT if root.resolve() == PACK_ROOT.resolve() else root / 'dev'
    paths.update(dev.glob('*.py'))
    for filename in ('java_import_index.json', 'java_frontend_requirements.txt',
                     'translation_job.example.json', 'translation_job.sample.json', 'NeoCore转换.cmd'):
        path = dev / filename
        if path.is_file():
            paths.add(path)
    vendor = dev / 'vendor/java_parser'
    if vendor.exists():
        paths.update(path for path in vendor.rglob('*') if path.is_file() and
            (path.suffix in ('.py', '.pyd') or path.name == 'METADATA'))
    grammar = dev / 'vendor/java_grammar_src'
    for relative in ('grammar.js', 'neocore_patch.json', 'src/parser.c', 'src/tree_sitter/parser.h',
        'tree_sitter_java_qualified.dll'):
        path = grammar / relative
        if path.is_file():
            paths.add(path)
    for folder in ('tests', 'templates', 'examples', 'fixtures'):
        base = dev / folder
        if base.exists():
            paths.update(path for path in base.rglob('*') if path.is_file()
                and path.suffix in ('.py', '.java', '.toml', '.json'))
    return {(path.relative_to(root).as_posix() if root.resolve() in path.resolve().parents else 'dev/' + path.relative_to(dev).as_posix()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths) if '__pycache__' not in path.parts}


def write_report(path, report):
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
