"""Explicit lossy source-conversion policy. Never certifies gameplay equivalence."""
import json
from pathlib import Path
from java_mixin_plan import config_requirements, digest


def partition(root):
    root = Path(root).resolve()
    active, skipped, unsupported = [], [], []
    for issue in config_requirements(root):
        if issue['kind'] != 'mixin':
            unsupported.append(dict(issue, category='asm_jvm', status='UNSUPPORTED'))
            continue
        path = (root / issue['source']).resolve()
        # Missing, escaping, malformed or non-boolean flags are never optional.
        try:
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError('Missing/escaping config')
            raw = path.read_bytes()
            config = json.loads(raw.decode('utf-8-sig'))
            optional = isinstance(config, dict) and config.get('required') is False
        except (OSError, ValueError):
            optional = False
        if optional:
            skipped.append(dict(issue, category='optional_mixin', status='SKIPPED_OPTIONAL',
                label='已跳过（可选）', sha256=digest(raw),
                reason='Explicit degraded conversion: entire optional config, plugin and injections skipped; behavior may differ.'))
        else:
            active.append(issue)
    return active, skipped, unsupported
