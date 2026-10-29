package nativecontent;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
public class Example extends AbstractContainerMenu {
 public int body=0;
 public Example(int id){super(null,id);body=Audit.tails;}
 public boolean stillValid(Player p){return true;}
 public ItemStack quickMoveStack(Player p,int index){return null;}
}