"""Local Git source checkpoints and verified portable bundles; no remote publication."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import uuid

from workspace_paths import PACK_ROOT as PACK, DEV_ROOT, PROJECT_ROOT as PROJECT

BACKUPS = Path(r'E:\NeoCore备份')


def git(repository, *arguments):
    process = subprocess.run(['git', '-C', str(repository)] + list(arguments),
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
    if process.returncode:
        raise RuntimeError(process.stderr)
    return process.stdout.strip()


def selected_files():
    roots = [PACK/'NeoForgeCoreScripts', PACK/'entities', PACK.parent/'resource_pack_kFreO1qQ',
             PROJECT/'NeoCore分块任务', PROJECT/'development/neocore/retained_pack_material']
    roots += [DEV_ROOT/name for name in ('tests', 'templates', 'examples', 'fixtures', 'references')]
    roots += [DEV_ROOT/'vendor'/name for name in ('java_parser', 'java_grammar_src')]
    roots += [PROJECT/'refs'/name for name in ('goblintraders-1.11.2-source', 'goblintraders-1.11.2-input')]
    files = set(PROJECT.glob('*.md'))
    files.update(DEV_ROOT.parent.glob('*.md'))
    files.update(DEV_ROOT.parent.glob('*.cmd'))
    files.update(PACK.glob('*.json'))
    files.update(p for p in (DEV_ROOT).glob('*') if p.is_file() and
                 p.suffix in ('.py', '.json', '.txt', '.toml', '.cmd'))
    files.update((PROJECT/'refs').glob('goblintraders-1.11.2-*.json'))
    for root in roots:
        if not root.exists():
            continue
        for directory, names, leaves in os.walk(root):
            names[:] = [name for name in names if name not in
                        ('__pycache__', '.git', 'node_modules', '.gradle')]
            for name in names:
                path = Path(directory)/name
                if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                    raise ValueError('Backup refuses directory links: ' + str(path))
            files.update(Path(directory)/name for name in leaves if not name.endswith(('.pyc', '.pyo')))
    for path in files:
        if path.is_symlink() or not any(root.resolve() in path.resolve().parents for root in (PROJECT, DEV_ROOT.parent)):
            raise ValueError('Backup source escapes project: ' + str(path))
    return sorted(files)


def verify_restored_bytes(repository, commit, relative, records):
    """Check the actual recovery repository blobs, not just its HEAD identity."""
    process = subprocess.Popen(['git', '-C', str(repository), 'cat-file', '--batch'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for name, expected in records.items():
            request = commit + ':' + relative + '/' + name
            if '\n' in request or '\r' in request:
                raise ValueError('Unsupported newline in backup filename')
            process.stdin.write((request + '\n').encode('utf-8'))
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[1] != b'blob':
                raise RuntimeError('Missing recovery blob: ' + name)
            remaining, digest = int(header[2]), hashlib.sha256()
            while remaining:
                block = process.stdout.read(min(remaining, 1024 * 1024))
                if not block:
                    raise RuntimeError('Truncated recovery blob: ' + name)
                digest.update(block)
                remaining -= len(block)
            if process.stdout.read(1) != b'\n' or digest.hexdigest() != expected:
                raise RuntimeError('Recovery byte checksum mismatch: ' + name)
        process.stdin.close()
        if process.wait(timeout=30):
            raise RuntimeError('Git recovery blob verification failed')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)


def remove_recovery_clone(recovery):
    if (recovery.resolve().parent != BACKUPS.resolve() or
            not recovery.name.startswith('.restore-check-') or recovery.is_symlink() or
            (hasattr(recovery, 'is_junction') and recovery.is_junction())):
        raise ValueError('Recovery cleanup target escapes backup directory')
    def retry_readonly(function, filename, error):
        path = Path(filename).resolve()
        if not isinstance(error, PermissionError) or recovery.resolve() not in path.parents:
            raise error
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        function(filename)
    shutil.rmtree(recovery, onexc=retry_readonly)


def backup():
    previous_path = BACKUPS/'latest_backup.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    repository = BACKUPS/'repository'
    repository.mkdir(parents=True, exist_ok=True)
    if not (repository/'.git').exists():
        git(repository, 'init')
    git(repository, 'config', 'core.autocrlf', 'false')
    # Backup snapshots must store original bytes, regardless of user Git settings.
    (repository/'.gitattributes').write_bytes(b'* -text\n')
    # Vendor trees may carry their own .gitattributes; info/attributes overrides them.
    (repository/'.git/info').mkdir(parents=True, exist_ok=True)
    (repository/'.git/info/attributes').write_bytes(b'* -text\n')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    snapshot = repository/'snapshots'/stamp
    snapshot.mkdir(parents=True, exist_ok=False)
    records = {}
    sources = {}
    for path in selected_files():
        relative = (Path('tools')/path.relative_to(DEV_ROOT.parent) if DEV_ROOT.parent.resolve() in path.resolve().parents else Path('project')/path.relative_to(PROJECT))
        target = snapshot/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        target.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Backup checksum mismatch: ' + str(relative))
        records[relative.as_posix()] = digest
        sources[relative.as_posix()] = path
    for relative, digest in records.items():
        if hashlib.sha256(sources[relative].read_bytes()).hexdigest() != digest:
            raise RuntimeError('Source changed during backup: ' + relative)
    manifest = {'source_root': str(PROJECT), 'tool_root': str(DEV_ROOT), 'files': records,
        'excluded': ['dev/builds (regenerable releases)', 'Python caches', 'Zig/compiler installations',
                     'unrelated AddOn projects', 'external game installations'],
        'limits': 'Source backup only; checksums do not prove program/game compatibility.'}
    (snapshot/'backup_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    relative = snapshot.relative_to(repository).as_posix()
    git(repository, 'add', '--', '.gitattributes')
    # Compiled parser DLLs and vendor files can match global ignore rules.
    git(repository, 'add', '--sparse', '--force', '--', relative)
    git(repository, '-c', 'user.name=NeoCore Local Backup', '-c', 'user.email=local-backup@localhost',
        '-c', 'commit.gpgsign=false', 'commit', '-m', 'NeoCore source checkpoint ' + stamp)
    commit = git(repository, 'rev-parse', 'HEAD')
    bundle = BACKUPS/('NeoCore_' + stamp + '.bundle')
    git(repository, 'bundle', 'create', str(bundle), '--all')
    git(repository, 'bundle', 'verify', str(bundle))
    recovery = BACKUPS/('.restore-check-' + stamp)
    process = subprocess.run(['git', 'clone', '--bare', str(bundle), str(recovery)],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
    if process.returncode or git(recovery, 'rev-parse', 'HEAD') != commit:
        raise RuntimeError('Portable bundle recovery failed: ' + process.stderr)
    verify_restored_bytes(recovery, commit, relative, records)
    # Keep two expanded snapshots; older snapshots remain in compressed Git history.
    patterns = ['/.gitattributes', '/' + relative + '/']
    previous_snapshot = Path(previous['snapshot']) if previous.get('snapshot') else None
    if previous_snapshot is not None and repository.resolve() in previous_snapshot.resolve().parents:
        patterns.append('/' + previous_snapshot.relative_to(repository).as_posix() + '/')
    git(repository, 'sparse-checkout', 'init', '--no-cone')
    git(repository, 'sparse-checkout', 'set', '--no-cone', *patterns)
    report = {'repository': str(repository), 'snapshot': str(snapshot), 'commit': commit,
              'bundle': str(bundle), 'recovery_clone': None, 'files': len(records),
              'verified': True, 'byte_exact': True, 'history_preserved': True,
              'recovery_verification': 'Temporary bare clone and every source blob SHA256 verified, then clone removed.',
              'retention': 'Latest two expanded snapshots and latest two compressed bundles; full Git history retained.',
              'remote_published': False}
    remove_recovery_clone(recovery)
    keep = {bundle.resolve()}
    if previous.get('bundle'):
        keep.add(Path(previous['bundle']).resolve())
    for old_bundle in BACKUPS.glob('NeoCore_*.bundle'):
        if old_bundle.resolve().parent != BACKUPS.resolve() or old_bundle.is_symlink():
            raise ValueError('Bundle cleanup target escapes backup directory')
        if old_bundle.resolve() not in keep:
            old_bundle.unlink()
    (BACKUPS/'latest_backup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(backup(), ensure_ascii=False, indent=2))
