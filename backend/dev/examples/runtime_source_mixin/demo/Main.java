package demo;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_source_mixin_example") public class Main {
 public int total=0;public int cancelled=Target.run(-1);
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){total=total+Target.run(1);}
}