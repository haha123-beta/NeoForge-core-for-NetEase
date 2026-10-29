# -*- coding: utf-8 -*-
"""Python 2 worker: execute original generated entry/lifecycle, emit ID receipt."""
from __future__ import print_function
import io, json, sys, traceback


def main():
    with io.open(sys.argv[1], 'r', encoding='utf-8') as f:
        payload = json.load(f)
    scope = {'__name__':'item_registration_loader'}
    eval(compile(payload['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), scope)
    runtime = scope['SourceModuleLoader'](payload['core']['sources'])
    session = None
    try:
        session = runtime.load('core.bundled_mods').BundledModSession(
            payload['core']['sources'], [payload['content']], payload['side'],
            payload.get('platform_versions'), runtime=runtime)
        results = session.loader.activate()
        if not results or any(not row.get('ready') for row in results.values()):
            raise RuntimeError('Original generated entry/lifecycle failed: ' + repr(results))
        describe = runtime.load('core.item_content').describe
        items = [dict(describe(value), identifier=name) for name,value in
                 sorted(session.loader.registries.get('minecraft:item', {}).items())]
        registry = session.loader.registries.get('minecraft:item', {})
        block_registry=session.loader.registries.get('minecraft:block',{})
        block_describe=runtime.load('core.block_content').describe
        blocks=[dict(block_describe(value,registry),identifier=name) for name,value in sorted(block_registry.items())]
        creative_ids = runtime.load('core.item_content').creative_snapshot(session.loader.contexts,registry)
        for row in items:
            if row['identifier'] in creative_ids:
                row['creative_tab'] = 'minecraft:ingredients'
        building_ids=runtime.load('core.item_content').creative_snapshot(session.loader.contexts,registry,'BUILDING_BLOCKS') if blocks else []
        for row in items:
            if row['identifier'] in building_ids:row['creative_tab']='minecraft:building_blocks'
        result = {'status':'LOCAL_REGISTRATION_EXECUTED', 'python_major':sys.version_info[0],
                  'blocks':blocks,
                  'items':items, 'mods':results, 'engine_verified':False,
                  'creative_event_evidence':{'tab':'minecraft:ingredients','items':creative_ids,
                                             'scope':'LOCAL_ORIGINAL_CALLBACK_NOT_NATIVE_GUI'}}
        with io.open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(u'{}'.format(json.dumps(result, ensure_ascii=True)))
    finally:
        if session is not None:
            session.close()
        runtime.close()


if __name__ == '__main__':
    main()
