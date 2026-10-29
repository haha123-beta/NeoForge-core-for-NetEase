"""Validated mining recipe: Java21 Optional.ofNullable, reference subset only."""
def resolve(base,name,arity,actual):
    if base!='java.util.Optional' or name!='ofNullable' or arity!=1 or len(actual)!=1:return None
    kind=actual[0]
    if kind=='<null>':
        return dict(return_type='java.util.Optional',parameters=['java.lang.Object'],static_owner=base,
                    receiver_kind='game_api',checked_arguments=True,polymorphic_empty_optional=True)
    if not kind or kind in ('void','boolean','byte','short','char','int','long','float','double'):return None
    if '?' in kind or '<unknown>' in kind or ('.' not in kind and not kind.endswith('[]')):return None
    return dict(return_type='java.util.Optional<'+kind+'>',parameters=[kind],static_owner=base,
                receiver_kind='game_api',checked_arguments=True)
