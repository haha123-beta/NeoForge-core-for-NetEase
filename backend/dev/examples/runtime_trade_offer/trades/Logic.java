package trades;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.trading.ItemCost;
import net.minecraft.world.item.trading.MerchantOffer;
import net.minecraft.world.item.trading.MerchantOffers;
public class Logic {
 public static MerchantOffer make(Item payment,Item sold){return new MerchantOffer(new ItemCost(payment,3),new ItemStack(sold,2),2,5,0);}
 public static int run(MerchantOffer offer,ItemStack a,ItemStack b){if(!offer.take(a,b))return -1;offer.increaseUses();MerchantOffers all=new MerchantOffers();all.add(offer);return all.get(0).getUses()*100+a.getCount();}
}