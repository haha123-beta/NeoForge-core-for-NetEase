import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness import Package
from java_mixin_plan import plan,MixinPlanError
from translate_java import translate
from build_source_bundle import core_bundle,content_bundle
from test_native_mixin_lowering_r69 import FILES as MENU_FILES

HOOK='''package nativehooks;
import net.minecraft.world.inventory.MerchantResultSlot;
import net.minecraft.world.item.trading.Merchant;
import net.minecraft.resources.ResourceLocation;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.At;
import nativecontent.Audit;
@Mixin(value={MerchantResultSlot.class}) public class TradeHooks {
 @Shadow @Final private Merchant merchant;
 @ModifyArg(method={"onTake"},at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/player/Player;awardStat(Lnet/minecraft/resources/ResourceLocation;)V"))
 private ResourceLocation stat(ResourceLocation value){if(this.merchant!=null){Audit.tails++;}return value;}
}'''

def files(root,hook=HOOK):
    for name,raw in MENU_FILES.items():
        if name.endswith('mixins.json'):
            data=json.loads(raw);data['mixins'].append('TradeHooks');raw=json.dumps(data)
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw,encoding='utf-8')
    (root/'nativehooks/TradeHooks.java').write_text(hook,encoding='utf-8')

class NativeTradeTests(unittest.TestCase):
    def test_original_handlers_compile_register_and_release_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'input';files(root)
            result=translate(root,Path(tmp)/'output');self.assertEqual(result['manual_review'],0,result)
            content=content_bundle(Path(tmp)/'output/input',{'native_menu_example':'nativecontent.Main:_nc_mod_entry_0'})
            core=core_bundle();runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
            session=runtime.load('core.bundled_mods').BundledModSession(core['sources'],[content],runtime=runtime)
            try:
                state=session.loader.activate();self.assertTrue(state['native_menu_example']['ready'],state)
                hooks=runtime.load('neoforge.mixin_hooks');self.assertEqual(hooks.MixinHooks.count(),2)
                trade=runtime.load('minecraft.merchant_result_slot');obj=object.__new__(trade.MerchantResultSlot);obj.merchant=object()
                stat=trade.TRADED_WITH_VILLAGER
                self.assertIs(hooks.modify_argument(hooks.TRADE_STAT,obj,stat),stat)
                self.assertEqual(runtime.load('nativecontent.Audit').Audit.tails,2)
                manifest=content['runtime_requirements'] if 'runtime_requirements' in content else None
                self.assertIn('neocore.runtime.MixinHooks@2',str(result))
                session.close();self.assertEqual(hooks.MixinHooks.count(),0)
                self.assertIs(hooks.modify_argument(hooks.TRADE_STAT,obj,stat),stat)
            finally:session.close();runtime.close()

    def test_exact_site_and_final_field_constraints(self):
        for old,new in [('onTake','wrong'),('awardStat(','wrong('),('value="INVOKE"','value="HEAD"'),
                        ('@Shadow @Final','@Shadow @Final @org.spongepowered.asm.mixin.Mutable'),
                        ('Audit.tails++;','this.merchant=null;'),('method={"onTake"}','method={"onTake","wrong"}'),
                        ('private ResourceLocation','public ResourceLocation')]:
            with self.subTest(new=new),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);files(root,HOOK.replace(old,new))
                with self.assertRaises(MixinPlanError):plan(root)

    def test_result_slot_payment_order_and_failed_payment_xp(self):
        p=Package().load('core.source_modules').SourceModuleLoader(core_bundle()['sources'])
        self.addCleanup(p.close)
        m=p.load('minecraft.merchant_container');t=p.load('minecraft.trading');i=p.load('minecraft.item')
        r=p.load('minecraft.merchant_result_slot');h=p.load('neoforge.mixin_hooks');events=[]
        class Player:
            def level(self):return None
            def awardStat(self,stat,amount=1):events.append(('stat',str(stat),amount))
        class Trader(m.Merchant):
            def __init__(self):self.offers=t.MerchantOffers();self.xp=0
            def getOffers(self):return self.offers
            def notifyTradeUpdated(self,stack):events.append(('update',stack.getCount()))
            def notifyTrade(self,offer):events.append(('trade',offer.getUses()));offer.increaseUses()
            def getVillagerXp(self):return self.xp
            def overrideXp(self,value):events.append(('xp',value));self.xp=value
        player=Player();merchant=Trader();a=i.Item();b=i.Item();sold=i.Item()
        optional=p.load('java_stdlib.util').Optional
        offer=t.MerchantOffer(t.ItemCost(a,3),optional.of(t.ItemCost(b,2)),i.ItemStack(sold,2),3,5,0)
        merchant.offers.add(offer);slots=m.MerchantContainer(merchant)
        slots.setItem(0,i.ItemStack(b,4));slots.setItem(1,i.ItemStack(a,6))
        slot=r.MerchantResultSlot(player,merchant,slots,2,0,0);scope=h.MixinHooks.openScope(object())
        def high(receiver,stat):events.append(('hook',str(stat)));self.assertIs(receiver,slot);return 'high'
        def low(receiver,stat):events.append(('low',stat));return 'custom'
        scope.register(h.TRADE_STAT,low,500);scope.register(h.TRADE_STAT,high,1500)
        try:
            out=slot.remove(1);events[:]=[];slot.onTake(player,out)
            self.assertEqual((offer.getUses(),merchant.xp,slots.getItem(0).getCount(),slots.getItem(1).getCount()),(1,5,2,3))
            self.assertEqual([e[0] for e in events],['stat','trade','hook','low','stat','update','update','xp'])
            self.assertEqual(events[3],('low','high'));self.assertEqual(events[4],('stat','custom',1))
            # Preserve an active offer, then mutate the live stack without recomputing it.
            slots.getItem(1).setCount(0);events[:]=[];slot.onTake(player,out)
            self.assertEqual((offer.getUses(),merchant.xp),(1,10))
            self.assertEqual([e[0] for e in events],['stat','xp'])
        finally:scope.close()
        self.assertEqual(h.MixinHooks.count(),0)

if __name__=='__main__':unittest.main()
