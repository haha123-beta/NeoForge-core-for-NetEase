package fielddemo;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_mixin_fields_example") public class Main {
 public int total=0;
 public int checks=0;
 public Target first=new Target(2);
 public Target second=new Target(7);
 public Main(){if(!first.enabled(1))checks=checks+1;if(first.enabled(-1))checks=checks+1;NeoForge.EVENT_BUS.addListener(this::tick);}
 public void tick(ServerTickEvent.Post event){total=total+first.read()+second.read();}
}
