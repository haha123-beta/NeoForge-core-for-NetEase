"""Verify a NeoCore source package against its relative SHA-256 manifest.

This checks byte integrity, not author identity or engine compatibility. For an
independent trust anchor pass --manifest-sha256 from the published release.
Local configuration and outputs are intentionally outside the source manifest.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath


def verify(root, expected_manifest=None):
    root=Path(root).resolve()
    raw=(root/'SOURCE_MANIFEST.json').read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    issues=[]
    if expected_manifest and digest!=expected_manifest.lower():
        issues.append('Manifest SHA-256 does not match the independent anchor')
    data=json.loads(raw)
    seen=set();checked=0
    for row in data['files']:
        name=row['path'];relative=PurePosixPath(name)
        if (not name or '\\' in name or ':' in name or relative.is_absolute()
                or any(x in ('','.','..') for x in name.split('/')) or name in seen):
            issues.append('Invalid or duplicate manifest path: '+name);continue
        seen.add(name);target=root.joinpath(*relative.parts)
        if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction())
               for p in [target,*list(target.parents)[:len(relative.parts)-1]]):
            issues.append('Source links are not accepted: '+name);continue
        if not target.is_file():issues.append('Missing file: '+name);continue
        if not re.fullmatch('[0-9a-f]{64}',row['sha256']):
            issues.append('Invalid SHA-256: '+name);continue
        content=target.read_bytes();checked+=1
        if len(content)!=row['bytes'] or hashlib.sha256(content).hexdigest()!=row['sha256']:
            issues.append('Changed file: '+name)
    return dict(status='PASSED_SOURCE_INTEGRITY' if not issues else 'FAILED',
                version=data.get('version'),checked_files=checked,manifest_sha256=digest,
                independently_anchored=expected_manifest is not None,
                engine_verified=False,issues=issues)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--manifest-sha256')
    args=parser.parse_args()
    try:result=verify(args.root,args.manifest_sha256)
    except (OSError,ValueError,KeyError,TypeError) as error:
        result=dict(status='FAILED',engine_verified=False,issues=[str(error)])
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return 0 if result['status']=='PASSED_SOURCE_INTEGRITY' else 1


if __name__=='__main__':raise SystemExit(main())
