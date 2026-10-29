"""Official NeoForge API probes using frozen local installer output, never mod input."""
import hashlib,json
from pathlib import Path
from workspace_paths import DEV_ROOT
from java_official_probe import jars,run_with_dependencies

def run_original(source,groups=()):
    manifest=json.loads((DEV_ROOT/'references/checkpoint-0.8.7/named_platform_manifest.json').read_text(encoding='utf-8'))
    dependencies=[]
    for row in manifest['jars']:
        path=Path(row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Frozen official platform reference changed: '+str(path))
        dependencies.append(path)
    return run_with_dependencies(source,dependencies+jars(groups)[1:])
