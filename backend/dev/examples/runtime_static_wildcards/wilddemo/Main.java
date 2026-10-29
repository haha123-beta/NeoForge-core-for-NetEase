package wilddemo;
import static wildutil.IntTools.*;
import static wildutil.RefTools.*;
import static wildutil.IntTools.BASE;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_static_wildcards_example")
public class Main {
    public int total=BASE;
    public int selected=choose(1);
    public int accessSelected=choose("x");
    public Main(){NeoForge.EVENT_BUS.addListener(this::tick);}
    public void tick(ServerTickEvent.Post event){total=bump(total);}
}
