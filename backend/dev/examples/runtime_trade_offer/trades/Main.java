package trades;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.trading.MerchantOffer;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_trade_offer_example") public class Main {
 public int initial=run();public int total=0;
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public static int run(){Item payment=new Item(new Item.Properties());Item sold=new Item(new Item.Properties());MerchantOffer offer=Logic.make(payment,sold);return Logic.run(offer,new ItemStack(payment,7),ItemStack.EMPTY);}
 public void tick(ServerTickEvent.Post event){total=total+run();}
}