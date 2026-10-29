package generic.remap;
import java.util.Map;
import java.util.LinkedHashMap;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_map_defaults_example")
public class Main {
    public final Map<String,Integer> values = new LinkedHashMap<>();
    public int ticks;
    public Main() {
        values.put("count", 0);
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }
    private void onTick(ServerTickEvent.Post event) {
        ticks++;
        values.merge("count", 1, (old, next) -> old + next);
        values.compute("mirror", (key, old) -> values.get("count"));
    }
}
