"""Regenerate/build the scoped-record grammar patch using pinned local development tools."""
import hashlib
import json
from pathlib import Path
import subprocess

DEV = Path(__file__).resolve().parent
ROOT = DEV / 'vendor/java_grammar_src'
CLI = DEV / 'vendor/tree_cli/node_modules/tree-sitter-cli/tree-sitter.exe'
ZIG = DEV / 'vendor/zig/ziglang/zig.exe'


def build():
    for path in (ROOT / 'grammar.js', CLI, ZIG):
        if not path.is_file():
            raise FileNotFoundError('Required local build dependency is missing: ' + str(path))
    manifest = json.loads((ROOT / 'neocore_patch.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256((ROOT / 'grammar.js').read_bytes()).hexdigest()
    if digest != manifest['grammar_sha256']:
        raise ValueError('Grammar changed; review/update the patch manifest before building')
    cli_version = subprocess.check_output([str(CLI), '--version'], text=True).strip()
    zig_version = subprocess.check_output([str(ZIG), 'version'], text=True).strip()
    if not cli_version.startswith('tree-sitter 0.24.7') or zig_version != '0.14.1':
        raise ValueError('Expected tree-sitter-cli 0.24.7 and zig 0.14.1')
    subprocess.run([str(CLI), 'generate'], cwd=ROOT, check=True)
    subprocess.run([str(ZIG), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2',
        '-Isrc', 'src/parser.c', '-o', 'tree_sitter_java_qualified.dll'], cwd=ROOT, check=True)
    manifest.update(revision='0.23.5+neocore.qualified-record.1', generator_version='0.24.7',
        c_compiler='zig 0.14.1', target='x86_64-windows-gnu', abi=14,
        parser_sha256=hashlib.sha256((ROOT / 'src/parser.c').read_bytes()).hexdigest(),
        library_sha256=hashlib.sha256((ROOT / 'tree_sitter_java_qualified.dll').read_bytes()).hexdigest())
    (ROOT / 'neocore_patch.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
