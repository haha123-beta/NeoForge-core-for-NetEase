"""Reviewed tool/holder-set data signatures. Native codecs and record text stay unresolved."""
TOOL='net.minecraft.world.item.component.Tool';RULE=TOOL+'.Rule';BLOCK='net.minecraft.world.level.block.Block';TAG='net.minecraft.tags.TagKey<'+BLOCK+'>';HOLDERS='net.minecraft.core.HolderSet';HOLDER='net.minecraft.core.Holder';BT='net.minecraft.tags.BlockTags'
STATE='net.minecraft.world.level.block.state.BlockState'
def resolve(raw,base,name,arity,actual,canonical):
    row=None;static=False;call_name=None
    if base==STATE:
        row={'getBlock':(BLOCK,[]),'isAir':('boolean',[])}.get(name)
        if name=='is' and arity==1 and actual[0] in (BLOCK,TAG,HOLDERS+'<'+BLOCK+'>'):
            row=('boolean',actual[:]);call_name='isBlock'
    elif base==TOOL:
        row={'rules':('java.util.List<'+RULE+'>',[]),'defaultMiningSpeed':('float',[]),'damagePerBlock':('int',[]),'getMiningSpeed':('float',['net.minecraft.world.level.block.state.BlockState']),'isCorrectForDrops':('boolean',['net.minecraft.world.level.block.state.BlockState']),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
    elif base==RULE:
        row={'blocks':(HOLDERS+'<'+BLOCK+'>',[]),'speed':('java.util.Optional<java.lang.Float>',[]),'correctForDrops':('java.util.Optional<java.lang.Boolean>',[]),'deniesDrops':(RULE,[TAG]),'minesAndDrops':(RULE,[TAG,'float']),'overrideSpeed':(RULE,[TAG,'float']),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
        static=name in ('deniesDrops','minesAndDrops','overrideSpeed')
        if static and arity and actual[0]=='java.util.List<'+BLOCK+'>' and name!='deniesDrops':
            row=(RULE,['java.util.List<'+BLOCK+'>','float']);call_name='_mines_blocks' if name=='minesAndDrops' else '_speed_blocks'
    elif base in (HOLDERS,HOLDERS+'.Named',HOLDERS+'.Direct'):
        row={'size':('int',[]),'canSerializeIn':('boolean',['net.minecraft.core.HolderOwner<'+BLOCK+'>']),'unwrapKey':('java.util.Optional<'+TAG+'>',[]),'contains':('boolean',[HOLDER+'<'+BLOCK+'>']),'hashCode':('int',[]),'equals':('boolean',['java.lang.Object'])}.get(name)
        if name=='key' and base.endswith('.Named'):row=(TAG,[])
    if base not in (STATE,TOOL,RULE,HOLDERS,HOLDERS+'.Named',HOLDERS+'.Direct'):return None
    if row is None:raise ValueError('Tool/holder-set API requires review (codecs/formatting are not implemented): '+name)
    result,formal=row
    if arity!=len(formal) or any(a!=f and a!='<null>' and f!='java.lang.Object' for a,f in zip(actual,formal)):raise ValueError('Tool data argument signature mismatch: '+name)
    data={'return_type':result,'parameters':formal,'receiver_kind':'game_api'}
    if static:data['static_owner']=base
    if call_name:data['call_name']=call_name
    return data
def resolve_field(owner,name):
    from java_block_tag_data import BLOCK_TAG_LOCATIONS
    if owner==BT and name in BLOCK_TAG_LOCATIONS:return {'return_type':TAG,'static_owner':owner,'final':True,'receiver_kind':'game_api'}
    if owner in (BT,TOOL,RULE,HOLDERS,HOLDERS+'.Named',HOLDERS+'.Direct'):raise ValueError('Tool/tag/holder field is not reviewed: '+name)
