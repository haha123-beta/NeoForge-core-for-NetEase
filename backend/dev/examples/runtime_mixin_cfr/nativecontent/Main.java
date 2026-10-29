package nativecontent;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("cfr_native_example") public class Main {
 public Example menu=new Example(7);public int seen=Audit.tails;public int ticks=0;
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){ticks=ticks+1;menu=new Example(ticks);}
}