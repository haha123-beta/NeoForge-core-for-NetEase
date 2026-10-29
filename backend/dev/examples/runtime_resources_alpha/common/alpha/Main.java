package common.alpha;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("resources_alpha") public class Main {
 public int initial=Helper.compute(3);public int total=0;
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){total=total+initial;}
}