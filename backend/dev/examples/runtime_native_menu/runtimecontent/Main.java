package runtimecontent;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_native_menu") public class Main {
 public Example menu=new Example(7);public int seen=Audit.tails;public int total=0;
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){total=total+menu.incrementStateId();}
}