package staticdemo;
import static util.Tools.BASE;
import static util.Tools.TITLE;
import static util.Tools.add;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_static_imports_example")
public class Main {
    public int total = BASE;
    public String label = TITLE;
    public Main() { NeoForge.EVENT_BUS.addListener(this::tick); }
    public void tick(ServerTickEvent.Post event) { total = add(total, 1); }
}
