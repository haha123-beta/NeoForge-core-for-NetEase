"""Observation sets only: no line/name/order-based expression anchors."""
import collections

def observations(classes,compiler_calls=()):
    calls=[]
    for row in classes:
        for call in row.get('calls',[]):
            calls.append(dict(class_name=row['name'],**call))
    bytecode={ (c['target']['owner'],c['target']['name'],c['target']['descriptor'])
               for c in calls if 'target' in c and c['opcode'].startswith('invoke') }
    resolved={tuple(c) for c in compiler_calls}
    return dict(bytecode_calls=calls,compiler_resolved_symbols=sorted(resolved),
        bytecode_symbol_set=sorted(bytecode),compiler_only_symbols=sorted(resolved-bytecode),
        bytecode_only_symbols=sorted(bytecode-resolved),
        comparison_kind='AGGREGATE_SYMBOL_OBSERVATIONS_NOT_EXPRESSION_ALIGNMENT',
        trusted_expression_anchors=[],production_descriptor_overrides=0,
        unknowns=['No bytecode-to-CFR expression bijection established',
                  'Compiler selections are compile-time types; bytecode includes bridges/synthetic calls and erased descriptors',
                  'Line numbers, names and instruction order cannot prove correspondence'])
