"""Build-time registration receipt with an owned, bounded actual Python2 worker."""
import hashlib, json, os, sys
from pathlib import Path
from build_source_bundle import core_bundle, content_bundle, SCRIPTS
from build_item_content import PROFILE
from translation_observer import call as observed


def collect(root, entrypoints, output, side='SERVER', platform_versions=None, python2=None):
    output = Path(output)
    output.mkdir(exist_ok=False)
    dev = Path(__file__).parent
    interpreter = Path(python2 or os.environ.get('NEOCORE_PYTHON2', str(dev.parent/'python27_validation/runtime/python.exe')))
    if not interpreter.is_file():
        raise RuntimeError('Actual Python2 required for item registration; configure NEOCORE_PYTHON2')
    payload = {'core':core_bundle(), 'content':content_bundle(root,entrypoints), 'side':side,
               'platform_versions':dict(platform_versions or {}),
               'loader_source':(SCRIPTS/'core/source_modules.py').read_text(encoding='utf-8-sig')}
    input_path, result_path = output/'input.json', output/'receipt.json'
    input_path.write_text(json.dumps(payload,ensure_ascii=True),encoding='utf-8')
    # Reuse the existing process lifecycle; no alternate worker framework.
    sys.path.insert(0,str(dev/'tools/neocore_gui_092'))
    from process_control import OwnedProcess
    with (output/'execution.log').open('wb') as log:
        worker = OwnedProcess([str(interpreter),'-B',str(dev/'item_registration_probe.py'),str(input_path),str(result_path)],log)
        code = observed('item_registration_execution',worker.wait,30)
    if code or not result_path.is_file():
        raise RuntimeError('Generated entry execution or content snapshot failed; see item_registration/execution.log')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if result.get('python_major') != 2 or result.get('status') != 'LOCAL_REGISTRATION_EXECUTED':
        raise RuntimeError('Registration receipt is not from a completed Python2 run')
    # This initial target profile has two locally verified vanilla identities.
    # Unknown vanilla references are rejected by the resource converter.
    declaration = {'schema_version':1,'profile':PROFILE,'items':result['items'],
                   'native_items':['minecraft:coal','minecraft:charcoal']}
    if result.get('blocks'):
        declaration['blocks']=result['blocks']
        declaration['native_items'].append('minecraft:flint')
    result['core_sources_sha256'] = hashlib.sha256(json.dumps(
        {n:r['sha256'] for n,r in payload['core']['sources'].items()},sort_keys=True).encode()).hexdigest()
    result['declaration'] = declaration
    (output/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return declaration
