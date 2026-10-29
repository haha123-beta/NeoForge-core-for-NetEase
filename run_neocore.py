"""Configure this checkout locally, then run GUI, CLI or compatibility mining."""
from pathlib import Path
import json,os,runpy,sys
ROOT=Path(__file__).resolve().parent
DEV=ROOT/'backend/dev'
def configure():
 config={'dev_root':str(DEV),'python2':os.environ.get('NEOCORE_PYTHON2','')}
 for p in (ROOT/'backend.json',DEV/'tools/neocore_gui_092/backend.json'):
  p.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
 return config
def main():
 mode=sys.argv[1] if len(sys.argv)>1 else 'gui'
 if mode not in ('gui','cli','mining','configure'):raise SystemExit('Usage: python run_neocore.py [gui|cli|mining|configure] [arguments]')
 configure()
 if mode=='configure':print('Local backend configured.');return
 os.chdir(ROOT)
 script=DEV/'compatibility_mining.py' if mode=='mining' else ROOT/('app.py' if mode=='gui' else 'cli.py')
 sys.path.insert(0,str(DEV if mode=='mining' else ROOT));sys.argv=[str(script),*sys.argv[2:]]
 runpy.run_path(str(script),run_name='__main__')
if __name__=='__main__':main()
