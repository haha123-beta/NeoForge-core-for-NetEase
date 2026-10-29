package generic.maps;

import java.util.Map;
import java.util.LinkedHashMap;
import java.util.Collection;
import java.util.Collections;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;

@Mod("runtime_map_example")
public class Main {
    public final Map<String,Integer> cache = new LinkedHashMap<>();
    public final Map<String,Integer> readonly = Collections.unmodifiableMap(cache);
    public final Collection<Integer> live = cache.values();
    public int ticks;

    public Main() {
        cache.put("initial", 2);
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }

    private void onTick(ServerTickEvent.Post event) {
        ticks++;
        cache.put("tick", ticks);
    }

    public int total() {
        int result = 0;
        for (Integer value : live) {
            result += value;
        }
        return result;
    }
}
