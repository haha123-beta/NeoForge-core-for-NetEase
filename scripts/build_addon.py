"""Regenerate an independent core AddOn into a new directory."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend/dev'))
from build_distribution import build
if __name__=='__main__':
    output=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'outputs/addon-0.9.8'
    result=build(output,[],platform_versions={'minecraft':'1.21.1','neoforge':'21.1.233'})
    print(json.dumps({'protocol':result['protocol'],'core_modules':result['core_modules'],'engine_verified':False},ensure_ascii=True))
