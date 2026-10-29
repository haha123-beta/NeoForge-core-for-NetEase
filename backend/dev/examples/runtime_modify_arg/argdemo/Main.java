package argdemo;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_modify_arg_example") public class Main {
 public int total=0;public int initial=Target.run();
 public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){total=total+Target.run();}
}