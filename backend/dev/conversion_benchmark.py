"""Generic source-generation benchmark, fixed input hash and explicit denominator."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def category(row):
    reason=row.get('reason','')
    if re.search(r'ASM|modlauncher|org\.objectweb\.asm|java\.lang\.(reflect|invoke)',reason,re.I):return 'asm_jvm'
    if re.search(r'net\.minecraft\.|com\.mojang\.',reason):return 'missing_official_class_or_abi'
    if 'Unresolved external import:' in reason or 'Unresolved/ambiguous superclass ABI:' in reason:return 'external_or_source_dependency'
    return 'language_or_adapter'


def summarize(report,jar,denominator):
    if report['files']!=denominator:raise ValueError('Input source count differs from frozen benchmark denominator')
    generated=[r for r in report['results'] if r['status']=='GENERATED_REVIEW_REQUIRED']
    blockers=Counter(category(r) for r in report['results'] if r['status']!='GENERATED_REVIEW_REQUIRED')
    return {'schema_version':1,'input_jar':Path(jar).name,'input_sha256':hashlib.sha256(Path(jar).read_bytes()).hexdigest(),
        'generated':len(generated),'denominator':denominator,'conversion_rate':len(generated)/denominator,
        'manual_review':report['manual_review'],'failed':report['failed'],
        'generated_with_missing_dependencies':sum(bool(r.get('missing_generated_dependencies')) for r in generated),
        'first_blocker_categories':dict(blockers),'first_blocker_reasons':dict(Counter(r.get('reason') for r in report['results'] if r['status']!='GENERATED_REVIEW_REQUIRED')),
        'skipped_optional':report.get('skipped_optional',[]),'capability_blockers':report.get('capability_blockers',[]),
        'source_generation_only':True,'engine_loaded':False,'playable':False,
        'limits':['Per-file first diagnostic, not an exhaustive capability inventory.','Generated files may have unresolved generated dependencies.','Optional skips change behavior; partial conversion is not compatibility.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--jar',type=Path,required=True)
    p.add_argument('--denominator',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.denominator<=0:raise ValueError('Positive denominator required')
    result=summarize(json.loads(a.report.read_bytes()),a.jar,a.denominator)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('{}/{} ({:.2%}); source generation only'.format(result['generated'],result['denominator'],result['conversion_rate']))


if __name__=='__main__':main()
